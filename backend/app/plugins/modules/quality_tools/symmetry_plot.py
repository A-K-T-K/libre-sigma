"""
Symmetry Plot Plugin for OpenMinitab Quality Tools.
Assesses distribution symmetry around sample median by plotting upper distances vs. lower distances against a 45-degree line.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class SymmetryPlotParams(BaseModel):
    data_column: str = Field(
        ...,
        description="Measurement Variable",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )


class SymmetryPlotPlugin(AnalysisPlugin):
    id = "symmetry_plot"
    name = "Symmetry Plot"
    menu_path = ["Stat", "Quality Tools", "Symmetry Plot"]
    description = "Evaluates whether sample data are distributed symmetrically about the median."
    param_schema = SymmetryPlotParams

    def execute(self, df: pd.DataFrame, params: SymmetryPlotParams) -> AnalysisResult:
        data_col = params.data_column
        if data_col not in df.columns:
            raise ValueError(f"Column '{data_col}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[data_col], errors="coerce").dropna()
        if len(raw_series) < 4:
            raise ValueError("Symmetry Plot requires at least 4 observations.")

        x = np.sort(raw_series.to_numpy(dtype=float))
        n = len(x)
        median_val = float(np.median(x))
        mean_val = float(np.mean(x))
        skew_val = float(stats.skew(x))

        m = n // 2
        # Upper distance vs Lower distance from median
        lower_dist = np.array([median_val - x[i] for i in range(m)], dtype=float)
        upper_dist = np.array([x[n - 1 - i] - median_val for i in range(m)], dtype=float)

        max_dist = float(max(np.max(lower_dist), np.max(upper_dist))) * 1.1

        # Build Session Log Table
        summary_table = TableResult(
            title="Symmetry & Distribution Shape Statistics",
            headers=["Metric", "Value", "Interpretation"],
            rows=[
                ["Sample Median", f"{median_val:.4f}", "Center reference for symmetry distances"],
                ["Sample Mean", f"{mean_val:.4f}", "Mean vs. Median difference indicates asymmetry"],
                ["Sample Skewness", f"{skew_val:.4f}", "Near 0 = Symmetric, > 0 = Right Skew, < 0 = Left Skew"],
                ["Number of Distance Pairs", str(m), "Points (Lower Distance, Upper Distance)"]
            ]
        )

        plotly_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": lower_dist.tolist(),
                    "y": upper_dist.tolist(),
                    "name": "Distance Pairs (X_lower, Y_upper)",
                    "marker": {"color": "#0078d4", "size": 7, "symbol": "circle"}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [0, max_dist],
                    "y": [0, max_dist],
                    "name": "Symmetry Reference Line (y = x)",
                    "line": {"color": "#d13438", "width": 2, "dash": "solid"}
                }
            ],
            "layout": {
                "title": f"Symmetry Plot for {data_col}",
                "xaxis": {"title": f"Lower Distance: (Median - X(i))", "showgrid": True, "gridcolor": "#ececec", "rangemode": "tozero"},
                "yaxis": {"title": f"Upper Distance: (X(n-i+1) - Median)", "showgrid": True, "gridcolor": "#ececec", "rangemode": "tozero"},
                "legend": {"orientation": "h", "y": -0.2},
                "annotations": [
                    {
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.05,
                        "y": 0.95,
                        "text": f"<b>Median:</b> {median_val:.3f}<br><b>Skewness:</b> {skew_val:.3f}",
                        "showarrow": False,
                        "bgcolor": "rgba(255,255,255,0.85)",
                        "bordercolor": "#d2d0ce",
                        "borderwidth": 1
                    }
                ]
            }
        }

        return AnalysisResult(
            title=f"Symmetry Plot for {data_col}",
            subtitle=f"Median = {median_val:.4f} | Skewness = {skew_val:.3f}",
            tables=[summary_table],
            plotly_figure=plotly_fig,
            statistics={
                "median": median_val,
                "mean": mean_val,
                "skewness": skew_val,
                "num_pairs": m
            }
        )
