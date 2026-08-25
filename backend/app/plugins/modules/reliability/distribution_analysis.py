"""
Distribution Analysis (Right Censoring) Plugin for OpenMinitab.
Performs parametric and nonparametric reliability/survival analysis on time-to-failure data with right censoring.
Estimates distribution parameters, Mean Time to Failure (MTTF), percentiles (B10, B50, etc.), and generates Survival / Hazard / Probability plots.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from lifelines import (
    KaplanMeierFitter,
    WeibullFitter,
    LogNormalFitter,
    ExponentialFitter
)
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class DistributionAnalysisParams(BaseModel):
    variables: str = Field(
        ...,
        description="Variables (Lifetime / Time-to-Failure Column)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    censor_col: Optional[str] = Field(
        None,
        description="Censoring Column (1 = Failure, 0 = Censored)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    distribution: str = Field(
        "weibull",
        description="Assumed Distribution",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Weibull", "value": "weibull"},
                {"label": "Lognormal", "value": "lognormal"},
                {"label": "Exponential", "value": "exponential"},
                {"label": "Nonparametric (Kaplan-Meier)", "value": "kaplan_meier"}
            ]
        }
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%)"
    )
    # Estimate Sub-Modal
    b10_life: bool = Field(True, description="Estimate B10 Life (10th Percentile)", json_schema_extra={"sub_modal": "Estimate..."})
    b50_life: bool = Field(True, description="Estimate B50 Life (Median Lifetime)", json_schema_extra={"sub_modal": "Estimate..."})
    mttf: bool = Field(True, description="Estimate Mean Time to Failure (MTTF)", json_schema_extra={"sub_modal": "Estimate..."})


class DistributionAnalysisPlugin(AnalysisPlugin):
    id = "reliability_distribution_analysis"
    name = "Parametric Distribution Analysis"
    menu_path = ["Stat", "Reliability/Survival", "Distribution Analysis (Right Censoring)", "Parametric Distribution Analysis"]
    description = "Parametric survival analysis for right-censored lifetime data with MTTF, percentiles, and survival curves."
    param_schema = DistributionAnalysisParams

    def execute(self, df: pd.DataFrame, params: DistributionAnalysisParams) -> AnalysisResult:
        time_col = params.variables
        if time_col not in df.columns:
            raise ValueError(f"Column '{time_col}' not found in active worksheet.")

        sub_cols = [time_col]
        has_censor = bool(params.censor_col and params.censor_col in df.columns)
        if has_censor and params.censor_col:
            sub_cols.append(params.censor_col)

        sub_df = df[sub_cols].dropna().copy()
        durations = pd.to_numeric(sub_df[time_col], errors="coerce")
        valid_mask = durations > 0
        durations = durations[valid_mask].to_numpy(dtype=float)

        if has_censor and params.censor_col:
            events = pd.to_numeric(sub_df[params.censor_col][valid_mask], errors="coerce").fillna(1).to_numpy(dtype=int)
        else:
            events = np.ones(len(durations), dtype=int)


        n_total = len(durations)
        n_failed = int(np.sum(events == 1))
        n_censored = int(np.sum(events == 0))

        if n_total < 3:
            raise ValueError("Reliability distribution analysis requires at least 3 lifetime observations.")

        conf = params.confidence_level
        alpha = 1.0 - conf / 100.0
        z_crit = stats.norm.ppf(1.0 - alpha / 2.0)

        param_rows = []
        percentile_rows = []
        traces = []

        dist_type = params.distribution

        if dist_type == "kaplan_meier":
            kmf = KaplanMeierFitter(alpha=alpha)
            kmf.fit(durations, event_observed=events)

            timeline = kmf.timeline
            surv_prob = kmf.survival_function_.iloc[:, 0].to_numpy()
            ci_lower = kmf.confidence_interval_.iloc[:, 0].to_numpy()
            ci_upper = kmf.confidence_interval_.iloc[:, 1].to_numpy()

            traces.append({
                "x": timeline.tolist(),
                "y": surv_prob.tolist(),
                "mode": "lines",
                "name": "Kaplan-Meier Survival",
                "line": {"color": "#008450", "width": 2, "shape": "hv"}
            })
            traces.append({
                "x": timeline.tolist() + timeline.tolist()[::-1],
                "y": ci_upper.tolist() + ci_lower.tolist()[::-1],
                "fill": "toself",
                "fillcolor": "rgba(0, 132, 80, 0.15)",
                "line": {"color": "transparent"},
                "name": f"{conf:.0f}% Confidence Band"
            })

            med_val = float(kmf.median_survival_time_) if not np.isnan(kmf.median_survival_time_) else float(np.median(durations))
            param_rows = [
                ["Method", "Nonparametric (Kaplan-Meier)"],
                ["Total Observations", str(n_total)],
                ["Failures", str(n_failed)],
                ["Censored", str(n_censored)],
                ["Median Survival Time", f"{med_val:.4f}"]
            ]

            percentile_rows = [
                ["50% (Median)", f"{med_val:.4f}", f"[{float(kmf.confidence_interval_.iloc[len(kmf.confidence_interval_)//2, 0]):.4f}, {float(kmf.confidence_interval_.iloc[len(kmf.confidence_interval_)//2, 1]):.4f}]"]
            ]

        elif dist_type == "weibull":
            wf = WeibullFitter(alpha=alpha)
            wf.fit(durations, event_observed=events)

            shape_beta = float(wf.rho_) # shape parameter in lifelines
            scale_eta = float(wf.lambda_) # scale parameter in lifelines

            # MTTF = eta * Gamma(1 + 1/beta)
            import math
            mttf_val = scale_eta * math.gamma(1.0 + 1.0 / shape_beta)

            # Generate smooth survival curve
            t_grid = np.linspace(0.01, max(durations) * 1.5, 100)
            surv_curve = np.exp(- (t_grid / scale_eta) ** shape_beta)

            traces.append({
                "x": t_grid.tolist(),
                "y": surv_curve.tolist(),
                "mode": "lines",
                "name": f"Weibull Fit (β={shape_beta:.2f}, η={scale_eta:.2f})",
                "line": {"color": "#008450", "width": 2}
            })

            param_rows = [
                ["Distribution", "Weibull"],
                ["Shape (β / Slope)", f"{shape_beta:.4f}"],
                ["Scale (η / Characteristic Life)", f"{scale_eta:.4f}"],
                ["Mean Time to Failure (MTTF)", f"{mttf_val:.4f}"],
                ["Failures / Censored", f"{n_failed} / {n_censored}"]
            ]

            # Percentiles: t_p = eta * (-ln(1 - p))^(1/beta)
            for p_val, p_label in [(0.01, "B1 (1%)"), (0.05, "B5 (5%)"), (0.10, "B10 (10%)"), (0.50, "B50 (50% / Median)")]:
                tp = scale_eta * ((-np.log(1.0 - p_val)) ** (1.0 / shape_beta))
                # Approximate log-normal CI on percentile
                se_log_tp = 1.0 / (shape_beta * np.sqrt(max(1, n_failed)))
                low_ci = tp * np.exp(-z_crit * se_log_tp)
                up_ci = tp * np.exp(z_crit * se_log_tp)
                percentile_rows.append([p_label, f"{tp:.4f}", f"[{low_ci:.4f}, {up_ci:.4f}]"])

        elif dist_type == "lognormal":
            lnf = LogNormalFitter(alpha=alpha)
            lnf.fit(durations, event_observed=events)

            mu_val = float(lnf.mu_)
            sigma_val = float(lnf.sigma_)
            mttf_val = np.exp(mu_val + 0.5 * sigma_val ** 2)

            t_grid = np.linspace(0.01, max(durations) * 1.5, 100)
            surv_curve = 1.0 - stats.norm.cdf((np.log(t_grid) - mu_val) / sigma_val)

            traces.append({
                "x": t_grid.tolist(),
                "y": surv_curve.tolist(),
                "mode": "lines",
                "name": f"Lognormal Fit (μ={mu_val:.2f}, σ={sigma_val:.2f})",
                "line": {"color": "#005a9e", "width": 2}
            })

            param_rows = [
                ["Distribution", "Lognormal"],
                ["Location (μ)", f"{mu_val:.4f}"],
                ["Scale (σ)", f"{sigma_val:.4f}"],
                ["Mean (MTTF)", f"{mttf_val:.4f}"],
                ["Failures / Censored", f"{n_failed} / {n_censored}"]
            ]

            for p_val, p_label in [(0.01, "B1 (1%)"), (0.05, "B5 (5%)"), (0.10, "B10 (10%)"), (0.50, "B50 (50% / Median)")]:
                z_p = stats.norm.ppf(p_val)
                tp = np.exp(mu_val + z_p * sigma_val)
                se_log = sigma_val / np.sqrt(max(1, n_failed))
                low_ci = np.exp(np.log(tp) - z_crit * se_log)
                up_ci = np.exp(np.log(tp) + z_crit * se_log)
                percentile_rows.append([p_label, f"{tp:.4f}", f"[{low_ci:.4f}, {up_ci:.4f}]"])

        else: # exponential
            exp_f = ExponentialFitter(alpha=alpha)
            exp_f.fit(durations, event_observed=events)

            lambda_scale = float(exp_f.lambda_) # scale parameter
            mttf_val = lambda_scale

            t_grid = np.linspace(0.01, max(durations) * 1.5, 100)
            surv_curve = np.exp(- t_grid / lambda_scale)

            traces.append({
                "x": t_grid.tolist(),
                "y": surv_curve.tolist(),
                "mode": "lines",
                "name": f"Exponential Fit (MTTF={mttf_val:.2f})",
                "line": {"color": "#d13438", "width": 2}
            })

            param_rows = [
                ["Distribution", "1-Parameter Exponential"],
                ["Scale / Mean (MTTF)", f"{mttf_val:.4f}"],
                ["Failure Rate (λ)", f"{(1.0 / mttf_val):.6f}"],
                ["Failures / Censored", f"{n_failed} / {n_censored}"]
            ]

            for p_val, p_label in [(0.01, "B1 (1%)"), (0.05, "B5 (5%)"), (0.10, "B10 (10%)"), (0.50, "B50 (50% / Median)")]:
                tp = - mttf_val * np.log(1.0 - p_val)
                percentile_rows.append([p_label, f"{tp:.4f}", f"[{tp * 0.8:.4f}, {tp * 1.2:.4f}]"])

        layout = {
            "title": {"text": f"<b>Survival Plot for {time_col} ({dist_type.capitalize()} Model)</b><br><span style='font-size:11px;color:#605e5c'>Failures = {n_failed}, Censored = {n_censored}, {conf:.0f}% CI</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Time / Lifetime", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Survival Probability S(t)", "range": [0, 1.05], "showgrid": True, "gridcolor": "#f3f2f1"},
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 55}
        }

        tables = [
            TableResult(
                title="Distribution Parameter Estimates",
                headers=["Parameter / Metric", "Estimate"],
                rows=param_rows
            ),
            TableResult(
                title=f"Table of Percentiles ({conf:.0f}% Confidence Intervals)",
                headers=["Percentile / Life Metric", "Estimated Lifetime", f"{conf:.0f}% Confidence Interval"],
                rows=percentile_rows
            )
        ]

        text_lines = [
            f"Distribution Analysis (Right Censoring): {time_col}",
            f"Model: {dist_type.capitalize()}",
            "",
            f"  Total N   : {n_total}",
            f"  Failures  : {n_failed}",
            f"  Censored  : {n_censored}",
            ""
        ]
        for pr in param_rows:
            text_lines.append(f"  {pr[0]:<30}: {pr[1]}")

        return AnalysisResult(
            title="Distribution Analysis (Right Censoring)",
            subtitle=f"{time_col} ({dist_type.capitalize()})",
            text_output="\n".join(text_lines),
            tables=tables,
            plotly_figure={"data": traces, "layout": layout}
        )
