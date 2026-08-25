import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class OneSampleZParams(BaseModel):
    sample_col: str = Field(
        ...,
        description="Sample Data Column",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    known_sigma: float = Field(
        ...,
        description="Known standard deviation (sigma > 0)",
        json_schema_extra={"ui_type": "number"}
    )
    perform_test: bool = Field(
        True,
        description="Perform hypothesis test",
        json_schema_extra={"ui_type": "checkbox"}
    )
    hypothesized_mean: float = Field(
        0.0,
        description="Hypothesized mean (mu_0)",
        json_schema_extra={"ui_type": "number"}
    )
    alternative: str = Field(
        "two_sided",
        description="Alternative Hypothesis",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "mean != hypothesized mean (two-sided)", "value": "two_sided"},
                {"label": "mean < hypothesized mean (less than)", "value": "less"},
                {"label": "mean > hypothesized mean (greater than)", "value": "greater"},
            ]
        }
    )
    confidence_level: float = Field(
        95.0,
        description="Confidence level (%)",
        json_schema_extra={"ui_type": "number"}
    )


class OneSampleZPlugin(AnalysisPlugin):
    id = "one_sample_z"
    name = "1-Sample Z"
    menu_path = ["Stat", "Basic Statistics", "1-Sample Z"]
    description = "Performs a 1-Sample Z hypothesis test and confidence interval for the mean with known population standard deviation."
    param_schema = OneSampleZParams

    def execute(self, df: pd.DataFrame, params: OneSampleZParams) -> AnalysisResult:
        if params.sample_col not in df.columns:
            raise ValueError(f"Column '{params.sample_col}' not found in active worksheet.")

        if params.known_sigma <= 0:
            raise ValueError("Known standard deviation (sigma) must be strictly greater than 0.")

        series = pd.to_numeric(df[params.sample_col], errors="coerce").dropna().to_numpy(dtype=float)
        n = len(series)
        if n < 1:
            raise ValueError(f"1-Sample Z requires at least 1 valid data value.")

        mean_val = float(np.mean(series))
        sigma = float(params.known_sigma)
        se_mean = float(sigma / np.sqrt(n))

        conf = params.confidence_level / 100.0
        alpha = 1.0 - conf

        # Confidence Interval
        if params.alternative == "two_sided":
            z_crit = stats.norm.ppf(1.0 - alpha / 2.0)
            ci_low = mean_val - z_crit * se_mean
            ci_high = mean_val + z_crit * se_mean
            ci_str = f"({ci_low:.4f}, {ci_high:.4f})"
        elif params.alternative == "less":
            z_crit = stats.norm.ppf(1.0 - alpha)
            ci_low = -np.inf
            ci_high = mean_val + z_crit * se_mean
            ci_str = f"(-Inf, {ci_high:.4f})"
        else:  # greater
            z_crit = stats.norm.ppf(1.0 - alpha)
            ci_low = mean_val - z_crit * se_mean
            ci_high = np.inf
            ci_str = f"({ci_low:.4f}, Inf)"

        # Hypothesis Test
        z_stat = (mean_val - params.hypothesized_mean) / se_mean
        if params.alternative == "two_sided":
            p_val = 2.0 * (1.0 - stats.norm.cdf(abs(z_stat)))
            alt_sym = "≠"
        elif params.alternative == "less":
            p_val = stats.norm.cdf(z_stat)
            alt_sym = "<"
        else:
            p_val = 1.0 - stats.norm.cdf(z_stat)
            alt_sym = ">"

        p_val = min(max(float(p_val), 0.0), 1.0)

        # Tables
        desc_headers = ["Sample", "N", "Mean", "Known StDev", "SE Mean", f"{params.confidence_level}% CI"]
        desc_rows = [[params.sample_col, n, f"{mean_val:.4f}", f"{sigma:.4f}", f"{se_mean:.4f}", ci_str]]

        test_headers = ["Null hypothesis", "Alternative hypothesis", "Z-Value", "P-Value"]
        test_rows = [
            [f"H₀: μ = {params.hypothesized_mean}", f"H₁: μ {alt_sym} {params.hypothesized_mean}", f"{z_stat:.2f}", f"{p_val:.4f}"]
        ]

        text_lines = [
            f"One-Sample Z: {params.sample_col}",
            "",
            f"Descriptive Statistics (Known standard deviation = {sigma})",
            f"  {'Sample':<12} {'N':>5} {'Mean':>10} {'SE Mean':>10} {f'{params.confidence_level}% CI':>25}",
            f"  {'-'*12} {'-'*5} {'-'*10} {'-'*10} {'-'*25}",
            f"  {params.sample_col:<12} {n:>5} {mean_val:>10.4f} {se_mean:>10.4f} {ci_str:>25}",
            "",
            "Test",
            f"  Null hypothesis:         H₀: μ = {params.hypothesized_mean}",
            f"  Alternative hypothesis:  H₁: μ {alt_sym} {params.hypothesized_mean}",
            f"  Z-Value: {z_stat:.2f}",
            f"  P-Value: {p_val:.4f}",
        ]

        # Plot: Individual Values + Mean & CI + Hypothesized Mean Reference Line
        plot_data = [
            {
                "type": "scatter",
                "x": np.random.normal(1.0, 0.04, size=n).tolist(),
                "y": series.tolist(),
                "mode": "markers",
                "name": "Data Points",
                "marker": {"color": "rgba(100, 116, 139, 0.6)", "size": 7},
                "hoverinfo": "y",
            },
            {
                "type": "scatter",
                "x": [1.0],
                "y": [mean_val],
                "error_y": {
                    "type": "data",
                    "symmetric": True,
                    "array": [z_crit * se_mean],
                    "color": "#1e40af",
                    "thickness": 2.5,
                    "width": 12,
                },
                "mode": "markers",
                "name": f"Sample Mean ({params.confidence_level}% CI)",
                "marker": {"color": "#1e40af", "size": 10, "symbol": "square"},
            }
        ]

        layout = {
            "title": {"text": f"<b>Individual Value Plot of {params.sample_col}</b><br><span style='font-size:12px;color:#64748b;'>with {params.confidence_level}% CI and H₀ (μ₀={params.hypothesized_mean})</span>", "x": 0.5},
            "showlegend": True,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 400,
            "xaxis": {"showticklabels": False, "showgrid": False, "range": [0.7, 1.3]},
            "yaxis": {"title": {"text": params.sample_col}, "showgrid": True, "gridcolor": "#ececec"},
            "shapes": [
                {
                    "type": "line",
                    "xref": "paper",
                    "x0": 0,
                    "x1": 1,
                    "y0": params.hypothesized_mean,
                    "y1": params.hypothesized_mean,
                    "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"},
                }
            ],
            "annotations": [
                {
                    "xref": "paper",
                    "x": 0.02,
                    "y": params.hypothesized_mean,
                    "text": f"H₀: μ₀ = {params.hypothesized_mean}",
                    "showarrow": False,
                    "font": {"color": "#dc2626", "size": 11},
                    "bgcolor": "#ffffff",
                }
            ]
        }

        return AnalysisResult(
            title="1-Sample Z",
            subtitle=f"{params.sample_col} (σ={sigma})",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title="Descriptive Statistics", headers=desc_headers, rows=desc_rows),
                TableResult(title="Hypothesis Test", headers=test_headers, rows=test_rows)
            ],
            statistics={"z_stat": z_stat, "p_value": p_val, "mean": mean_val, "se_mean": se_mean, "ci": [ci_low, ci_high]},
            plotly_figure={"data": plot_data, "layout": layout}
        )
