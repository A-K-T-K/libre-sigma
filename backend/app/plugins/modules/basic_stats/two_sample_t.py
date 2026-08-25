import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class TwoSampleTParams(BaseModel):
    sample1_col: str = Field(
        ...,
        description="Sample 1 Column",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    sample2_col: str = Field(
        ...,
        description="Sample 2 Column",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    assume_equal_variances: bool = Field(
        False,
        description="Assume equal variances (Pooled StDev)",
        json_schema_extra={"ui_type": "checkbox"}
    )
    hypothesized_diff: float = Field(
        0.0,
        description="Hypothesized difference (mu1 - mu2)",
        json_schema_extra={"ui_type": "number"}
    )
    alternative: str = Field(
        "two_sided",
        description="Alternative Hypothesis",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "diff != hypothesized diff (two-sided)", "value": "two_sided"},
                {"label": "diff < hypothesized diff (less than)", "value": "less"},
                {"label": "diff > hypothesized diff (greater than)", "value": "greater"},
            ]
        }
    )
    confidence_level: float = Field(
        95.0,
        description="Confidence level (%)",
        json_schema_extra={"ui_type": "number"}
    )


class TwoSampleTPlugin(AnalysisPlugin):
    id = "two_sample_t"
    name = "2-Sample t"
    menu_path = ["Stat", "Basic Statistics", "2-Sample t"]
    description = "Performs an independent two-sample t-test (Welch or Pooled) and confidence interval to compare two population means."
    param_schema = TwoSampleTParams

    def execute(self, df: pd.DataFrame, params: TwoSampleTParams) -> AnalysisResult:
        if params.sample1_col not in df.columns or params.sample2_col not in df.columns:
            raise ValueError(f"Selected columns not found in active worksheet.")

        s1 = pd.to_numeric(df[params.sample1_col], errors="coerce").dropna().to_numpy(dtype=float)
        s2 = pd.to_numeric(df[params.sample2_col], errors="coerce").dropna().to_numpy(dtype=float)

        n1, n2 = len(s1), len(s2)
        if n1 < 2 or n2 < 2:
            raise ValueError(f"2-Sample t requires at least 2 observations in each sample (found n1={n1}, n2={n2}).")

        m1, m2 = float(np.mean(s1)), float(np.mean(s2))
        sd1, sd2 = float(np.std(s1, ddof=1)), float(np.std(s2, ddof=1))
        v1, v2 = sd1 ** 2, sd2 ** 2
        se1, se2 = float(sd1 / np.sqrt(n1)), float(sd2 / np.sqrt(n2))

        diff_est = m1 - m2
        conf = params.confidence_level / 100.0
        alpha = 1.0 - conf

        if params.assume_equal_variances:
            sp2 = ((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2)
            sp = np.sqrt(sp2)
            se_diff = float(sp * np.sqrt(1.0 / n1 + 1.0 / n2))
            df_deg = n1 + n2 - 2
        else:
            se_diff = float(np.sqrt(v1 / n1 + v2 / n2))
            # Welch-Satterthwaite approximation
            df_num = (v1 / n1 + v2 / n2) ** 2
            df_den = ((v1 / n1) ** 2) / (n1 - 1) + ((v2 / n2) ** 2) / (n2 - 1)
            df_deg = df_num / df_den if df_den > 0 else (n1 + n2 - 2)

        # CI for Difference
        if params.alternative == "two_sided":
            t_crit = stats.t.ppf(1.0 - alpha / 2.0, df=df_deg)
            ci_low = diff_est - t_crit * se_diff
            ci_high = diff_est + t_crit * se_diff
            ci_str = f"({ci_low:.4f}, {ci_high:.4f})"
        elif params.alternative == "less":
            t_crit = stats.t.ppf(1.0 - alpha, df=df_deg)
            ci_low = -np.inf
            ci_high = diff_est + t_crit * se_diff
            ci_str = f"(-Inf, {ci_high:.4f})"
        else:
            t_crit = stats.t.ppf(1.0 - alpha, df=df_deg)
            ci_low = diff_est - t_crit * se_diff
            ci_high = np.inf
            ci_str = f"({ci_low:.4f}, Inf)"

        # Hypothesis Test
        t_stat = (diff_est - params.hypothesized_diff) / se_diff if se_diff > 0 else 0.0
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
            [params.sample1_col, n1, f"{m1:.4f}", f"{sd1:.4f}", f"{se1:.4f}"],
            [params.sample2_col, n2, f"{m2:.4f}", f"{sd2:.4f}", f"{se2:.4f}"]
        ]

        est_headers = ["Difference", "Estimate for Difference", f"{params.confidence_level}% CI for Difference"]
        est_rows = [[f"μ({params.sample1_col}) - μ({params.sample2_col})", f"{diff_est:.4f}", ci_str]]

        test_headers = ["Null hypothesis", "Alternative hypothesis", "T-Value", "DF", "P-Value"]
        test_rows = [
            [f"H₀: μ₁ - μ₂ = {params.hypothesized_diff}", f"H₁: μ₁ - μ₂ {alt_sym} {params.hypothesized_diff}", f"{t_stat:.2f}", f"{df_deg:.1f}", f"{p_val:.4f}"]
        ]

        text_lines = [
            f"Two-Sample T-Test and CI: {params.sample1_col}, {params.sample2_col}",
            "",
            "Descriptive Statistics",
            f"  {'Sample':<12} {'N':>5} {'Mean':>10} {'StDev':>10} {'SE Mean':>10}",
            f"  {'-'*12} {'-'*5} {'-'*10} {'-'*10} {'-'*10}",
            f"  {params.sample1_col:<12} {n1:>5} {m1:>10.4f} {sd1:>10.4f} {se1:>10.4f}",
            f"  {params.sample2_col:<12} {n2:>5} {m2:>10.4f} {sd2:>10.4f} {se2:>10.4f}",
            "",
            f"Estimation for Difference: {diff_est:.4f}",
            f"{params.confidence_level}% CI for Difference: {ci_str}",
            "",
            "Test",
            f"  Null hypothesis:         H₀: μ₁ - μ₂ = {params.hypothesized_diff}",
            f"  Alternative hypothesis:  H₁: μ₁ - μ₂ {alt_sym} {params.hypothesized_diff}",
            f"  T-Value: {t_stat:.2f}    DF: {df_deg:.1f}    P-Value: {p_val:.4f}",
        ]

        # Plot: Boxplots Side-by-Side
        plot_data = [
            {
                "type": "box",
                "y": s1.tolist(),
                "name": params.sample1_col,
                "boxpoints": "all",
                "jitter": 0.3,
                "pointpos": -1.8,
                "marker": {"color": "#1d4ed8"},
            },
            {
                "type": "box",
                "y": s2.tolist(),
                "name": params.sample2_col,
                "boxpoints": "all",
                "jitter": 0.3,
                "pointpos": -1.8,
                "marker": {"color": "#0d9488"},
            }
        ]

        layout = {
            "title": {"text": f"<b>Boxplot of {params.sample1_col}, {params.sample2_col}</b>", "x": 0.5},
            "showlegend": True,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 400,
            "yaxis": {"title": {"text": "Value"}, "showgrid": True, "gridcolor": "#ececec"},
        }

        return AnalysisResult(
            title="2-Sample t",
            subtitle=f"{params.sample1_col} vs {params.sample2_col}",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title="Descriptive Statistics", headers=desc_headers, rows=desc_rows),
                TableResult(title="Estimation for Difference", headers=est_headers, rows=est_rows),
                TableResult(title="Hypothesis Test", headers=test_headers, rows=test_rows)
            ],
            statistics={"diff_est": diff_est, "t_stat": t_stat, "df": df_deg, "p_value": p_val, "ci": [ci_low, ci_high]},
            plotly_figure={"data": plot_data, "layout": layout}
        )
