"""
Mood's Median Test Plugin for OpenMinitab.
Tests the equality of medians from two or more independent populations by dichotomizing data around the overall median.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class MoodsMedianParams(BaseModel):
    response: str = Field(
        ...,
        description="Response Variable (Continuous Numeric)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    factor: str = Field(
        ...,
        description="Factor Variable (Grouping / Categorical)",
        json_schema_extra={"ui_type": "column_picker"}
    )


class MoodsMedianPlugin(AnalysisPlugin):
    id = "nonparam_moods_median"
    name = "Mood's Median Test"
    menu_path = ["Stat", "Nonparametrics", "Mood's Median Test"]
    description = "Nonparametric test for equality of medians across groups by evaluating counts above and below the overall grand median."
    param_schema = MoodsMedianParams

    def execute(self, df: pd.DataFrame, params: MoodsMedianParams) -> AnalysisResult:
        resp_col, factor_col = params.response, params.factor
        if resp_col not in df.columns or factor_col not in df.columns:
            raise ValueError(f"Columns '{resp_col}' and/or '{factor_col}' not found in active worksheet.")

        sub_df = df[[factor_col, resp_col]].dropna().copy()
        sub_df[resp_col] = pd.to_numeric(sub_df[resp_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n_total = len(sub_df)
        if n_total < 4:
            raise ValueError("Mood's Median test requires at least 4 valid observations.")

        groups = sub_df[factor_col].unique()
        k = len(groups)
        if k < 2:
            raise ValueError(f"Factor '{factor_col}' must contain at least 2 distinct levels.")

        all_y = sub_df[resp_col].to_numpy(dtype=float)
        grand_median = float(np.median(all_y))

        # Build group arrays
        group_arrays = [sub_df[sub_df[factor_col] == g][resp_col].to_numpy(dtype=float) for g in groups]

        # Mood's Median test via scipy.stats.median_test
        stat_val, p_val, med_val, table_contingency = stats.median_test(*group_arrays, ties="below")

        df_deg = k - 1

        # Table rows: [Group, N <= Median, N > Median, Median, Q1, Q3, 95% CI]
        table_rows = []
        traces = []

        for idx, g in enumerate(groups):
            grp_y = group_arrays[idx]
            n_i = len(grp_y)
            n_above = int(np.sum(grp_y > grand_median))
            n_below = int(np.sum(grp_y <= grand_median))

            med_i = float(np.median(grp_y))
            q1_i = float(np.percentile(grp_y, 25))
            q3_i = float(np.percentile(grp_y, 75))
            iqr_i = q3_i - q1_i

            # Standard 95% CI approximation for group median: median ± 1.57 * IQR / sqrt(n)
            ci_half = (1.57 * iqr_i) / np.sqrt(n_i) if n_i > 1 else 0.0
            ci_str = f"[{med_i - ci_half:.2f}, {med_i + ci_half:.2f}]"

            table_rows.append([str(g), n_below, n_above, round(med_i, 4), round(q1_i, 4), round(q3_i, 4), ci_str])

            traces.append({
                "y": grp_y.tolist(),
                "type": "box",
                "name": f"{g} (Med={med_i:.2f})",
                "boxpoints": "all",
                "jitter": 0.25,
                "pointpos": -1.8
            })

        # Overall reference line
        shapes = [{
            "type": "line",
            "xref": "paper",
            "x0": 0,
            "x1": 1,
            "y0": grand_median,
            "y1": grand_median,
            "line": {"color": "#d13438", "width": 1.5, "dash": "dash"}
        }]

        layout = {
            "title": {"text": f"<b>Mood's Median Test: {resp_col} by {factor_col}</b><br><span style='font-size:11px;color:#605e5c'>Overall Grand Median = {grand_median:.4f} (Chi-Sq = {stat_val:.3f}, p = {p_val:.5f})</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": factor_col, "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": resp_col, "showgrid": True, "gridcolor": "#f3f2f1"},
            "shapes": shapes,
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 50}
        }

        table = TableResult(
            title=f"Mood's Median Test: {resp_col} versus {factor_col}",
            headers=[factor_col, "N <= Median", "N > Median", "Median", "Q1", "Q3", "95% CI for Median"],
            rows=table_rows
        )

        test_table = TableResult(
            title="Chi-Square Test for Equality of Medians",
            headers=["Overall Median", "Chi-Square", "DF", "P-Value"],
            rows=[[round(grand_median, 4), round(float(stat_val), 3), df_deg, round(float(p_val), 5)]]
        )

        text_lines = [
            f"Mood's Median Test: {resp_col} versus {factor_col}",
            "",
            f"Overall Median = {grand_median:.4f}",
            "",
            f"  {factor_col:<16} {'<= Median':>10} {'> Median':>10} {'Median':>10} {'Q1':>10} {'Q3':>10}",
            f"  {'-'*16} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}",
        ]
        for r in table_rows:
            text_lines.append(f"  {r[0]:<16} {r[1]:>10} {r[2]:>10} {r[3]:>10.4f} {r[4]:>10.4f} {r[5]:>10.4f}")

        text_lines += [
            "",
            f"Chi-Square = {stat_val:.3f}   DF = {df_deg}   P-Value = {p_val:.5f}"
        ]

        return AnalysisResult(
            title="Mood's Median Test",
            subtitle=f"{resp_col} by {factor_col}",
            text_output="\n".join(text_lines),
            tables=[table, test_table],
            plotly_figure={"data": traces, "layout": layout}
        )
