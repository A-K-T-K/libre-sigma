"""
Stepwise / Best Subsets Regression Plugin for OpenMinitab.
Performs automated subset selection for multiple linear regression models using Stepwise, Forward Selection, Backward Elimination, and Best Subsets algorithms.
Computes Step-by-Step Selection Logs, Mallows' Cp, AIC, BIC, Adjusted R-Square, and Final Model ANOVA & Coefficient Tables.
"""

from typing import Any, Dict, List, Optional
import itertools
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class StepwiseRegressionParams(BaseModel):
    response: str = Field(
        ...,
        description="Response Variable (Continuous Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    predictors: List[str] = Field(
        ...,
        description="Candidate Predictors (X)",
        json_schema_extra={"ui_type": "column_multi_picker", "data_type": "numeric"}
    )
    method: str = Field(
        "stepwise",
        description="Selection Method",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Stepwise (Forward and Backward)", "value": "stepwise"},
                {"label": "Forward Selection", "value": "forward"},
                {"label": "Backward Elimination", "value": "backward"},
                {"label": "Best Subsets", "value": "best_subsets"}
            ]
        }
    )
    alpha_enter: float = Field(
        0.15,
        ge=0.001,
        le=0.50,
        description="Alpha to Enter (α_enter, Default: 0.15)",
        json_schema_extra={"sub_modal": "Criteria..."}
    )
    alpha_remove: float = Field(
        0.15,
        ge=0.001,
        le=0.50,
        description="Alpha to Remove (α_remove, Default: 0.15)",
        json_schema_extra={"sub_modal": "Criteria..."}
    )
    force_in: Optional[List[str]] = Field(
        None,
        description="Predictors to Force In (Always Retained)",
        json_schema_extra={"ui_type": "column_multi_picker", "sub_modal": "Criteria..."}
    )


class StepwiseRegressionPlugin(AnalysisPlugin):
    id = "regression_stepwise"
    name = "Stepwise / Best Subsets Regression"
    menu_path = ["Stat", "Regression", "Fit Regression Model", "Stepwise / Best Subsets"]
    description = "Automated variable selection for regression using Stepwise, Forward, Backward, or Best Subsets algorithms."
    param_schema = StepwiseRegressionParams

    def execute(self, df: pd.DataFrame, params: StepwiseRegressionParams) -> AnalysisResult:
        y_col = params.response
        cand_x = params.predictors

        if not cand_x:
            raise ValueError("Select at least one candidate predictor variable.")

        all_cols = [y_col] + cand_x
        sub_df = df[all_cols].dropna().copy()
        for c in all_cols:
            sub_df[c] = pd.to_numeric(sub_df[c], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n_obs = len(sub_df)
        if n_obs < len(cand_x) + 2:
            raise ValueError(f"Stepwise regression requires at least {len(cand_x) + 2} valid observations.")

        y_data = sub_df[y_col].to_numpy(dtype=float)

        # Full model MSE for Mallows' Cp: Cp = (SSE_p / MSE_full) - (n - 2*(p + 1))
        X_full = sm.add_constant(sub_df[cand_x].to_numpy(dtype=float))
        full_model = sm.OLS(y_data, X_full).fit()
        mse_full = max(1e-8, full_model.mse_resid)

        method = params.method
        alpha_in = params.alpha_enter
        alpha_out = params.alpha_remove
        forced = params.force_in or []
        forced = [f for f in forced if f in cand_x]

        selected_vars: List[str] = list(forced)
        step_log: List[List[Any]] = []
        step_idx = 1

        def eval_subset(var_list: List[str]) -> Dict[str, Any]:
            if not var_list:
                X_mat = np.ones((n_obs, 1))
                p_count = 0
            else:
                X_mat = sm.add_constant(sub_df[var_list].to_numpy(dtype=float))
                p_count = len(var_list)

            mod = sm.OLS(y_data, X_mat).fit()
            sse = float(mod.ssr)
            r2 = float(mod.rsquared) if var_list else 0.0
            r2_adj = float(mod.rsquared_adj) if var_list else 0.0
            s_val = float(np.sqrt(mod.mse_resid))
            cp_val = (sse / mse_full) - (n_obs - 2 * (p_count + 1))
            aic_val = float(mod.aic)
            bic_val = float(mod.bic)
            return {
                "model": mod,
                "r2": r2,
                "r2_adj": r2_adj,
                "s": s_val,
                "cp": cp_val,
                "aic": aic_val,
                "bic": bic_val,
                "p_count": p_count
            }

        # Algorithm Execution
        if method == "best_subsets":
            # Evaluate all combinations from size 1 up to min(len(cand_x), 6)
            best_models = []
            max_size = min(len(cand_x), 6)
            for k_size in range(1, max_size + 1):
                best_k_eval = None
                best_k_vars = []
                for combo in itertools.combinations(cand_x, k_size):
                    eval_res = eval_subset(list(combo))
                    if best_k_eval is None or eval_res["r2_adj"] > best_k_eval["r2_adj"]:
                        best_k_eval = eval_res
                        best_k_vars = list(combo)

                best_models.append((k_size, best_k_vars, best_k_eval))

            for k_size, k_vars, k_eval in best_models:
                step_log.append([
                    step_idx,
                    k_size,
                    round(k_eval["r2"] * 100.0, 2),
                    round(k_eval["r2_adj"] * 100.0, 2),
                    round(k_eval["cp"], 2),
                    round(k_eval["s"], 4),
                    ", ".join(k_vars)
                ])
                step_idx += 1

            # Best subset is the one with highest R2-adj
            selected_vars = max(best_models, key=lambda item: item[2]["r2_adj"])[1]

        else: # Stepwise, Forward, Backward
            if method == "backward":
                selected_vars = list(cand_x)

            max_steps = 2 * len(cand_x) + 5
            for _ in range(max_steps):
                action_taken = False

                # Forward / Stepwise Step: Try adding best candidate variable
                if method in ["stepwise", "forward"]:
                    remaining_vars = [v for v in cand_x if v not in selected_vars]
                    best_cand = None
                    best_pval = 1.0

                    for cand in remaining_vars:
                        test_vars = selected_vars + [cand]
                        eval_res = eval_subset(test_vars)
                        # p-value of candidate is the last coefficient
                        cand_p = float(eval_res["model"].pvalues[-1])
                        if cand_p < best_pval:
                            best_pval = cand_p
                            best_cand = cand

                    if best_cand and best_pval < alpha_in:
                        selected_vars.append(best_cand)
                        eval_cur = eval_subset(selected_vars)
                        step_log.append([
                            step_idx,
                            f"Entered: {best_cand}",
                            round(best_pval, 4),
                            round(eval_cur["r2"] * 100.0, 2),
                            round(eval_cur["r2_adj"] * 100.0, 2),
                            round(eval_cur["cp"], 2),
                            round(eval_cur["s"], 4),
                            ", ".join(selected_vars)
                        ])
                        step_idx += 1
                        action_taken = True

                # Backward / Stepwise Step: Try removing worst variable
                if method in ["stepwise", "backward"] and len(selected_vars) > len(forced):
                    eval_cur = eval_subset(selected_vars)
                    mod = eval_cur["model"]
                    pvals = mod.pvalues[1:] # ignore constant

                    worst_idx = int(np.argmax(pvals))
                    worst_pval = float(pvals[worst_idx])
                    worst_var = selected_vars[worst_idx]

                    if worst_var not in forced and worst_pval > alpha_out:
                        selected_vars.remove(worst_var)
                        eval_cur = eval_subset(selected_vars)
                        step_log.append([
                            step_idx,
                            f"Removed: {worst_var}",
                            round(worst_pval, 4),
                            round(eval_cur["r2"] * 100.0, 2),
                            round(eval_cur["r2_adj"] * 100.0, 2),
                            round(eval_cur["cp"], 2),
                            round(eval_cur["s"], 4),
                            ", ".join(selected_vars) if selected_vars else "(None)"
                        ])
                        step_idx += 1
                        action_taken = True

                if not action_taken:
                    break

        if not selected_vars:
            selected_vars = [cand_x[0]]

        # Fit Final Model
        final_eval = eval_subset(selected_vars)
        final_model = final_eval["model"]

        # Coefficient Table
        coef_rows = []
        X_final_mat = sm.add_constant(sub_df[selected_vars].to_numpy(dtype=float))
        terms = ["Constant"] + selected_vars

        for idx_t, term_name in enumerate(terms):
            c_val = float(final_model.params[idx_t])
            se_val = float(final_model.bse[idx_t])
            t_val = float(final_model.tvalues[idx_t])
            p_val = float(final_model.pvalues[idx_t])

            vif_str = ""
            if idx_t > 0 and len(selected_vars) > 1:
                try:
                    vif_val = variance_inflation_factor(X_final_mat, idx_t)
                    vif_str = f"{vif_val:.2f}"
                except Exception:
                    vif_str = "1.00"

            coef_rows.append([term_name, round(c_val, 4), round(se_val, 4), round(t_val, 2), round(p_val, 4), vif_str])

        # ANOVA Table
        ss_reg = float(final_model.ess)
        df_reg = len(selected_vars)
        ms_reg = ss_reg / df_reg if df_reg > 0 else 0.0

        ss_err = float(final_model.ssr)
        df_err = int(final_model.df_resid)
        ms_err = ss_err / df_err if df_err > 0 else 0.0

        f_stat = float(final_model.fvalue)
        p_f = float(final_model.f_pvalue)

        ss_tot = ss_reg + ss_err
        df_tot = df_reg + df_err

        anova_rows = [
            ["Regression", df_reg, round(ss_reg, 4), round(ms_reg, 4), round(f_stat, 2), round(p_f, 4)],
            ["Residual Error", df_err, round(ss_err, 4), round(ms_err, 4), "", ""],
            ["Total", df_tot, round(ss_tot, 4), "", "", ""]
        ]

        # Stepwise Log Table Headers
        if method == "best_subsets":
            log_headers = ["Step", "Vars (k)", "R-Sq (%)", "R-Sq(adj) (%)", "Mallows Cp", "S", "Included Variables"]
        else:
            log_headers = ["Step", "Action", "P-Value", "R-Sq (%)", "R-Sq(adj) (%)", "Mallows Cp", "S", "Included Variables"]

        # Selection Trajectory Plot (R-Sq(adj) vs Step)
        step_nums = [r[0] for r in step_log]
        r2_adj_vals = [r[3] if method == "best_subsets" else r[4] for r in step_log]
        cp_vals = [r[4] if method == "best_subsets" else r[5] for r in step_log]

        traces = [
            {
                "x": step_nums,
                "y": r2_adj_vals,
                "mode": "lines+markers",
                "name": "Adjusted R-Square (%)",
                "line": {"color": "#008450", "width": 2},
                "marker": {"size": 7}
            },
            {
                "x": step_nums,
                "y": cp_vals,
                "mode": "lines+markers",
                "name": "Mallows' Cp",
                "yaxis": "y2",
                "line": {"color": "#005a9e", "width": 2, "dash": "dash"},
                "marker": {"size": 7}
            }
        ]

        layout = {
            "title": {"text": f"<b>Stepwise Selection Trajectory ({params.method.capitalize()} Method)</b><br><span style='font-size:11px;color:#605e5c'>Final Model: {y_col} ~ {' + '.join(selected_vars)} (R-Sq(adj) = {final_eval['r2_adj']*100:.2f}%)</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Step Number", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Adjusted R-Square (%)", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis2": {"title": "Mallows' Cp", "overlaying": "y", "side": "right", "showgrid": False},
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 60, "t": 60, "b": 55}
        }

        tables = [
            TableResult(title=f"Stepwise Selection Log ({params.method.capitalize()})", headers=log_headers, rows=step_log),
            TableResult(title=f"Final Model Coefficients (Response: {y_col})", headers=["Term", "Coef", "SE Coef", "T-Value", "P-Value", "VIF"], rows=coef_rows),
            TableResult(title="Analysis of Variance (ANOVA)", headers=["Source", "DF", "Adj SS", "Adj MS", "F-Value", "P-Value"], rows=anova_rows)
        ]

        text_lines = [
            f"Stepwise Regression: {y_col} versus {', '.join(cand_x)}",
            f"Method: {params.method.capitalize()} (α_enter = {alpha_in}, α_remove = {alpha_out})",
            "",
            "Final Selected Variables: " + ", ".join(selected_vars),
            f"S = {final_eval['s']:.4f}   R-Sq = {final_eval['r2']*100:.2f}%   R-Sq(adj) = {final_eval['r2_adj']*100:.2f}%   Mallows Cp = {final_eval['cp']:.2f}",
            "",
            f"  {'Term':<18} {'Coef':>10} {'SE Coef':>10} {'T-Value':>8} {'P-Value':>8} {'VIF':>6}",
            f"  {'-'*18} {'-'*10} {'-'*10} {'-'*8} {'-'*8} {'-'*6}",
        ]
        for r in coef_rows:
            text_lines.append(f"  {r[0]:<18} {r[1]:>10.4f} {r[2]:>10.4f} {r[3]:>8.2f} {r[4]:>8.4f} {str(r[5]):>6}")

        return AnalysisResult(
            title="Stepwise / Best Subsets Regression",
            subtitle=f"Final Model: {y_col} ~ {' + '.join(selected_vars)}",
            text_output="\n".join(text_lines),
            tables=tables,
            plotly_figure={"data": traces, "layout": layout},
            statistics={
                "selected_variables": selected_vars,
                "r_squared": final_eval["r2"],
                "r_squared_adj": final_eval["r2_adj"],
                "s": final_eval["s"],
                "mallows_cp": final_eval["cp"]
            }
        )
