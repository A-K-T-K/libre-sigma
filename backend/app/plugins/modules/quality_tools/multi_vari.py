"""
Multi-Vari & Variability Chart Plugin for OpenMinitab Quality Tools.
Visualizes hierarchical sources of variation (Within-piece, Piece-to-piece, Time-to-time) across nested factors.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class MultiVariParams(BaseModel):
    response_column: str = Field(
        ...,
        description="Response Variable (Continuous)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    factor_1: str = Field(
        ...,
        description="Factor 1 (e.g. Within-Piece Position)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    factor_2: Optional[str] = Field(
        None,
        description="Factor 2 (e.g. Piece / Sample, optional)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    factor_3: Optional[str] = Field(
        None,
        description="Factor 3 (e.g. Batch / Day, optional)",
        json_schema_extra={"ui_type": "column_picker"}
    )


class MultiVariPlugin(AnalysisPlugin):
    id = "multi_vari"
    name = "Multi-Vari Chart"
    menu_path = ["Stat", "Quality Tools", "Multi-Vari Chart"]
    description = "Displays hierarchical sources of variation across multiple nested process factors."
    param_schema = MultiVariParams

    def execute(self, df: pd.DataFrame, params: MultiVariParams) -> AnalysisResult:
        resp_col = params.response_column
        f1 = params.factor_1
        f2 = params.factor_2
        f3 = params.factor_3

        factors = [f for f in [f1, f2, f3] if f and f in df.columns]
        if len(factors) == 0 or resp_col not in df.columns:
            raise ValueError("Specify a valid response variable and at least one factor.")

        sub_df = df[[resp_col] + factors].dropna().copy()
        sub_df[resp_col] = pd.to_numeric(sub_df[resp_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        if len(sub_df) < 4:
            raise ValueError("Multi-Vari Chart requires at least 4 observations.")

        grand_mean = float(sub_df[resp_col].mean())

        # Group by factor hierarchy
        grouped = sub_df.groupby(factors, sort=False)[resp_col].agg(["mean", "min", "max", "count"]).reset_index()

        table_rows = []
        for _, r in grouped.iterrows():
            row_vals = [str(r[f]) for f in factors]
            row_vals.extend([
                f"{r['mean']:.4f}",
                f"{r['min']:.4f}",
                f"{r['max']:.4f}",
                str(int(r['count']))
            ])
            table_rows.append(row_vals)

        multivari_table = TableResult(
            title=f"Multi-Vari Cell Means for {resp_col}",
            headers=factors + ["Cell Mean", "Min", "Max", "Count"],
            rows=table_rows
        )

        # Plotly Hierarchical Multi-Vari Traces
        traces = []
        x_ticks = []
        x_labels = []

        if len(factors) == 1:
            cats = grouped[f1].unique()
            x_vals = list(range(len(cats)))
            y_means = [float(grouped[grouped[f1] == c]["mean"].iloc[0]) for c in cats]
            traces.append({
                "type": "scatter",
                "mode": "lines+markers",
                "x": x_vals,
                "y": y_means,
                "name": f1,
                "line": {"color": "#0078d4", "width": 2},
                "marker": {"size": 8, "color": "#004d2c"}
            })
            x_ticks = x_vals
            x_labels = [str(c) for c in cats]
        else:
            # Primary grouping by outer factor, connecting lines for inner factor
            outer_factor = factors[-1]
            inner_factor = factors[0]
            outer_cats = sub_df[outer_factor].unique()

            x_idx = 0
            for out_val in outer_cats:
                sub_grp = grouped[grouped[outer_factor] == out_val]
                x_sub = list(range(x_idx, x_idx + len(sub_grp)))
                y_sub = sub_grp["mean"].tolist()

                traces.append({
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": x_sub,
                    "y": y_sub,
                    "name": f"{outer_factor} = {out_val}",
                    "marker": {"size": 7}
                })

                for i, (_, row) in enumerate(sub_grp.iterrows()):
                    x_ticks.append(x_idx + i)
                    x_labels.append(f"{row[inner_factor]} ({out_val})")

                x_idx += len(sub_grp) + 1

        # Grand Mean Reference Line
        traces.append({
            "type": "scatter",
            "mode": "lines",
            "x": [0, max(x_ticks) if x_ticks else 1],
            "y": [grand_mean, grand_mean],
            "name": f"Grand Mean ({grand_mean:.3f})",
            "line": {"color": "#d13438", "width": 1.5, "dash": "dash"}
        })

        plotly_fig = {
            "data": traces,
            "layout": {
                "title": f"Multi-Vari Chart for {resp_col} by " + ", ".join(factors),
                "xaxis": {
                    "title": " / ".join(factors),
                    "tickvals": x_ticks,
                    "ticktext": x_labels,
                    "tickangle": -25 if len(x_labels) > 6 else 0,
                    "showgrid": True,
                    "gridcolor": "#ececec"
                },
                "yaxis": {"title": resp_col, "showgrid": True, "gridcolor": "#ececec"},
                "legend": {"orientation": "h", "y": -0.25}
            }
        }

        return AnalysisResult(
            title=f"Multi-Vari Chart for {resp_col}",
            subtitle=f"Grand Mean = {grand_mean:.4f} across {len(grouped)} factor cells",
            tables=[multivari_table],
            plotly_figure=plotly_fig,
            statistics={
                "grand_mean": grand_mean,
                "num_cells": len(grouped),
                "factors": factors
            }
        )
