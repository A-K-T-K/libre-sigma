import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class TwoVariancesParams(BaseModel):
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
    target_type: str = Field(
        "stdev_ratio",
        description="Perform test for",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Ratio of standard deviations (sigma1 / sigma2)", "value": "stdev_ratio"},
                {"label": "Ratio of variances (sigma1^2 / sigma2^2)", "value": "variance_ratio"},
            ]
        }
    )
    hypothesized_ratio: float = Field(
        1.0,
        description="Hypothesized ratio (> 0)",
        json_schema_extra={"ui_type": "number"}
    )
    alternative: str = Field(
        "two_sided",
        description="Alternative Hypothesis",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "ratio != hypothesized ratio (two-sided)", "value": "two_sided"},
                {"label": "ratio < hypothesized ratio (less than)", "value": "less"},
                {"label": "ratio > hypothesized ratio (greater than)", "value": "greater"},
            ]
        }
    )
    confidence_level: float = Field(
        95.0,
        description="Confidence level (%)",
        json_schema_extra={"ui_type": "number"}
    )


class TwoVariancesPlugin(AnalysisPlugin):
    id = "two_variances"
    name = "2 Variances"
    menu_path = ["Stat", "Basic Statistics", "2 Variances"]
    description = "Tests for equality of two variances or standard deviations using F-Test, Levene's Test, and Bonett's method."
    param_schema = TwoVariancesParams

    def execute(self, df: pd.DataFrame, params: TwoVariancesParams) -> AnalysisResult:
        if params.sample1_col not in df.columns or params.sample2_col not in df.columns:
            raise ValueError("Selected columns not found in active worksheet.")

        s1 = pd.to_numeric(df[params.sample1_col], errors="coerce").dropna().to_numpy(dtype=float)
        s2 = pd.to_numeric(df[params.sample2_col], errors="coerce").dropna().to_numpy(dtype=float)

        n1, n2 = len(s1), len(s2)
        if n1 < 2 or n2 < 2:
            raise ValueError(f"2 Variances requires at least 2 data points in each sample (found n1={n1}, n2={n2}).")

        sd1, sd2 = float(np.std(s1, ddof=1)), float(np.std(s2, ddof=1))
        var1, var2 = sd1 ** 2, sd2 ** 2
        df1, df2 = n1 - 1, n2 - 1

        sample_sd_ratio = (sd1 / sd2) if sd2 > 0 else np.nan
        sample_var_ratio = (var1 / var2) if var2 > 0 else np.nan

        ratio0 = float(params.hypothesized_ratio)
        if ratio0 <= 0:
            raise ValueError("Hypothesized ratio must be strictly greater than 0.")

        conf = params.confidence_level / 100.0
        alpha = 1.0 - conf

        # 1. F-Test (Normal distribution assumption)
        f_stat = sample_var_ratio / (ratio0 ** 2 if params.target_type == "stdev_ratio" else ratio0)

        if params.alternative == "two_sided":
            p_left = stats.f.cdf(f_stat, df1, df2)
            p_right = 1.0 - stats.f.cdf(f_stat, df1, df2)
            p_val_f = min(1.0, 2.0 * min(p_left, p_right))
            alt_sym = "≠"
            f_low_crit = stats.f.ppf(1.0 - alpha / 2.0, df1, df2)
            f_high_crit = stats.f.ppf(alpha / 2.0, df1, df2)
            ci_var_low = sample_var_ratio / f_low_crit if f_low_crit > 0 else 0.0
            ci_var_high = sample_var_ratio / f_high_crit if f_high_crit > 0 else np.inf
        elif params.alternative == "less":
            p_val_f = stats.f.cdf(f_stat, df1, df2)
            alt_sym = "<"
            f_low_crit = stats.f.ppf(1.0 - alpha, df1, df2)
            ci_var_low = 0.0
            ci_var_high = sample_var_ratio / f_low_crit if f_low_crit > 0 else np.inf
        else:  # greater
            p_val_f = 1.0 - stats.f.cdf(f_stat, df1, df2)
            alt_sym = ">"
            f_high_crit = stats.f.ppf(alpha, df1, df2)
            ci_var_low = sample_var_ratio / f_high_crit if f_high_crit > 0 else 0.0
            ci_var_high = np.inf

        ci_sd_low = np.sqrt(ci_var_low) if ci_var_low >= 0 else 0.0
        ci_sd_high = np.sqrt(ci_var_high) if ci_var_high < np.inf else np.inf

        # 2. Levene's Test (Non-normal data)
        lev_res = stats.levene(s1, s2, center="median")
        lev_stat = float(lev_res.statistic)
        p_val_levene = float(lev_res.pvalue)

        # 3. Bonett's Method
        gamma1 = stats.kurtosis(s1, bias=False) if n1 > 3 else 0.0
        gamma2 = stats.kurtosis(s2, bias=False) if n2 > 3 else 0.0
        se_bonett = np.sqrt((2.0 / df1) * (1.0 + gamma1 / 2.0) + (2.0 / df2) * (1.0 + gamma2 / 2.0))
        z_crit = stats.norm.ppf(1.0 - alpha / 2.0)
        bonett_sd_ci_low = sample_sd_ratio * np.exp(-z_crit * se_bonett)
        bonett_sd_ci_high = sample_sd_ratio * np.exp(z_crit * se_bonett)

        if params.target_type == "stdev_ratio":
            est_val = sample_sd_ratio
            ci_f_str = f"({ci_sd_low:.4f}, {ci_sd_high:.4f})"
            ci_bonett_str = f"({bonett_sd_ci_low:.4f}, {bonett_sd_ci_high:.4f})"
            hyp_str = f"σ₁ / σ₂ = {ratio0:.4f}"
            metric_label = "Standard Deviation Ratio"
        else:
            est_val = sample_var_ratio
            ci_f_str = f"({ci_var_low:.4f}, {ci_var_high:.4f})"
            ci_bonett_str = f"({bonett_sd_ci_low**2:.4f}, {bonett_sd_ci_high**2:.4f})"
            hyp_str = f"σ₁² / σ₂² = {ratio0:.4f}"
            metric_label = "Variance Ratio"

        # Tables
        desc_headers = ["Sample", "N", "StDev", "Variance"]
        desc_rows = [
            [params.sample1_col, n1, f"{sd1:.4f}", f"{var1:.4f}"],
            [params.sample2_col, n2, f"{sd2:.4f}", f"{var2:.4f}"],
        ]

        est_headers = ["Ratio", "Estimate", f"{params.confidence_level}% CI (F-Test)", f"{params.confidence_level}% CI (Bonett)"]
        est_rows = [[metric_label, f"{est_val:.4f}", ci_f_str, ci_bonett_str]]

        test_headers = ["Method", "DF1", "DF2", "Statistic", "P-Value"]
        test_rows = [
            ["F-Test (Normal)", str(df1), str(df2), f"{f_stat:.2f}", f"{p_val_f:.4f}"],
            ["Levene's Test (Any continuous)", "1", str(n1 + n2 - 2), f"{lev_stat:.2f}", f"{p_val_levene:.4f}"],
        ]

        text_lines = [
            f"Test and CI for Two Variances: {params.sample1_col}, {params.sample2_col}",
            "",
            "Descriptive Statistics",
            f"  {'Sample':<12} {'N':>5} {'StDev':>10} {'Variance':>10}",
            f"  {'-'*12} {'-'*5} {'-'*10} {'-'*10}",
            f"  {params.sample1_col:<12} {n1:>5} {sd1:>10.4f} {var1:>10.4f}",
            f"  {params.sample2_col:<12} {n2:>5} {sd2:>10.4f} {var2:>10.4f}",
            "",
            f"Estimation for Ratio: {est_val:.4f}",
            f"{params.confidence_level}% CI (F-Test): {ci_f_str}",
            f"{params.confidence_level}% CI (Bonett): {ci_bonett_str}",
            "",
            "Test",
            f"  Null hypothesis:         H₀: {hyp_str}",
            f"  Alternative hypothesis:  H₁: {hyp_str.replace('=', alt_sym)}",
            f"  Method                           Statistic  P-Value",
            f"  F-Test (Normal)                  {f_stat:>9.2f}  {p_val_f:.4f}",
            f"  Levene's Test (Continuous)       {lev_stat:>9.2f}  {p_val_levene:.4f}",
        ]

        # Plot: Side-by-Side Boxplots
        plot_data = [
            {
                "type": "box",
                "y": s1.tolist(),
                "name": f"{params.sample1_col} (s={sd1:.3f})",
                "marker": {"color": "#3b82f6"},
                "boxpoints": "all",
            },
            {
                "type": "box",
                "y": s2.tolist(),
                "name": f"{params.sample2_col} (s={sd2:.3f})",
                "marker": {"color": "#10b981"},
                "boxpoints": "all",
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
            title="2 Variances",
            subtitle=f"{params.sample1_col} vs {params.sample2_col}",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title="Descriptive Statistics", headers=desc_headers, rows=desc_rows),
                TableResult(title="Ratio Estimation", headers=est_headers, rows=est_rows),
                TableResult(title="Hypothesis Test Results", headers=test_headers, rows=test_rows)
            ],
            statistics={"f_stat": f_stat, "p_val_f": p_val_f, "levene_stat": lev_stat, "p_val_levene": p_val_levene, "ratio_est": est_val},
            plotly_figure={"data": plot_data, "layout": layout}
        )
