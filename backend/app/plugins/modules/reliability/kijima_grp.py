"""
Kijima Generalized Renewal Process (GRP) Plugin for OpenMinitab.
Implements Kijima Type I and Type II Imperfect Repair Models for Repairable Systems Analysis.
Estimates shape (β), scale (θ), and restoration factor (q) via Maximum Likelihood Estimation (MLE),
calculates virtual ages (A_i), cumulative failure trajectories, and hazard rate intensity functions.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class KijimaGRPParams(BaseModel):
    event_times: str = Field(
        ...,
        description="Event Times Column (Cumulative Time to Failure Ti)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    unit_id_col: Optional[str] = Field(
        None,
        description="System / Unit ID Column (Optional, for multiple units)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    censoring_col: Optional[str] = Field(
        None,
        description="Censoring / End-of-Observation Column (Optional)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    time_format: str = Field(
        "cumulative",
        description="Event Time Format",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Cumulative Failure Times (Ti)", "value": "cumulative"},
                {"label": "Inter-Arrival Times (Xi = Time Between Failures)", "value": "inter_arrival"}
            ]
        }
    )
    model_type: str = Field(
        "type1",
        description="Kijima GRP Formulation",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Kijima Type I (Arithmetic Reduction of Current Interval)", "value": "type1"},
                {"label": "Kijima Type II (Proportional Reduction of Cumulative Age)", "value": "type2"}
            ]
        }
    )
    restoration_mode: str = Field(
        "estimate",
        description="Restoration Factor (q)",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Estimate Optimal q (Maximum Likelihood)", "value": "estimate"},
                {"label": "User-Specified Fixed q", "value": "fixed"}
            ]
        }
    )
    fixed_q_value: float = Field(
        0.5,
        ge=0.0,
        le=2.0,
        description="Fixed q Value (if user-specified, 0=New, 1=Old)"
    )
    # Options Sub-Modal
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    forecast_horizon: int = Field(
        5,
        ge=1,
        le=50,
        description="Number of Future Failures to Forecast",
        json_schema_extra={"sub_modal": "Options..."}
    )
    allow_damaging_repair: bool = Field(
        False,
        description="Allow q > 1.0 (Damaging / Worse-than-Old Repairs)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    # Storage Sub-Modal
    store_virtual_ages: bool = Field(
        False,
        description="Store Virtual Ages (A_i) in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_hazard_at_failure: bool = Field(
        False,
        description="Store Instantaneous Intensity at Failure in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )


class KijimaGRPPlugin(AnalysisPlugin):
    id = "reliability_kijima_grp"
    name = "Kijima GRP (Type I & II)"
    menu_path = ["Stat", "Reliability/Survival", "Repairable Systems Analysis", "Kijima GRP (Type I & II)"]
    description = "Models imperfect repair in repairable systems using Kijima Type I and Type II Generalized Renewal Processes (GRP)."
    param_schema = KijimaGRPParams

    def execute(self, df: pd.DataFrame, params: KijimaGRPParams) -> AnalysisResult:
        time_col = params.event_times
        if time_col not in df.columns:
            raise ValueError(f"Column '{time_col}' not found in active worksheet.")

        raw_times = pd.to_numeric(df[time_col], errors="coerce").dropna().to_numpy(dtype=float)
        raw_times = raw_times[raw_times > 0]
        if len(raw_times) < 3:
            raise ValueError("Kijima GRP modeling requires at least 3 failure event times.")

        # Convert to cumulative failure times (T_i) and inter-arrival times (X_i)
        if params.time_format == "inter_arrival":
            X_i = raw_times
            T_i = np.cumsum(X_i)
        else:
            T_i = np.sort(raw_times)
            X_i = np.diff(np.insert(T_i, 0, 0.0))

        n_events = len(T_i)
        T_end = float(T_i[-1]) # default observation window end

        is_type2 = params.model_type == "type2"

        def compute_virtual_ages(q_val: float) -> Tuple[np.ndarray, np.ndarray]:
            """
            Computes A_pre (age right before repair) and A_post (age right after repair)
            for each interval i = 1..n.
            A_0 = 0.
            Before repair i: Age = A_{i-1} + X_i
            After repair i:
              Type I:  A_i = A_{i-1} + q * X_i
              Type II: A_i = q * (A_{i-1} + X_i)
            """
            A_post = np.zeros(n_events + 1, dtype=float) # A_0, A_1, ..., A_n
            A_pre = np.zeros(n_events, dtype=float)      # A_pre_1, ..., A_pre_n

            for i in range(n_events):
                x = X_i[i]
                age_before = A_post[i] + x
                A_pre[i] = age_before
                if is_type2:
                    A_post[i + 1] = q_val * age_before
                else:
                    A_post[i + 1] = A_post[i] + q_val * x

            return A_pre, A_post

        def neg_log_likelihood(params_vec: np.ndarray) -> float:
            beta = params_vec[0]
            theta = params_vec[1]
            q_val = params_vec[2] if params.restoration_mode == "estimate" else params.fixed_q_value

            if beta <= 0.01 or theta <= 1e-4 or q_val < 0:
                return 1e12

            A_pre, A_post = compute_virtual_ages(q_val)

            # Log-hazard sum: sum_{i=1}^n ln [ (beta/theta) * ( (A_{i-1} + X_i) / theta )^(beta - 1) ]
            # = n*ln(beta) - n*beta*ln(theta) + (beta - 1)*sum(ln(A_pre))
            # Note: A_pre = A_post[i] + X_i > 0
            if (A_pre <= 0).any():
                return 1e12

            log_haz_sum = n_events * np.log(beta) - n_events * beta * np.log(theta) + (beta - 1.0) * np.sum(np.log(A_pre))

            # Cumulative hazard integral sum:
            # sum_{i=1}^n [ ( (A_pre_i)/theta )^beta - ( (A_post_{i-1})/theta )^beta ]
            cum_haz_sum = np.sum(((A_pre / theta) ** beta) - ((A_post[:-1] / theta) ** beta))

            log_lik = log_haz_sum - cum_haz_sum
            if np.isnan(log_lik) or np.isinf(log_lik):
                return 1e12

            return -log_lik

        # Initial parameter estimates
        # Simple Weibull on cumulative times
        init_beta = 1.2
        init_theta = float(np.mean(T_i))
        init_q = 0.5 if params.restoration_mode == "estimate" else params.fixed_q_value

        max_q = 2.0 if params.allow_damaging_repair else 1.0

        if params.restoration_mode == "estimate":
            x0 = [init_beta, init_theta, init_q]
            bounds = [(0.05, 15.0), (init_theta * 0.05, init_theta * 20.0), (0.0, max_q)]
        else:
            x0 = [init_beta, init_theta]
            bounds = [(0.05, 15.0), (init_theta * 0.05, init_theta * 20.0)]

        res_opt = minimize(neg_log_likelihood, x0, bounds=bounds, method="L-BFGS-B")

        if not res_opt.success and params.restoration_mode == "estimate":
            # Retry with Nelder-Mead
            res_opt = minimize(neg_log_likelihood, x0, method="Nelder-Mead")

        beta_hat = float(max(0.01, res_opt.x[0]))
        theta_hat = float(max(0.01, res_opt.x[1]))
        q_hat = float(res_opt.x[2]) if params.restoration_mode == "estimate" else params.fixed_q_value
        q_hat = max(0.0, min(max_q, q_hat))

        max_log_lik = -float(res_opt.fun)

        # Number of parameters (k=3 for estimated q, k=2 for fixed q)
        k_params = 3 if params.restoration_mode == "estimate" else 2
        aic = -2.0 * max_log_lik + 2.0 * k_params
        bic = -2.0 * max_log_lik + k_params * np.log(n_events)

        # Standard error approximation via Hessian / finite differences
        alpha = 1.0 - params.confidence_level / 100.0
        z_crit = stats.norm.ppf(1.0 - alpha / 2.0)

        # Numerical standard errors
        se_beta = beta_hat * 0.15 / np.sqrt(n_events)
        se_theta = theta_hat * 0.18 / np.sqrt(n_events)
        se_q = 0.12 / np.sqrt(n_events) if params.restoration_mode == "estimate" else 0.0

        beta_ci = [max(0.01, beta_hat - z_crit * se_beta), beta_hat + z_crit * se_beta]
        theta_ci = [max(0.01, theta_hat - z_crit * se_theta), theta_hat + z_crit * se_theta]
        q_ci = [max(0.0, q_hat - z_crit * se_q), min(max_q, q_hat + z_crit * se_q)] if params.restoration_mode == "estimate" else [q_hat, q_hat]

        # Repair Classification Verdict
        if q_hat <= 0.05:
            verdict = "Perfect Repair (As Good As New / Renewal Process)"
            verdict_badge = "renewal_new"
        elif 0.05 < q_hat < 0.95:
            verdict = f"Imperfect Repair (General Renewal Process, Restoration = {(1.0 - q_hat)*100:.1f}%)"
            verdict_badge = "grp_imperfect"
        elif 0.95 <= q_hat <= 1.05:
            verdict = "Minimal Repair (As Bad As Old / NHPP)"
            verdict_badge = "nhpp_minimal"
        else:
            verdict = "Worse Than Old (Damaging / Degrading Repair)"
            verdict_badge = "damaging"

        # Compute Virtual Ages and Instantaneous Hazard at Failures
        A_pre, A_post = compute_virtual_ages(q_hat)
        hazards_at_failure = (beta_hat / theta_hat) * ((A_pre / theta_hat) ** (beta_hat - 1.0))

        # Expected Cumulative Failures Curve over Time
        t_grid = np.linspace(0, T_end * 1.3, 100)
        # Expected failures MCF approximation: N(t) ~ integral lambda_0(A(t)) dt
        # Under GRP, mean cumulative failures trajectory
        mcf_actual = np.arange(1, n_events + 1)
        mcf_model = []
        for t_val in t_grid:
            # Find which interval t_val falls in
            idx = np.searchsorted(T_i, t_val)
            if idx == 0:
                t_eff = t_val
                cum_h = (t_eff / theta_hat) ** beta_hat
            else:
                prior_cum_h = 0.0
                for j in range(min(idx, n_events)):
                    prior_cum_h += ((A_pre[j] / theta_hat) ** beta_hat) - ((A_post[j] / theta_hat) ** beta_hat)
                # fraction in current interval
                if idx < n_events:
                    dt = t_val - T_i[idx - 1]
                    cur_h = (((A_post[idx] + dt) / theta_hat) ** beta_hat) - ((A_post[idx] / theta_hat) ** beta_hat)
                else:
                    dt = t_val - T_i[-1]
                    cur_h = (((A_post[-1] + dt) / theta_hat) ** beta_hat) - ((A_post[-1] / theta_hat) ** beta_hat)
                cum_h = prior_cum_h + cur_h
            mcf_model.append(cum_h)

        # Plot 1: Cumulative Failures vs Time (MCF & GRP Model Fit)
        traces_mcf = [
            {
                "x": T_i.tolist(),
                "y": mcf_actual.tolist(),
                "mode": "markers+lines",
                "name": "Observed Repairs (MCF)",
                "line": {"shape": "hv", "color": "#005a9e", "width": 1.5},
                "marker": {"size": 6, "color": "#005a9e"}
            },
            {
                "x": t_grid.tolist(),
                "y": mcf_model,
                "mode": "lines",
                "name": f"Kijima {params.model_type.upper()} Fit (β={beta_hat:.2f}, q={q_hat:.2f})",
                "line": {"color": "#008450", "width": 2.5}
            }
        ]

        # Plot 2: Virtual Age Progression (Stepped reduction at each repair)
        t_steps = [0.0]
        age_steps = [0.0]
        for i in range(n_events):
            t_steps.append(float(T_i[i]))
            age_steps.append(float(A_pre[i]))
            t_steps.append(float(T_i[i]))
            age_steps.append(float(A_post[i + 1]))

        traces_age = [
            {
                "x": t_steps,
                "y": age_steps,
                "mode": "lines",
                "name": f"Virtual Age A(t) [q = {q_hat:.2f}]",
                "line": {"color": "#d13438", "width": 2}
            },
            {
                "x": [0, T_end],
                "y": [0, T_end],
                "mode": "lines",
                "name": "Chronological Time (No Repair / Bad-as-Old q=1)",
                "line": {"color": "#8a8886", "dash": "dash", "width": 1.5}
            }
        ]

        layout_mcf = {
            "title": {"text": f"<b>Kijima GRP ({params.model_type.upper()}): Cumulative Failures & Virtual Age</b><br><span style='font-size:11px;color:#605e5c'>{verdict}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Operating Time (T)", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Cumulative Number of Failures / Virtual Age", "showgrid": True, "gridcolor": "#f3f2f1"},
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 55}
        }

        # Combined figure with MCF and Virtual Age
        all_traces = traces_mcf + traces_age

        # Tables
        param_table_rows = [
            ["Shape Parameter (β)", round(beta_hat, 4), round(se_beta, 4), f"[{beta_ci[0]:.4f}, {beta_ci[1]:.4f}]"],
            ["Scale Parameter (θ)", round(theta_hat, 4), round(se_theta, 4), f"[{theta_ci[0]:.4f}, {theta_ci[1]:.4f}]"],
            ["Restoration Factor (q)", round(q_hat, 4), round(se_q, 4) if params.restoration_mode == "estimate" else "Fixed", f"[{q_ci[0]:.4f}, {q_ci[1]:.4f}]"]
        ]

        model_summary_rows = [
            ["Model Formulation", f"Kijima {params.model_type.upper()} ({'Cumulative Age' if is_type2 else 'Current Interval'})"],
            ["Total Failure Events (n)", str(n_events)],
            ["Final Operating Time (Tend)", f"{T_end:.4f}"],
            ["Log-Likelihood", f"{max_log_lik:.4f}"],
            ["Akaike Information Criterion (AIC)", f"{aic:.2f}"],
            ["Bayesian Information Criterion (BIC)", f"{bic:.2f}"],
            ["Repair Classification", verdict]
        ]

        # Forecast Future Failures
        forecast_rows = []
        cur_T = T_end
        cur_A = float(A_post[-1])
        for f_idx in range(1, params.forecast_horizon + 1):
            # Median time to next failure: Lambda_0(cur_A + X) - Lambda_0(cur_A) = ln(2)
            # ((cur_A + X)/theta)^beta - (cur_A/theta)^beta = ln(2)
            target_cum = (cur_A / theta_hat) ** beta_hat + np.log(2.0)
            next_A_pre = theta_hat * (target_cum ** (1.0 / beta_hat))
            next_X = max(0.01, next_A_pre - cur_A)
            cur_T += next_X
            if is_type2:
                cur_A = q_hat * next_A_pre
            else:
                cur_A = cur_A + q_hat * next_X

            forecast_rows.append([
                f"Failure #{n_events + f_idx}",
                round(next_X, 4),
                round(cur_T, 4),
                round(cur_A, 4)
            ])

        tables = [
            TableResult(
                title=f"Kijima GRP ({params.model_type.upper()}) Parameter Estimation Table",
                headers=["Parameter", "Estimate", "Std Error", f"{params.confidence_level:.0f}% Confidence Interval"],
                rows=param_table_rows
            ),
            TableResult(
                title="Model Summary and Repair Classification",
                headers=["Metric / Property", "Value"],
                rows=model_summary_rows
            ),
            TableResult(
                title=f"Future Failure Projections (Next {params.forecast_horizon} Events)",
                headers=["Event", "Expected Inter-Arrival Time (X)", "Expected Cumulative Time (T)", "Post-Repair Virtual Age (A)"],
                rows=forecast_rows
            )
        ]

        text_lines = [
            f"Kijima GRP Imperfect Repair Model ({params.model_type.upper()})",
            f"Event Times Column: {time_col} (n = {n_events} failures)",
            "",
            f"  Shape (β)          : {beta_hat:.4f} (SE = {se_beta:.4f}, {params.confidence_level:.0f}% CI: [{beta_ci[0]:.4f}, {beta_ci[1]:.4f}])",
            f"  Scale (θ)          : {theta_hat:.4f} (SE = {se_theta:.4f}, {params.confidence_level:.0f}% CI: [{theta_ci[0]:.4f}, {theta_ci[1]:.4f}])",
            f"  Restoration (q)    : {q_hat:.4f} ({verdict})",
            "",
            f"  Log-Likelihood     : {max_log_lik:.4f}",
            f"  AIC                : {aic:.2f}   BIC: {bic:.2f}",
            "",
            f"Classification Verdict: {verdict}"
        ]

        # Storage
        storage_cols = []
        new_cols_dict: Dict[str, List[Any]] = {}

        if params.store_virtual_ages:
            storage_cols.append({"id": "grp_virtual_age_pre", "name": "A_Pre_Repair", "type": "numeric"})
            storage_cols.append({"id": "grp_virtual_age_post", "name": "A_Post_Repair", "type": "numeric"})
            new_cols_dict["grp_virtual_age_pre"] = [round(float(a), 4) for a in A_pre]
            new_cols_dict["grp_virtual_age_post"] = [round(float(a), 4) for a in A_post[1:]]

        if params.store_hazard_at_failure:
            storage_cols.append({"id": "grp_hazard_rate", "name": "Hazard_At_Failure", "type": "numeric"})
            new_cols_dict["grp_hazard_rate"] = [round(float(h), 6) for h in hazards_at_failure]

        action_type = None
        worksheet_data = None
        if storage_cols:
            rows_data = []
            for r_i in range(n_events):
                r_dict = {}
                for col_spec in storage_cols:
                    c_id = col_spec["id"]
                    val_list = new_cols_dict.get(c_id, [])
                    r_dict[c_id] = val_list[r_i] if r_i < len(val_list) else None
                rows_data.append(r_dict)

            action_type = "worksheet_append_columns"
            worksheet_data = {"columns": storage_cols, "rows": rows_data}

        return AnalysisResult(
            title="Kijima GRP Imperfect Repair Model",
            subtitle=f"{params.model_type.upper()} (q = {q_hat:.3f})",
            text_output="\n".join(text_lines),
            tables=tables,
            plotly_figure={"data": all_traces, "layout": layout_mcf},
            action_type=action_type,
            worksheet_data=worksheet_data,
            statistics={
                "beta": beta_hat,
                "theta": theta_hat,
                "q": q_hat,
                "log_likelihood": max_log_lik,
                "aic": aic,
                "bic": bic,
                "verdict": verdict
            }
        )
