"""
Pareto Chart Plugin for OpenMinitab Quality Tools.
Displays defect frequencies in descending order with cumulative percentage curve and dual-axis visualization.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class ParetoChartParams(BaseModel):
    defects_column: str = Field(
        ...,
        description="Defects or Attribute Variable",
        json_schema_extra={"ui_type": "column_picker"}
    )
    frequencies_column: Optional[str] = Field(
        None,
        description="Frequencies / Costs Variable (optional)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    combine_threshold: float = Field(
        95.0,
        ge=50.0,
        le=100.0,
        description="Combine remaining defect categories after this percentage (Default: 95%)"
    )
    other_label: str = Field("Other", description="Label for combined categories")


class ParetoChartPlugin(AnalysisPlugin):
    id = "pareto_chart"
    name = "Pareto Chart"
    menu_path = ["Stat", "Quality Tools", "Pareto Chart"]
    description = "Identifies the vital few causes vs. trivial many using 80/20 dual-axis Pareto analysis."
    param_schema = ParetoChartParams

    def execute(self, df: pd.DataFrame, params: ParetoChartParams) -> AnalysisResult:
        defect_col = params.defects_column
        if defect_col not in df.columns:
            raise ValueError(f"Defects column '{defect_col}' not found in active worksheet.")

        freq_col = params.frequencies_column

        # Clean and aggregate
        if freq_col and freq_col in df.columns:
            sub_df = df[[defect_col, freq_col]].dropna().copy()
            sub_df[freq_col] = pd.to_numeric(sub_df[freq_col], errors="coerce").fillna(0.0)
            agg = sub_df.groupby(defect_col)[freq_col].sum().reset_index()
            agg.columns = ["Defect", "Count"]
        else:
            sub_df = df[[defect_col]].dropna().copy()
            agg = sub_df[defect_col].value_counts().reset_index()
            agg.columns = ["Defect", "Count"]

        agg["Count"] = agg["Count"].astype(float)
        agg = agg[agg["Count"] > 0].sort_values(by="Count", ascending=False).reset_index(drop=True)

        if len(agg) == 0:
            raise ValueError("No valid positive defect counts found to plot Pareto Chart.")

        total_count = float(agg["Count"].sum())
        agg["Percent"] = (agg["Count"] / total_count) * 100.0
        agg["CumCount"] = agg["Count"].cumsum()
        agg["CumPercent"] = (agg["CumCount"] / total_count) * 100.0

        # Apply Combine Threshold
        thresh = params.combine_threshold
        cutoff_idx = len(agg)

        if thresh < 100.0 and len(agg) > 3:
            for idx, cum_p in enumerate(agg["CumPercent"]):
                if cum_p >= thresh and idx < len(agg) - 1:
                    cutoff_idx = idx + 1
                    break

        main_items = agg.iloc[:cutoff_idx].copy()
        other_items = agg.iloc[cutoff_idx:].copy()

        if len(other_items) > 0:
            other_count = float(other_items["Count"].sum())
            other_percent = (other_count / total_count) * 100.0
            other_row = pd.DataFrame([{
                "Defect": params.other_label,
                "Count": other_count,
                "Percent": other_percent,
                "CumCount": total_count,
                "CumPercent": 100.0
            }])
            final_df = pd.concat([main_items, other_row], ignore_index=True)
        else:
            final_df = main_items

        # Build Session Log Table
        table_rows = []
        for _, r in final_df.iterrows():
            table_rows.append([
                str(r["Defect"]),
                f"{r['Count']:.0f}" if r["Count"].is_integer() else f"{r['Count']:.2f}",
                f"{r['Percent']:.1f}%",
                f"{r['CumPercent']:.1f}%"
            ])

        pareto_table = TableResult(
            title="Pareto Table of " + defect_col,
            headers=["Defect Category", "Count / Cost", "Percent (%)", "Cum %"],
            rows=table_rows
        )

        # Plotly Dual-Axis Figure
        categories = [str(d) for d in final_df["Defect"]]
        counts = final_df["Count"].tolist()
        cum_percents = final_df["CumPercent"].tolist()

        plotly_fig = {
            "data": [
                {
                    "type": "bar",
                    "x": categories,
                    "y": counts,
                    "name": "Count",
                    "marker": {
                        "color": "#0078d4",
                        "line": {"color": "#004d2c", "width": 1}
                    },
                    "yaxis": "y1"
                },
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": categories,
                    "y": cum_percents,
                    "name": "Cumulative %",
                    "line": {"color": "#d13438", "width": 2.5},
                    "marker": {"size": 8, "color": "#d13438", "symbol": "diamond"},
                    "yaxis": "y2"
                }
            ],
            "layout": {
                "title": f"Pareto Chart of {defect_col}",
                "xaxis": {"title": "Defect Category", "tickangle": -30 if len(categories) > 5 else 0},
                "yaxis": {
                    "title": "Count / Frequency",
                    "showgrid": True,
                    "gridcolor": "#ececec",
                    "rangemode": "tozero"
                },
                "yaxis2": {
                    "title": "Cumulative Percentage (%)",
                    "overlaying": "y",
                    "side": "right",
                    "range": [0, 105],
                    "showgrid": False,
                    "ticksuffix": "%"
                },
                "showlegend": True,
                "legend": {"orientation": "h", "y": -0.25}
            }
        }

        return AnalysisResult(
            title=f"Pareto Chart of {defect_col}",
            subtitle=f"Total Count = {total_count:.0f} across {len(final_df)} categories",
            tables=[pareto_table],
            plotly_figure=plotly_fig,
            statistics={
                "total_count": total_count,
                "num_categories": len(final_df),
                "top_category": str(final_df.iloc[0]["Defect"]),
                "top_category_pct": float(final_df.iloc[0]["Percent"])
            }
        )
