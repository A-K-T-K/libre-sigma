import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class TwoProportionsParams(BaseModel):
    data_mode: str = Field(
        "raw",
        description="Data Format",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Both samples are in separate columns", "value": "raw"},
                {"label": "Summarized data (Events & Trials for each sample)", "value": "summarized"},
            ]
        }
    )
    sample1_col: Optional[str] = Field(
        None,
        description="Sample 1 Column (for raw data)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    sample2_col: Optional[str] = Field(
        None,
        description="Sample 2 Column (for raw data)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    sample1_events: Optional[int] = Field(
        None,
        description="Sample 1 Events (X1)",
        json_schema_extra={"ui_type": "number"}
    )
    sample1_trials: Optional[int] = Field(
        None,
        description="Sample 1 Trials (N1)",
        json_schema_extra={"ui_type": "number"}
    )
    sample2_events: Optional[int] = Field(
        None,
        description="Sample 2 Events (X2)",
        json_schema_extra={"ui_type": "number"}
    )
    sample2_trials: Optional[int] = Field(
        None,
        description="Sample 2 Trials (N2)",
        json_schema_extra={"ui_type": "number"}
    )
    hypothesized_diff: float = Field(
        0.0,
        description="Hypothesized difference (p1 - p2)",
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


class TwoProportionsPlugin(AnalysisPlugin):
    id = "two_proportions"
    name = "2 Proportions"
    menu_path = ["Stat", "Basic Statistics", "2 Proportions"]
    description = "Compares two population proportions using Fisher's exact test and normal approximation test, with Odds Ratio and Relative Risk."
    param_schema = TwoProportionsParams

    def execute(self, df: pd.DataFrame, params: TwoProportionsParams) -> AnalysisResult:
        if params.data_mode == "raw":
            if not params.sample1_col or not params.sample2_col:
                raise ValueError("Select both Sample 1 and Sample 2 columns.")
            s1 = df[params.sample1_col].dropna()
            s2 = df[params.sample2_col].dropna()
            n1, n2 = len(s1), len(s2)
            if n1 < 1 or n2 < 1:
                raise ValueError("Both columns must contain valid data.")
            # Assume 1 / True / non-zero as event
            x1 = int(pd.to_numeric(s1, errors="coerce").fillna(0).astype(bool).sum())
            x2 = int(pd.to_numeric(s2, errors="coerce").fillna(0).astype(bool).sum())
        else:
            if None in (params.sample1_events, params.sample1_trials, params.sample2_events, params.sample2_trials):
                raise ValueError("Please provide Events and Trials for both samples.")
            x1, n1 = int(params.sample1_events), int(params.sample1_trials)
            x2, n2 = int(params.sample2_events), int(params.sample2_trials)
            if x1 < 0 or n1 <= 0 or x1 > n1 or x2 < 0 or n2 <= 0 or x2 > n2:
                raise ValueError("Events must be between 0 and Trials for both samples.")

        p1 = float(x1 / n1)
        p2 = float(x2 / n2)
        diff = p1 - p2

        conf = params.confidence_level / 100.0
        alpha = 1.0 - conf

        # Pooled proportion for hypothesis test
        p_pool = (x1 + x2) / (n1 + n2)
        se_pool = np.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n2))
        se_unpool = np.sqrt(p1 * (1.0 - p1) / n1 + p2 * (1.0 - p2) / n2)

        # CI for difference (Unpooled)
        z_crit = stats.norm.ppf(1.0 - alpha / 2.0)
        ci_low = diff - z_crit * se_unpool
        ci_high = diff + z_crit * se_unpool
        ci_str = f"({ci_low:.4f}, {ci_high:.4f})"

        # Normal Approximation Test
        z_stat = (diff - params.hypothesized_diff) / se_pool if se_pool > 0 else 0.0
        if params.alternative == "two_sided":
            p_val_norm = 2.0 * (1.0 - stats.norm.cdf(abs(z_stat)))
            alt_sym = "≠"
            fisher_alt = "two-sided"
        elif params.alternative == "less":
            p_val_norm = stats.norm.cdf(z_stat)
            alt_sym = "<"
            fisher_alt = "less"
        else:
            p_val_norm = 1.0 - stats.norm.cdf(z_stat)
            alt_sym = ">"
            fisher_alt = "greater"

        # Fisher's Exact Test
        contingency_table = [[x1, n1 - x1], [x2, n2 - x2]]
        odds_ratio, p_val_fisher = stats.fisher_exact(contingency_table, alternative=fisher_alt)

        # Relative Risk
        rel_risk = (p1 / p2) if p2 > 0 else np.nan

        # Tables
        desc_headers = ["Sample", "X (Events)", "N (Trials)", "Sample p"]
        desc_rows = [
            ["Sample 1", x1, n1, f"{p1:.4f}"],
            ["Sample 2", x2, n2, f"{p2:.4f}"],
        ]

        est_headers = ["Difference", "Estimate for Difference", f"{params.confidence_level}% CI for Difference"]
        est_rows = [["p₁ - p₂", f"{diff:.4f}", ci_str]]

        test_headers = ["Method", "Null hypothesis", "Alternative hypothesis", "Z-Value", "P-Value"]
        test_rows = [
            ["Normal approximation", f"H₀: p₁ - p₂ = {params.hypothesized_diff}", f"H₁: p₁ - p₂ {alt_sym} {params.hypothesized_diff}", f"{z_stat:.2f}", f"{p_val_norm:.4f}"],
            ["Fisher's exact", f"H₀: p₁ - p₂ = {params.hypothesized_diff}", f"H₁: p₁ - p₂ {alt_sym} {params.hypothesized_diff}", "—", f"{p_val_fisher:.4f}"],
        ]

        text_lines = [
            "Test and CI for Two Proportions",
            "",
            "Descriptive Statistics",
            f"  {'Sample':<12} {'X':>5} {'N':>5} {'Sample p':>10}",
            f"  {'-'*12} {'-'*5} {'-'*5} {'-'*10}",
            f"  {'Sample 1':<12} {x1:>5} {n1:>5} {p1:>10.4f}",
            f"  {'Sample 2':<12} {x2:>5} {n2:>5} {p2:>10.4f}",
            "",
            f"Estimation for Difference: {diff:.4f}",
            f"{params.confidence_level}% CI for Difference: {ci_str}",
            f"Odds Ratio: {odds_ratio:.4f}" if not np.isnan(odds_ratio) else "Odds Ratio: —",
            f"Relative Risk: {rel_risk:.4f}" if not np.isnan(rel_risk) else "Relative Risk: —",
            "",
            "Test",
            f"  Null hypothesis:         H₀: p₁ - p₂ = {params.hypothesized_diff}",
            f"  Alternative hypothesis:  H₁: p₁ - p₂ {alt_sym} {params.hypothesized_diff}",
            f"  Method                 Z-Value  P-Value",
            f"  Normal approximation   {z_stat:>7.2f}  {p_val_norm:.4f}",
            f"  Fisher's exact            —     {p_val_fisher:.4f}",
        ]

        # Plot: Comparative Bar Chart
        plot_data = [
            {
                "type": "bar",
                "x": ["Sample 1", "Sample 2"],
                "y": [p1, p2],
                "error_y": {
                    "type": "data",
                    "symmetric": True,
                    "array": [z_crit * np.sqrt(p1 * (1 - p1) / n1), z_crit * np.sqrt(p2 * (1 - p2) / n2)],
                    "color": "#1e40af",
                    "thickness": 2,
                    "width": 10,
                },
                "marker": {"color": ["#3b82f6", "#10b981"]},
            }
        ]

        layout = {
            "title": {"text": "<b>Comparison of Proportions (with 95% CIs)</b>", "x": 0.5},
            "showlegend": False,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 400,
            "yaxis": {"title": {"text": "Proportion"}, "range": [0, min(1.05, max(p1, p2) + 0.2)], "showgrid": True, "gridcolor": "#ececec"},
        }

        return AnalysisResult(
            title="2 Proportions",
            subtitle=f"Sample 1 ({x1}/{n1}) vs Sample 2 ({x2}/{n2})",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title="Descriptive Statistics", headers=desc_headers, rows=desc_rows),
                TableResult(title="Estimation for Difference", headers=est_headers, rows=est_rows),
                TableResult(title="Hypothesis Test Results", headers=test_headers, rows=test_rows)
            ],
            statistics={"diff": diff, "z_stat": z_stat, "p_val_norm": p_val_norm, "p_val_fisher": p_val_fisher, "odds_ratio": odds_ratio, "ci": [ci_low, ci_high]},
            plotly_figure={"data": plot_data, "layout": layout}
        )
