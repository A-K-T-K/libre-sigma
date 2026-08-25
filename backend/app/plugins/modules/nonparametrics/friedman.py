"""
Friedman Test Plugin for OpenMinitab.
Nonparametric alternative to Two-Way ANOVA for randomized complete block designs (RCBD).
Computes Treatment Level Ranks, Friedman S-statistic, DF, and p-values.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class FriedmanParams(BaseModel):
    response: str = Field(
        ...,
        description="Response Variable (Continuous Measurement)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    treatment: str = Field(
        ...,
        description="Treatment Factor",
        json_schema_extra={"ui_type": "column_picker"}
    )
    blocks: str = Field(
        ...,
        description="Blocking Factor",
        json_schema_extra={"ui_type": "column_picker"}
    )


class FriedmanPlugin(AnalysisPlugin):
    id = "nonparam_friedman"
    name = "Friedman Test"
    menu_path = ["Stat", "Nonparametrics", "Friedman Test"]
    description = "Nonparametric test for randomized complete block designs comparing treatment effects across blocks."
    param_schema = FriedmanParams

    def execute(self, df: pd.DataFrame, params: FriedmanParams) -> AnalysisResult:
        resp_col, trt_col, blk_col = params.response, params.treatment, params.blocks
        for c in [resp_col, trt_col, blk_col]:
            if c not in df.columns:
                raise ValueError(f"Column '{c}' not found in active worksheet.")

        sub_df = df[[blk_col, trt_col, resp_col]].dropna().copy()
        sub_df[resp_col] = pd.to_numeric(sub_df[resp_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        if len(sub_df) < 4:
            raise ValueError("Friedman test requires at least 4 observations.")

        # Pivot into Blocks (rows) x Treatments (columns)
        piv = sub_df.pivot_table(index=blk_col, columns=trt_col, values=resp_col, aggfunc="mean")
        piv_clean = piv.dropna()

        n_blocks, k_trts = piv_clean.shape
        if n_blocks < 2:
            raise ValueError("Friedman test requires at least 2 complete blocks with no missing treatment combinations.")
        if k_trts < 2:
            raise ValueError("Friedman test requires at least 2 treatment levels.")

        # Rank treatments within each block row
        rank_matrix = np.apply_along_axis(stats.rankdata, 1, piv_clean.to_numpy(dtype=float))

        # Sum of ranks per treatment column
        rank_sums = np.sum(rank_matrix, axis=0)
        trt_names = list(piv_clean.columns)

        # scipy.stats.friedmanchisquare takes treatments as separate positional args
        trt_series_list = [piv_clean[col].to_numpy(dtype=float) for col in trt_names]
        friedman_res = stats.friedmanchisquare(*trt_series_list)

        s_stat = float(friedman_res.statistic)
        p_val = float(friedman_res.pvalue)
        df_deg = k_trts - 1

        # Table rows
        table_rows = []
        traces = []
        for idx, t_name in enumerate(trt_names):
            r_sum = float(rank_sums[idx])
            med_t = float(np.median(piv_clean[t_name]))
            table_rows.append([str(t_name), n_blocks, round(med_t, 4), round(r_sum, 1)])

            traces.append({
                "x": [str(t_name)],
                "y": [r_sum],
                "type": "bar",
                "name": str(t_name),
                "text": [f"Rank Sum: {r_sum:.1f}"],
                "textposition": "auto",
                "marker": {"color": "#008450"}
            })

        layout = {
            "title": {"text": f"<b>Friedman Test: {resp_col} by {trt_col} (Blocked by {blk_col})</b><br><span style='font-size:11px;color:#605e5c'>S = {s_stat:.3f}, DF = {df_deg}, p-value = {p_val:.5f}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": f"Treatment: {trt_col}", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Sum of Ranks", "showgrid": True, "gridcolor": "#f3f2f1"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 50}
        }

        desc_table = TableResult(
            title=f"Friedman Test for {resp_col} by {trt_col} blocked by {blk_col}",
            headers=[trt_col, "N (Blocks)", "Est Median", "Sum of Ranks"],
            rows=table_rows
        )

        test_table = TableResult(
            title="Friedman Test Statistic",
            headers=["Criterion", "Value"],
            rows=[
                ["Friedman Statistic (S)", f"{s_stat:.3f}"],
                ["Degrees of Freedom (DF)", str(df_deg)],
                ["P-Value", f"{p_val:.5f}"]
            ]
        )

        text_lines = [
            f"Friedman Test: {resp_col} versus {trt_col} blocked by {blk_col}",
            f"S = {s_stat:.2f}   DF = {df_deg}   P-Value = {p_val:.4f}",
            "",
            f"  {trt_col:<18} {'N':>6} {'Est Median':>12} {'Sum of Ranks':>14}",
            f"  {'-'*18} {'-'*6} {'-'*12} {'-'*14}",
        ]
        for r in table_rows:
            text_lines.append(f"  {r[0]:<18} {r[1]:>6} {r[2]:>12.4f} {r[3]:>14.1f}")

        return AnalysisResult(
            title="Friedman Test",
            subtitle=f"{trt_col} Blocked by {blk_col}",
            text_output="\n".join(text_lines),
            tables=[desc_table, test_table],
            plotly_figure={"data": traces, "layout": layout}
        )
