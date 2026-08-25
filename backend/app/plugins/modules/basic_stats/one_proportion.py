import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class OneProportionParams(BaseModel):
    data_mode: str = Field(
        "raw",
        description="Data Format",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "One or more samples, each in a column", "value": "raw"},
                {"label": "Summarized data (Events & Trials)", "value": "summarized"},
            ]
        }
    )
    sample_col: Optional[str] = Field(
        None,
        description="Sample Column (for raw data)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    event_value: Optional[str] = Field(
        None,
        description="Event Value in Column (defaults to 1 or True or first unique)",
        json_schema_extra={"ui_type": "text"}
    )
    num_events: Optional[int] = Field(
        None,
        description="Number of Events (for summarized data)",
        json_schema_extra={"ui_type": "number"}
    )
    num_trials: Optional[int] = Field(
        None,
        description="Number of Trials (for summarized data)",
        json_schema_extra={"ui_type": "number"}
    )
    hypothesized_prop: float = Field(
        0.5,
        description="Hypothesized proportion (p_0 between 0 and 1)",
        json_schema_extra={"ui_type": "number"}
    )
    alternative: str = Field(
        "two_sided",
        description="Alternative Hypothesis",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "proportion != hypothesized prop (two-sided)", "value": "two_sided"},
                {"label": "proportion < hypothesized prop (less than)", "value": "less"},
                {"label": "proportion > hypothesized prop (greater than)", "value": "greater"},
            ]
        }
    )
    confidence_level: float = Field(
        95.0,
        description="Confidence level (%)",
        json_schema_extra={"ui_type": "number"}
    )
    method: str = Field(
        "exact",
        description="Calculation Method",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Exact (Clopper-Pearson)", "value": "exact"},
                {"label": "Normal approximation", "value": "normal_approx"},
            ]
        }
    )


class OneProportionPlugin(AnalysisPlugin):
    id = "one_proportion"
    name = "1 Proportion"
    menu_path = ["Stat", "Basic Statistics", "1 Proportion"]
    description = "Tests for a population proportion and computes exact Clopper-Pearson or normal approximation confidence intervals."
    param_schema = OneProportionParams

    def execute(self, df: pd.DataFrame, params: OneProportionParams) -> AnalysisResult:
        if params.data_mode == "raw":
            if not params.sample_col or params.sample_col not in df.columns:
                raise ValueError("Select a valid Sample Column for raw data mode.")
            series = df[params.sample_col].dropna()
            n = len(series)
            if n < 1:
                raise ValueError("Column contains no valid data.")

            if params.event_value:
                x = int((series.astype(str) == str(params.event_value)).sum())
            else:
                # Infer binary event
                uniques = series.unique()
                event_val = uniques[0]
                x = int((series == event_val).sum())
        else:
            if params.num_events is None or params.num_trials is None:
                raise ValueError("Please provide Number of Events and Number of Trials.")
            x = int(params.num_events)
            n = int(params.num_trials)
            if x < 0 or n <= 0 or x > n:
                raise ValueError(f"Invalid inputs: Events ({x}) must be between 0 and Trials ({n}).")

        sample_p = float(x / n)
        p0 = float(params.hypothesized_prop)
        if p0 <= 0 or p0 >= 1:
            raise ValueError("Hypothesized proportion must be strictly between 0 and 1.")

        conf = params.confidence_level / 100.0
        alpha = 1.0 - conf

        # Exact Clopper-Pearson Test & CI
        alt_map = {"two_sided": "two-sided", "less": "less", "greater": "greater"}
        binom_res = stats.binomtest(x, n, p=p0, alternative=alt_map.get(params.alternative, "two-sided"))
        p_val_exact = float(binom_res.pvalue)
        ci_exact = binom_res.proportion_ci(confidence_level=conf)

        # Normal Approximation
        se_norm = np.sqrt(p0 * (1.0 - p0) / n)
        z_stat = (sample_p - p0) / se_norm if se_norm > 0 else 0.0

        if params.alternative == "two_sided":
            p_val_norm = 2.0 * (1.0 - stats.norm.cdf(abs(z_stat)))
            z_crit = stats.norm.ppf(1.0 - alpha / 2.0)
            ci_norm_low = max(0.0, sample_p - z_crit * np.sqrt(sample_p * (1 - sample_p) / n))
            ci_norm_high = min(1.0, sample_p + z_crit * np.sqrt(sample_p * (1 - sample_p) / n))
            alt_sym = "≠"
        elif params.alternative == "less":
            p_val_norm = stats.norm.cdf(z_stat)
            z_crit = stats.norm.ppf(1.0 - alpha)
            ci_norm_low = 0.0
            ci_norm_high = min(1.0, sample_p + z_crit * np.sqrt(sample_p * (1 - sample_p) / n))
            alt_sym = "<"
        else:
            p_val_norm = 1.0 - stats.norm.cdf(z_stat)
            z_crit = stats.norm.ppf(1.0 - alpha)
            ci_norm_low = max(0.0, sample_p - z_crit * np.sqrt(sample_p * (1 - sample_p) / n))
            ci_norm_high = 1.0
            alt_sym = ">"

        if params.method == "exact":
            p_val = p_val_exact
            ci_low, ci_high = ci_exact.low, ci_exact.high
            method_desc = "Exact"
        else:
            p_val = float(p_val_norm)
            ci_low, ci_high = ci_norm_low, ci_norm_high
            method_desc = "Normal approximation"

        ci_str = f"({ci_low:.4f}, {ci_high:.4f})"

        # Tables
        desc_headers = ["Sample", "X (Events)", "N (Trials)", "Sample p", f"{params.confidence_level}% CI ({method_desc})"]
        desc_rows = [["Sample 1", x, n, f"{sample_p:.4f}", ci_str]]

        test_headers = ["Method", "Null hypothesis", "Alternative hypothesis", "Z-Value", "P-Value"]
        test_rows = [
            ["Exact", f"H₀: p = {p0}", f"H₁: p {alt_sym} {p0}", "—", f"{p_val_exact:.4f}"],
            ["Normal approximation", f"H₀: p = {p0}", f"H₁: p {alt_sym} {p0}", f"{z_stat:.2f}", f"{p_val_norm:.4f}"],
        ]

        text_lines = [
            "Test and CI for One Proportion",
            "",
            "Descriptive Statistics",
            f"  {'Sample':<12} {'X':>5} {'N':>5} {'Sample p':>10} {f'{params.confidence_level}% CI ({method_desc})':>25}",
            f"  {'-'*12} {'-'*5} {'-'*5} {'-'*10} {'-'*25}",
            f"  {'Sample 1':<12} {x:>5} {n:>5} {sample_p:>10.4f} {ci_str:>25}",
            "",
            "Test",
            f"  Null hypothesis:         H₀: p = {p0}",
            f"  Alternative hypothesis:  H₁: p {alt_sym} {p0}",
            f"  Method                 Z-Value  P-Value",
            f"  Exact                     —     {p_val_exact:.4f}",
            f"  Normal approximation   {z_stat:>7.2f}  {p_val_norm:.4f}",
        ]

        # Plot: Proportion with CI
        plot_data = [
            {
                "type": "bar",
                "x": ["Sample 1"],
                "y": [sample_p],
                "error_y": {
                    "type": "data",
                    "symmetric": False,
                    "array": [ci_high - sample_p],
                    "arrayminus": [sample_p - ci_low],
                    "color": "#1e40af",
                    "thickness": 2,
                    "width": 10,
                },
                "marker": {"color": "rgba(59, 130, 246, 0.75)", "line": {"color": "#1e40af", "width": 1.5}},
                "name": "Sample Proportion",
            }
        ]

        layout = {
            "title": {"text": f"<b>1 Proportion Test (p₀ = {p0})</b>", "x": 0.5},
            "showlegend": False,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 400,
            "yaxis": {"title": {"text": "Proportion"}, "range": [0, min(1.05, max(ci_high + 0.1, p0 + 0.1))], "showgrid": True, "gridcolor": "#ececec"},
            "shapes": [
                {
                    "type": "line",
                    "xref": "paper",
                    "x0": 0,
                    "x1": 1,
                    "y0": p0,
                    "y1": p0,
                    "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"},
                }
            ],
            "annotations": [
                {
                    "xref": "paper",
                    "x": 0.02,
                    "y": p0,
                    "text": f"H₀: p₀ = {p0}",
                    "showarrow": False,
                    "font": {"color": "#dc2626", "size": 11},
                    "bgcolor": "#ffffff",
                }
            ]
        }

        return AnalysisResult(
            title="1 Proportion",
            subtitle=f"X={x}, N={n} (p₀={p0})",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title="Descriptive Statistics", headers=desc_headers, rows=desc_rows),
                TableResult(title="Test Results", headers=test_headers, rows=test_rows)
            ],
            statistics={"sample_p": sample_p, "p_val_exact": p_val_exact, "p_val_norm": p_val_norm, "ci": [ci_low, ci_high]},
            plotly_figure={"data": plot_data, "layout": layout}
        )
