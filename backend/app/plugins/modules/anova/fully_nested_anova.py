"""
Fully Nested ANOVA Plugin for OpenMinitab.
Fits strictly hierarchical nested factor designs, computes sequential F-tests, and estimates variance components for each hierarchy level.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class FullyNestedAnovaParams(BaseModel):
    response_column: str = Field(
        ...,
        description="Response Variable (Continuous Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    nested_hierarchy: List[str] = Field(
        ...,
        description="Nested Factors in Hierarchical Order (e.g. Batch > Sample > Run)",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )


class FullyNestedAnovaPlugin(AnalysisPlugin):
    id = "fully_nested_anova"
    name = "Fully Nested ANOVA"
    menu_path = ["Stat", "ANOVA", "Fully Nested ANOVA"]
    description = "Evaluates strictly hierarchical multi-stage sampling designs with sequential F-tests and nested variance components."
    param_schema = FullyNestedAnovaParams

    def execute(self, df: pd.DataFrame, params: FullyNestedAnovaParams) -> AnalysisResult:
        y_col = params.response_column
        hierarchy = [f for f in params.nested_hierarchy if f in df.columns]

        if y_col not in df.columns or len(hierarchy) < 2:
            raise ValueError("Select a response variable and at least 2 hierarchical nested factors.")

        sub_df = df[[y_col] + hierarchy].dropna().copy().reset_index(drop=True)
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n_total = len(sub_df)
        if n_total < 6:
            raise ValueError("Fully Nested ANOVA requires at least 6 observations.")

        y = sub_df[y_col].to_numpy(dtype=float)
        grand_mean = float(np.mean(y))
        ss_total = float(np.sum((y - grand_mean) ** 2))

        # Hierarchical SS Decomposition
        # Stage 0: Factor 1 (Top Level)
        # Stage 1: Factor 2 nested in Factor 1 (F2|F1)
        # ...
        stage_names = []
        ss_stages = []
        df_stages = []
        prev_grouped_means = None
        prev_df = 0

        running_factors = []
        prev_ss_cum = 0.0

        for stage_idx, f in enumerate(hierarchy):
            running_factors.append(f)
            # Group by all factors up to current stage
            grp = sub_df.groupby(running_factors)[y_col]
            cell_means = grp.mean()
            cell_counts = grp.count()

            # Cumulative SS from top to current stage
            ss_cum = float(np.sum(cell_counts * (cell_means - grand_mean) ** 2))
            ss_stage = max(0.0, ss_cum - prev_ss_cum)
            df_cum = len(cell_means) - 1
            df_stage = max(1, df_cum - prev_df)

            if stage_idx == 0:
                stage_names.append(f)
            else:
                nest_str = "(" + ", ".join(hierarchy[:stage_idx]) + ")"
                stage_names.append(f"{f}{nest_str}")

            ss_stages.append(ss_stage)
            df_stages.append(df_stage)

            prev_ss_cum = ss_cum
            prev_df = df_cum

        # Error Term (Replication within innermost nested cell)
        ss_error = max(0.0, ss_total - prev_ss_cum)
        df_error = max(1, n_total - 1 - prev_df)

        stage_names.append("Error")
        ss_stages.append(ss_error)
        df_stages.append(df_error)

        ms_stages = [ss / max(1, df_val) for ss, df_val in zip(ss_stages, df_stages)]

        # Sequential F-Tests: MS(Stage k) / MS(Stage k + 1)
        anova_rows = []
        n_stages = len(stage_names)

        for k_idx in range(n_stages - 1):
            ms_k = ms_stages[k_idx]
            ms_next = ms_stages[k_idx + 1]
            df_k = df_stages[k_idx]
            df_next = df_stages[k_idx + 1]

            f_k = ms_k / max(1e-12, ms_next)
            p_k = float(1.0 - stats.f.cdf(f_k, df_k, df_next))

            anova_rows.append([
                stage_names[k_idx],
                str(df_k),
                f"{ss_stages[k_idx]:.4f}",
                f"{ms_k:.4f}",
                f"{f_k:.2f}",
                f"{p_k:.4f}" if p_k >= 0.0001 else "< 0.0001"
            ])

        anova_rows.append([stage_names[-1], str(df_stages[-1]), f"{ss_stages[-1]:.4f}", f"{ms_stages[-1]:.4f}", "---", "---"])
        anova_rows.append(["Total", str(n_total - 1), f"{ss_total:.4f}", "---", "---", "---"])

        # Variance Components Estimation
        var_comps = []
        # Error variance
        var_err = ms_stages[-1]
        var_comps.append(var_err)

        for k_idx in range(n_stages - 2, -1, -1):
            ms_k = ms_stages[k_idx]
            ms_next = ms_stages[k_idx + 1]
            # Divisor c is product of sub-sample sizes
            c_div = max(1.0, float(n_total) / float(df_stages[k_idx] + 1))
            var_k = max(0.0, (ms_k - ms_next) / c_div)
            var_comps.append(var_k)

        var_comps = var_comps[::-1] # Order from top factor to error
        var_total = float(sum(var_comps))
        pct_var = [(v / max(1e-12, var_total)) * 100.0 for v in var_comps]

        var_table = TableResult(
            title="Variance Component Estimation (Fully Nested Random Effects)",
            headers=["Hierarchy Level", "VarComponent", "StdDev", "% of Total Variance"],
            rows=[
                [
                    stage_names[i],
                    f"{var_comps[i]:.4f}",
                    f"{math.sqrt(var_comps[i]):.4f}",
                    f"{pct_var[i]:.2f}%"
                ]
                for i in range(n_stages)
            ]
        )

        anova_table = TableResult(
            title=f"Fully Nested Analysis of Variance for {y_col}",
            headers=["Source", "DF", "SS", "MS", "F-Value (Sequential)", "p-Value"],
            rows=anova_rows
        )

        # Plotly Variance Components Bar Chart
        plotly_fig = {
            "data": [
                {
                    "type": "bar",
                    "x": stage_names,
                    "y": pct_var,
                    "marker": {"color": ["#0078d4", "#008450", "#d13438", "#881798", "#ca5010"][:n_stages]}
                }
            ],
            "layout": {
                "title": f"Variance Component Distribution (% of Total Variance) for {y_col}",
                "xaxis": {"title": "Hierarchy Stage", "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": "% of Total Variance", "range": [0, 105], "ticksuffix": "%", "showgrid": True, "gridcolor": "#ececec"},
            }
        }

        return AnalysisResult(
            title=f"Fully Nested ANOVA: {y_col}",
            subtitle=f"{len(hierarchy)} Hierarchical Stages | Top Source: {stage_names[int(np.argmax(pct_var))]} ({np.max(pct_var):.1f}%)",
            tables=[anova_table, var_table],
            plotly_figure=plotly_fig,
            statistics={
                "variance_components": dict(zip(stage_names, var_comps)),
                "pct_variance": dict(zip(stage_names, pct_var)),
                "hierarchy": hierarchy
            }
        )
