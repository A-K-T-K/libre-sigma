import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class OneSamplePoissonRateParams(BaseModel):
    data_mode: str = Field(
        "raw",
        description="Data Format",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Column of event counts", "value": "raw"},
                {"label": "Summarized data (Total occurrences & Sample size/time)", "value": "summarized"},
            ]
        }
    )
    sample_col: Optional[str] = Field(
        None,
        description="Event Count Column (for raw data)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    total_occurrences: Optional[int] = Field(
        None,
        description="Total Occurrences (X)",
        json_schema_extra={"ui_type": "number"}
    )
    total_sample_size: Optional[float] = Field(
        1.0,
        description="Total Sample Size / Observation Units (T)",
        json_schema_extra={"ui_type": "number"}
    )
    hypothesized_rate: float = Field(
        1.0,
        description="Hypothesized rate (lambda_0 > 0)",
        json_schema_extra={"ui_type": "number"}
    )
    alternative: str = Field(
        "two_sided",
        description="Alternative Hypothesis",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "rate != hypothesized rate (two-sided)", "value": "two_sided"},
                {"label": "rate < hypothesized rate (less than)", "value": "less"},
                {"label": "rate > hypothesized rate (greater than)", "value": "greater"},
            ]
        }
    )
    confidence_level: float = Field(
        95.0,
        description="Confidence level (%)",
        json_schema_extra={"ui_type": "number"}
    )


class OneSamplePoissonRatePlugin(AnalysisPlugin):
    id = "one_sample_poisson_rate"
    name = "1-Sample Poisson Rate"
    menu_path = ["Stat", "Basic Statistics", "1-Sample Poisson Rate"]
    description = "Tests for a population Poisson rate parameter and computes exact Garwood confidence intervals."
    param_schema = OneSamplePoissonRateParams

    def execute(self, df: pd.DataFrame, params: OneSamplePoissonRateParams) -> AnalysisResult:
        if params.data_mode == "raw":
            if not params.sample_col or params.sample_col not in df.columns:
                raise ValueError("Select a valid count column for raw data mode.")
            counts = pd.to_numeric(df[params.sample_col], errors="coerce").dropna().to_numpy(dtype=float)
            if len(counts) == 0:
                raise ValueError("Column contains no valid numeric counts.")
            x = int(np.sum(counts))
            t = float(len(counts))
        else:
            if params.total_occurrences is None or params.total_sample_size is None:
                raise ValueError("Please provide Total Occurrences and Total Sample Size.")
            x = int(params.total_occurrences)
            t = float(params.total_sample_size)
            if x < 0 or t <= 0:
                raise ValueError("Occurrences must be >= 0 and Sample Size must be > 0.")

        rate_est = float(x / t)
        lam0 = float(params.hypothesized_rate)
        if lam0 <= 0:
            raise ValueError("Hypothesized rate must be strictly greater than 0.")

        conf = params.confidence_level / 100.0
        alpha = 1.0 - conf

        # Exact Poisson Confidence Interval (Garwood Chi-Square method)
        if x == 0:
            ci_low = 0.0
        else:
            ci_low = float(0.5 * stats.chi2.ppf(alpha / 2.0, df=2 * x) / t)
        ci_high = float(0.5 * stats.chi2.ppf(1.0 - alpha / 2.0, df=2 * (x + 1)) / t)
        ci_str = f"({ci_low:.4f}, {ci_high:.4f})"

        # Exact Test P-Value
        exp_counts = lam0 * t
        if params.alternative == "less":
            p_val_exact = stats.poisson.cdf(x, exp_counts)
            alt_sym = "<"
        elif params.alternative == "greater":
            p_val_exact = 1.0 - stats.poisson.cdf(x - 1, exp_counts) if x > 0 else 1.0
            alt_sym = ">"
        else:  # two-sided
            p_left = stats.poisson.cdf(x, exp_counts)
            p_right = 1.0 - stats.poisson.cdf(x - 1, exp_counts) if x > 0 else 1.0
            p_val_exact = min(1.0, 2.0 * min(p_left, p_right))
            alt_sym = "≠"

        # Normal Approximation
        z_stat = (rate_est - lam0) / np.sqrt(lam0 / t)
        if params.alternative == "two_sided":
            p_val_norm = 2.0 * (1.0 - stats.norm.cdf(abs(z_stat)))
        elif params.alternative == "less":
            p_val_norm = stats.norm.cdf(z_stat)
        else:
            p_val_norm = 1.0 - stats.norm.cdf(z_stat)

        # Tables
        desc_headers = ["Sample", "Total Occurrences (X)", "Total Sample Size (T)", "Rate per Unit", f"{params.confidence_level}% Exact CI"]
        desc_rows = [["Sample 1", x, f"{t:.1f}", f"{rate_est:.4f}", ci_str]]

        test_headers = ["Method", "Null hypothesis", "Alternative hypothesis", "Z-Value", "P-Value"]
        test_rows = [
            ["Exact", f"H₀: Rate = {lam0}", f"H₁: Rate {alt_sym} {lam0}", "—", f"{p_val_exact:.4f}"],
            ["Normal approximation", f"H₀: Rate = {lam0}", f"H₁: Rate {alt_sym} {lam0}", f"{z_stat:.2f}", f"{p_val_norm:.4f}"],
        ]

        text_lines = [
            "Test and CI for One-Sample Poisson Rate",
            "",
            "Descriptive Statistics",
            f"  {'Sample':<12} {'X':>6} {'T':>8} {'Rate':>10} {f'{params.confidence_level}% Exact CI':>25}",
            f"  {'-'*12} {'-'*6} {'-'*8} {'-'*10} {'-'*25}",
            f"  {'Sample 1':<12} {x:>6} {t:>8.1f} {rate_est:>10.4f} {ci_str:>25}",
            "",
            "Test",
            f"  Null hypothesis:         H₀: Rate = {lam0}",
            f"  Alternative hypothesis:  H₁: Rate {alt_sym} {lam0}",
            f"  Method                 Z-Value  P-Value",
            f"  Exact                     —     {p_val_exact:.4f}",
            f"  Normal approximation   {z_stat:>7.2f}  {p_val_norm:.4f}",
        ]

        # Plot: Rate with CI
        plot_data = [
            {
                "type": "bar",
                "x": ["Sample 1"],
                "y": [rate_est],
                "error_y": {
                    "type": "data",
                    "symmetric": False,
                    "array": [ci_high - rate_est],
                    "arrayminus": [rate_est - ci_low],
                    "color": "#1e40af",
                    "thickness": 2,
                    "width": 10,
                },
                "marker": {"color": "rgba(99, 102, 241, 0.75)", "line": {"color": "#4338ca", "width": 1.5}},
            }
        ]

        layout = {
            "title": {"text": f"<b>1-Sample Poisson Rate (Rate₀ = {lam0})</b>", "x": 0.5},
            "showlegend": False,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 400,
            "yaxis": {"title": {"text": "Rate per Unit"}, "showgrid": True, "gridcolor": "#ececec"},
            "shapes": [
                {
                    "type": "line",
                    "xref": "paper",
                    "x0": 0,
                    "x1": 1,
                    "y0": lam0,
                    "y1": lam0,
                    "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"},
                }
            ],
        }

        return AnalysisResult(
            title="1-Sample Poisson Rate",
            subtitle=f"X={x}, T={t} (Rate₀={lam0})",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title="Descriptive Statistics", headers=desc_headers, rows=desc_rows),
                TableResult(title="Test Results", headers=test_headers, rows=test_rows)
            ],
            statistics={"rate": rate_est, "p_val_exact": p_val_exact, "p_val_norm": p_val_norm, "ci": [ci_low, ci_high]},
            plotly_figure={"data": plot_data, "layout": layout}
        )
