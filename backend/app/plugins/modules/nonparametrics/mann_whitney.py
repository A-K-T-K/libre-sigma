"""
Mann-Whitney 2-Sample Rank-Sum Test Plugin for OpenMinitab.
Performs Mann-Whitney test for the difference between two population medians (eta1 - eta2), with Hodges-Lehmann point estimate and confidence intervals.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class MannWhitneyParams(BaseModel):
    first_sample: str = Field(
        ...,
        description="First Sample (X)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    second_sample: str = Field(
        ...,
        description="Second Sample (Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    alternative: str = Field(
        "two-sided",
        description="Alternative Hypothesis",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "not equal (η1 ≠ η2)", "value": "two-sided"},
                {"label": "less than (η1 < η2)", "value": "less"},
                {"label": "greater than (η1 > η2)", "value": "greater"}
            ]
        }
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%)"
    )


class MannWhitneyPlugin(AnalysisPlugin):
    id = "nonparam_mann_whitney"
    name = "Mann-Whitney"
    menu_path = ["Stat", "Nonparametrics", "Mann-Whitney"]
    description = "Nonparametric hypothesis test for the difference between two independent population medians (η1 - η2)."
    param_schema = MannWhitneyParams

    def execute(self, df: pd.DataFrame, params: MannWhitneyParams) -> AnalysisResult:
        col1, col2 = params.first_sample, params.second_sample
        if col1 not in df.columns or col2 not in df.columns:
            raise ValueError(f"Columns '{col1}' and/or '{col2}' not found in active worksheet.")

        s1 = pd.to_numeric(df[col1], errors="coerce").dropna().to_numpy(dtype=float)
        s2 = pd.to_numeric(df[col2], errors="coerce").dropna().to_numpy(dtype=float)

        n1, n2 = len(s1), len(s2)
        if n1 < 2 or n2 < 2:
            raise ValueError("Mann-Whitney test requires at least 2 valid observations in each sample.")

        med1, med2 = float(np.median(s1)), float(np.median(s2))

        # Perform Mann-Whitney U test
        res = stats.mannwhitneyu(s1, s2, alternative=params.alternative)
        u_stat = float(res.statistic)
        p_val = float(res.pvalue)

        # Wilcoxon W statistic = U + n1*(n1 + 1)/2
        w_stat = u_stat + (n1 * (n1 + 1)) / 2.0

        # Hodges-Lehmann Difference in Medians (pairwise differences s1_i - s2_j)
        pairwise_diffs = []
        for v1 in s1:
            for v2 in s2:
                pairwise_diffs.append(v1 - v2)
        pairwise_sorted = np.sort(pairwise_diffs)
        hl_diff = float(np.median(pairwise_sorted))

        # Hodges-Lehmann Confidence Interval
        alpha = 1.0 - params.confidence_level / 100.0
        z_val = stats.norm.ppf(1.0 - alpha / 2.0)
        n_pairs = len(pairwise_sorted)
        mu_u = n1 * n2 / 2.0
        sigma_u = np.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0)
        k_lower = max(0, int(np.floor(mu_u - z_val * sigma_u)))
        k_upper = min(n_pairs - 1, int(np.ceil(mu_u + z_val * sigma_u)))

        ci_lower = float(pairwise_sorted[k_lower])
        ci_upper = float(pairwise_sorted[k_upper])

        # Plotly Boxplot / Distribution comparison
        traces = [
            {
                "y": s1.tolist(),
                "type": "box",
                "name": f"{col1} (N={n1})",
                "boxpoints": "all",
                "jitter": 0.3,
                "pointpos": -1.8,
                "marker": {"color": "#008450", "size": 5},
                "line": {"color": "#008450"}
            },
            {
                "y": s2.tolist(),
                "type": "box",
                "name": f"{col2} (N={n2})",
                "boxpoints": "all",
                "jitter": 0.3,
                "pointpos": -1.8,
                "marker": {"color": "#005a9e", "size": 5},
                "line": {"color": "#005a9e"}
            }
        ]

        layout = {
            "title": {"text": f"<b>Mann-Whitney Test: {col1} vs {col2}</b><br><span style='font-size:11px;color:#605e5c'>Estimated Difference (η1 - η2) = {hl_diff:.4f} (p = {p_val:.5f})</span>", "font": {"size": 13, "color": "#201f1e"}},
            "yaxis": {"title": "Values", "showgrid": True, "gridcolor": "#f3f2f1"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 50}
        }

        # Table
        desc_table = TableResult(
            title="Sample Medians and Difference",
            headers=["Sample", "N", "Median", "Hodges-Lehmann Difference", f"{params.confidence_level:.0f}% CI for Difference"],
            rows=[
                [col1, n1, round(med1, 4), f"{hl_diff:.4f}", f"[{ci_lower:.4f}, {ci_upper:.4f}]"],
                [col2, n2, round(med2, 4), "", ""]
            ]
        )

        test_table = TableResult(
            title="Mann-Whitney Test Statistic",
            headers=["Statistic", "Value"],
            rows=[
                ["Mann-Whitney U", f"{u_stat:.2f}"],
                ["Wilcoxon W", f"{w_stat:.2f}"],
                ["P-Value (Adjusted for ties)", f"{p_val:.5f}"],
                ["Alternative Hypothesis", f"η1 " + ("≠" if params.alternative == "two-sided" else "<" if params.alternative == "less" else ">") + " η2"]
            ]
        )

        text_lines = [
            f"Mann-Whitney Test: {col1} versus {col2}",
            "",
            f"  {'Sample':<16} {'N':>6} {'Median':>12}",
            f"  {'-'*16} {'-'*6} {'-'*12}",
            f"  {col1:<16} {n1:>6} {med1:>12.4f}",
            f"  {col2:<16} {n2:>6} {med2:>12.4f}",
            "",
            f"Point estimate for η1 - η2 is {hl_diff:.4f}",
            f"{params.confidence_level:.0f}% CI for η1 - η2 is [{ci_lower:.4f}, {ci_upper:.4f}]",
            "",
            f"W = {w_stat:.2f} (U = {u_stat:.2f})",
            f"Test of η1 = η2 vs η1 " + ("≠" if params.alternative == "two-sided" else "<" if params.alternative == "less" else ">") + f" η2 is significant at P = {p_val:.5f}"
        ]

        return AnalysisResult(
            title="Mann-Whitney Test",
            subtitle=f"{col1} vs {col2}",
            text_output="\n".join(text_lines),
            tables=[desc_table, test_table],
            plotly_figure={"data": traces, "layout": layout}
        )
