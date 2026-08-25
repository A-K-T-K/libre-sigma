import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class OneVarianceParams(BaseModel):
    sample_col: str = Field(
        ...,
        description="Sample Data Column",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    target_type: str = Field(
        "stdev",
        description="Perform test for",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Standard deviation (sigma)", "value": "stdev"},
                {"label": "Variance (sigma squared)", "value": "variance"},
            ]
        }
    )
    hypothesized_value: float = Field(
        1.0,
        description="Hypothesized value (sigma_0 or sigma_0^2 > 0)",
        json_schema_extra={"ui_type": "number"}
    )
    alternative: str = Field(
        "two_sided",
        description="Alternative Hypothesis",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "value != hypothesized value (two-sided)", "value": "two_sided"},
                {"label": "value < hypothesized value (less than)", "value": "less"},
                {"label": "value > hypothesized value (greater than)", "value": "greater"},
            ]
        }
    )
    confidence_level: float = Field(
        95.0,
        description="Confidence level (%)",
        json_schema_extra={"ui_type": "number"}
    )


class OneVariancePlugin(AnalysisPlugin):
    id = "one_variance"
    name = "1 Variance"
    menu_path = ["Stat", "Basic Statistics", "1 Variance"]
    description = "Tests for a population standard deviation or variance using Chi-Square and Bonett tests."
    param_schema = OneVarianceParams

    def execute(self, df: pd.DataFrame, params: OneVarianceParams) -> AnalysisResult:
        if params.sample_col not in df.columns:
            raise ValueError(f"Column '{params.sample_col}' not found in active worksheet.")

        series = pd.to_numeric(df[params.sample_col], errors="coerce").dropna().to_numpy(dtype=float)
        n = len(series)
        if n < 3:
            raise ValueError(f"1 Variance requires at least 3 valid observations (found {n}).")

        stdev_val = float(np.std(series, ddof=1))
        var_val = float(np.var(series, ddof=1))
        df_deg = n - 1

        hyp_val = float(params.hypothesized_value)
        if hyp_val <= 0:
            raise ValueError("Hypothesized value must be strictly greater than 0.")

        sigma0_sq = hyp_val ** 2 if params.target_type == "stdev" else hyp_val
        sigma0 = hyp_val if params.target_type == "stdev" else np.sqrt(hyp_val)

        conf = params.confidence_level / 100.0
        alpha = 1.0 - conf

        # Chi-Square Test Statistic: (n - 1) * s^2 / sigma0^2
        chi2_stat = (df_deg * var_val) / sigma0_sq if sigma0_sq > 0 else 0.0

        if params.alternative == "two_sided":
            p_left = stats.chi2.cdf(chi2_stat, df=df_deg)
            p_right = 1.0 - stats.chi2.cdf(chi2_stat, df=df_deg)
            p_val_chi2 = min(1.0, 2.0 * min(p_left, p_right))
            alt_sym = "≠"
            chi2_low_crit = stats.chi2.ppf(1.0 - alpha / 2.0, df=df_deg)
            chi2_high_crit = stats.chi2.ppf(alpha / 2.0, df=df_deg)
            var_ci_low = (df_deg * var_val) / chi2_low_crit if chi2_low_crit > 0 else 0.0
            var_ci_high = (df_deg * var_val) / chi2_high_crit if chi2_high_crit > 0 else np.inf
        elif params.alternative == "less":
            p_val_chi2 = stats.chi2.cdf(chi2_stat, df=df_deg)
            alt_sym = "<"
            chi2_low_crit = stats.chi2.ppf(1.0 - alpha, df=df_deg)
            var_ci_low = 0.0
            var_ci_high = (df_deg * var_val) / chi2_low_crit if chi2_low_crit > 0 else np.inf
        else:  # greater
            p_val_chi2 = 1.0 - stats.chi2.cdf(chi2_stat, df=df_deg)
            alt_sym = ">"
            chi2_high_crit = stats.chi2.ppf(alpha, df=df_deg)
            var_ci_low = (df_deg * var_val) / chi2_high_crit if chi2_high_crit > 0 else 0.0
            var_ci_high = np.inf

        stdev_ci_low = np.sqrt(var_ci_low) if var_ci_low >= 0 else 0.0
        stdev_ci_high = np.sqrt(var_ci_high) if var_ci_high < np.inf else np.inf

        # Bonett's approximation for continuous data
        gamma = stats.kurtosis(series, bias=False) if n > 3 else 0.0
        c_bonett = (n - 1) / (n - 1 + max(0, gamma))
        z_crit = stats.norm.ppf(1.0 - alpha / 2.0)
        bonett_se = np.sqrt((2.0 / df_deg) * (1.0 + (gamma / 2.0)))
        bonett_log_ci_low = np.log(stdev_val) - z_crit * bonett_se
        bonett_log_ci_high = np.log(stdev_val) + z_crit * bonett_se
        bonett_sd_ci = (np.exp(bonett_log_ci_low), np.exp(bonett_log_ci_high))

        # Output strings
        if params.target_type == "stdev":
            ci_chi2_str = f"({stdev_ci_low:.4f}, {stdev_ci_high:.4f})"
            bonett_str = f"({bonett_sd_ci[0]:.4f}, {bonett_sd_ci[1]:.4f})"
            sample_val_str = f"{stdev_val:.4f}"
            hyp_str = f"σ = {sigma0:.4f}"
            test_target_name = "Standard Deviation"
        else:
            ci_chi2_str = f"({var_ci_low:.4f}, {var_ci_high:.4f})"
            bonett_str = f"({bonett_sd_ci[0]**2:.4f}, {bonett_sd_ci[1]**2:.4f})"
            sample_val_str = f"{var_val:.4f}"
            hyp_str = f"σ² = {sigma0_sq:.4f}"
            test_target_name = "Variance"

        # Tables
        desc_headers = ["Sample", "N", "StDev", "Variance", f"{params.confidence_level}% CI (Chi-Square)", f"{params.confidence_level}% CI (Bonett)"]
        desc_rows = [[params.sample_col, n, f"{stdev_val:.4f}", f"{var_val:.4f}", ci_chi2_str, bonett_str]]

        test_headers = ["Method", "Null hypothesis", "Alternative hypothesis", "Test Statistic", "DF", "P-Value"]
        test_rows = [
            ["Chi-Square", f"H₀: {hyp_str}", f"H₁: {hyp_str.replace('=', alt_sym)}", f"{chi2_stat:.2f}", str(df_deg), f"{p_val_chi2:.4f}"]
        ]

        text_lines = [
            f"Test and CI for One {test_target_name}: {params.sample_col}",
            "",
            "Descriptive Statistics",
            f"  {'Sample':<12} {'N':>5} {'StDev':>10} {'Variance':>10} {f'{params.confidence_level}% CI (Chi-Square)':>25}",
            f"  {'-'*12} {'-'*5} {'-'*10} {'-'*10} {'-'*25}",
            f"  {params.sample_col:<12} {n:>5} {stdev_val:>10.4f} {var_val:>10.4f} {ci_chi2_str:>25}",
            "",
            f"Bonett's Method {params.confidence_level}% CI: {bonett_str}",
            "",
            "Test",
            f"  Null hypothesis:         H₀: {hyp_str}",
            f"  Alternative hypothesis:  H₁: {hyp_str.replace('=', alt_sym)}",
            f"  Method       Test Statistic  DF  P-Value",
            f"  Chi-Square   {chi2_stat:>14.2f}  {df_deg:>3}  {p_val_chi2:.4f}",
        ]

        # Plot: Standard Deviation with CI and H0
        target_pt = stdev_val if params.target_type == "stdev" else var_val
        target_ci_low = stdev_ci_low if params.target_type == "stdev" else var_ci_low
        target_ci_high = stdev_ci_high if params.target_type == "stdev" else var_ci_high
        target_hyp = sigma0 if params.target_type == "stdev" else sigma0_sq

        plot_data = [
            {
                "type": "scatter",
                "x": [params.sample_col],
                "y": [target_pt],
                "error_y": {
                    "type": "data",
                    "symmetric": False,
                    "array": [target_ci_high - target_pt],
                    "arrayminus": [target_pt - target_ci_low],
                    "color": "#1e40af",
                    "thickness": 2.5,
                    "width": 12,
                },
                "mode": "markers",
                "name": f"Sample {test_target_name}",
                "marker": {"color": "#1e40af", "size": 10, "symbol": "circle"},
            }
        ]

        layout = {
            "title": {"text": f"<b>1 {test_target_name} Plot of {params.sample_col} (with {params.confidence_level}% CI)</b>", "x": 0.5},
            "showlegend": False,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 400,
            "yaxis": {"title": {"text": test_target_name}, "showgrid": True, "gridcolor": "#ececec"},
            "shapes": [
                {
                    "type": "line",
                    "xref": "paper",
                    "x0": 0,
                    "x1": 1,
                    "y0": target_hyp,
                    "y1": target_hyp,
                    "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"},
                }
            ],
            "annotations": [
                {
                    "xref": "paper",
                    "x": 0.02,
                    "y": target_hyp,
                    "text": f"H₀: {hyp_str}",
                    "showarrow": False,
                    "font": {"color": "#dc2626", "size": 11},
                    "bgcolor": "#ffffff",
                }
            ]
        }

        return AnalysisResult(
            title="1 Variance",
            subtitle=f"{params.sample_col} ({hyp_str})",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title="Descriptive Statistics", headers=desc_headers, rows=desc_rows),
                TableResult(title="Test Results", headers=test_headers, rows=test_rows)
            ],
            statistics={"stdev": stdev_val, "variance": var_val, "chi2_stat": chi2_stat, "df": df_deg, "p_value": p_val_chi2, "ci_chi2": [target_ci_low, target_ci_high]},
            plotly_figure={"data": plot_data, "layout": layout}
        )
