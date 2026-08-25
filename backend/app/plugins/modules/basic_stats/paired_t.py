import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class PairedTParams(BaseModel):
    sample1_col: str = Field(
        ...,
        description="First sample column (Sample 1)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    sample2_col: str = Field(
        ...,
        description="Second sample column (Sample 2)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    hypothesized_diff: float = Field(
        0.0,
        description="Hypothesized mean difference (mu_d)",
        json_schema_extra={"ui_type": "number"}
    )
    alternative: str = Field(
        "two_sided",
        description="Alternative Hypothesis",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "mean diff != hypothesized diff (two-sided)", "value": "two_sided"},
                {"label": "mean diff < hypothesized diff (less than)", "value": "less"},
                {"label": "mean diff > hypothesized diff (greater than)", "value": "greater"},
            ]
        }
    )
    confidence_level: float = Field(
        95.0,
        description="Confidence level (%)",
        json_schema_extra={"ui_type": "number"}
    )


class PairedTPlugin(AnalysisPlugin):
    id = "paired_t"
    name = "Paired t"
    menu_path = ["Stat", "Basic Statistics", "Paired t"]
    description = "Performs a paired t-test and confidence interval to compare two dependent/matched samples."
    param_schema = PairedTParams

    def execute(self, df: pd.DataFrame, params: PairedTParams) -> AnalysisResult:
        if params.sample1_col not in df.columns or params.sample2_col not in df.columns:
            raise ValueError("Selected paired columns not found in active worksheet.")

        sub_df = df[[params.sample1_col, params.sample2_col]].copy()
        sub_df[params.sample1_col] = pd.to_numeric(sub_df[params.sample1_col], errors="coerce")
        sub_df[params.sample2_col] = pd.to_numeric(sub_df[params.sample2_col], errors="coerce")
        clean_df = sub_df.dropna()

        n = len(clean_df)
        if n < 2:
            raise ValueError(f"Paired t-test requires at least 2 complete paired observations (found {n}).")

        s1 = clean_df[params.sample1_col].to_numpy(dtype=float)
        s2 = clean_df[params.sample2_col].to_numpy(dtype=float)
        diff = s1 - s2

        m1, m2 = float(np.mean(s1)), float(np.mean(s2))
        sd1, sd2 = float(np.std(s1, ddof=1)), float(np.std(s2, ddof=1))
        se1, se2 = float(sd1 / np.sqrt(n)), float(sd2 / np.sqrt(n))

        m_diff = float(np.mean(diff))
        sd_diff = float(np.std(diff, ddof=1))
        se_diff = float(sd_diff / np.sqrt(n))
        df_deg = n - 1

        conf = params.confidence_level / 100.0
        alpha = 1.0 - conf

        # Confidence Interval
        if params.alternative == "two_sided":
            t_crit = stats.t.ppf(1.0 - alpha / 2.0, df=df_deg)
            ci_low = m_diff - t_crit * se_diff
            ci_high = m_diff + t_crit * se_diff
            ci_str = f"({ci_low:.4f}, {ci_high:.4f})"
        elif params.alternative == "less":
            t_crit = stats.t.ppf(1.0 - alpha, df=df_deg)
            ci_low = -np.inf
            ci_high = m_diff + t_crit * se_diff
            ci_str = f"(-Inf, {ci_high:.4f})"
        else:
            t_crit = stats.t.ppf(1.0 - alpha, df=df_deg)
            ci_low = m_diff - t_crit * se_diff
            ci_high = np.inf
            ci_str = f"({ci_low:.4f}, Inf)"

        # Hypothesis Test
        t_stat = (m_diff - params.hypothesized_diff) / se_diff if se_diff > 0 else 0.0
        if params.alternative == "two_sided":
            p_val = 2.0 * (1.0 - stats.t.cdf(abs(t_stat), df=df_deg))
            alt_sym = "≠"
        elif params.alternative == "less":
            p_val = stats.t.cdf(t_stat, df=df_deg)
            alt_sym = "<"
        else:
            p_val = 1.0 - stats.t.cdf(t_stat, df=df_deg)
            alt_sym = ">"

        p_val = min(max(float(p_val), 0.0), 1.0)

        # Tables
        desc_headers = ["Sample", "N", "Mean", "StDev", "SE Mean"]
        desc_rows = [
            [params.sample1_col, n, f"{m1:.4f}", f"{sd1:.4f}", f"{se1:.4f}"],
            [params.sample2_col, n, f"{m2:.4f}", f"{sd2:.4f}", f"{se2:.4f}"],
            ["Difference", n, f"{m_diff:.4f}", f"{sd_diff:.4f}", f"{se_diff:.4f}"]
        ]

        est_headers = ["Mean Difference", f"{params.confidence_level}% CI for Mean Difference"]
        est_rows = [[f"{m_diff:.4f}", ci_str]]

        test_headers = ["Null hypothesis", "Alternative hypothesis", "T-Value", "DF", "P-Value"]
        test_rows = [
            [f"H₀: μ_d = {params.hypothesized_diff}", f"H₁: μ_d {alt_sym} {params.hypothesized_diff}", f"{t_stat:.2f}", str(df_deg), f"{p_val:.4f}"]
        ]

        text_lines = [
            f"Paired T-Test and CI: {params.sample1_col}, {params.sample2_col}",
            "",
            "Descriptive Statistics",
            f"  {'Sample':<15} {'N':>5} {'Mean':>10} {'StDev':>10} {'SE Mean':>10}",
            f"  {'-'*15} {'-'*5} {'-'*10} {'-'*10} {'-'*10}",
            f"  {params.sample1_col:<15} {n:>5} {m1:>10.4f} {sd1:>10.4f} {se1:>10.4f}",
            f"  {params.sample2_col:<15} {n:>5} {m2:>10.4f} {sd2:>10.4f} {se2:>10.4f}",
            f"  {'Difference':<15} {n:>5} {m_diff:>10.4f} {sd_diff:>10.4f} {se_diff:>10.4f}",
            "",
            f"Estimation for Paired Difference: {m_diff:.4f}",
            f"{params.confidence_level}% CI for Mean Difference: {ci_str}",
            "",
            "Test",
            f"  Null hypothesis:         H₀: μ_d = {params.hypothesized_diff}",
            f"  Alternative hypothesis:  H₁: μ_d {alt_sym} {params.hypothesized_diff}",
            f"  T-Value: {t_stat:.2f}    DF: {df_deg}    P-Value: {p_val:.4f}",
        ]

        # Plot: Histogram of Differences with normal curve
        x_min, x_max = min(diff), max(diff)
        x_span = max(0.1, x_max - x_min)
        x_curve = np.linspace(x_min - 0.1 * x_span, x_max + 0.1 * x_span, 100)
        y_curve = stats.norm.pdf(x_curve, m_diff, sd_diff) if sd_diff > 0 else np.zeros(100)

        plot_data = [
            {
                "type": "histogram",
                "x": diff.tolist(),
                "name": "Differences",
                "histnorm": "probability density",
                "marker": {"color": "rgba(99, 102, 241, 0.7)", "line": {"color": "#4f46e5", "width": 1}},
            },
            {
                "type": "scatter",
                "x": x_curve.tolist(),
                "y": y_curve.tolist(),
                "mode": "lines",
                "name": "Normal Fit",
                "line": {"color": "#dc2626", "width": 2},
            }
        ]

        layout = {
            "title": {"text": f"<b>Histogram of Differences ({params.sample1_col} - {params.sample2_col})</b>", "x": 0.5},
            "showlegend": True,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 400,
            "xaxis": {"title": {"text": "Difference"}, "showgrid": True, "gridcolor": "#ececec"},
            "yaxis": {"title": {"text": "Density"}, "showgrid": True, "gridcolor": "#ececec"},
            "shapes": [
                {
                    "type": "line",
                    "x0": params.hypothesized_diff,
                    "x1": params.hypothesized_diff,
                    "yref": "paper",
                    "y0": 0,
                    "y1": 1,
                    "line": {"color": "#16a34a", "width": 1.5, "dash": "dash"},
                }
            ],
            "annotations": [
                {
                    "x": params.hypothesized_diff,
                    "yref": "paper",
                    "y": 0.95,
                    "text": f"H₀: {params.hypothesized_diff}",
                    "showarrow": False,
                    "font": {"color": "#16a34a", "size": 11},
                    "bgcolor": "#ffffff",
                }
            ]
        }

        return AnalysisResult(
            title="Paired t",
            subtitle=f"{params.sample1_col} vs {params.sample2_col}",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title="Descriptive Statistics", headers=desc_headers, rows=desc_rows),
                TableResult(title="Estimation for Paired Difference", headers=est_headers, rows=est_rows),
                TableResult(title="Hypothesis Test", headers=test_headers, rows=test_rows)
            ],
            statistics={"m_diff": m_diff, "sd_diff": sd_diff, "t_stat": t_stat, "df": df_deg, "p_value": p_val, "ci": [ci_low, ci_high]},
            plotly_figure={"data": plot_data, "layout": layout}
        )
