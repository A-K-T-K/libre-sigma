"""
Differences Plugin for OpenMinitab Time Series.
Calculates consecutive or lag-d differences of a series and appends the new differenced column directly to the active worksheet.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class DifferencesParams(BaseModel):
    variable: str = Field(
        ...,
        description="Series / Variable",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    diff_order: int = Field(
        1,
        ge=1,
        le=50,
        description="Differencing Order (Lag)"
    )
    store_column_name: str = Field(
        "Diff_1",
        description="Store Differences in (Column Name)"
    )


class DifferencesPlugin(AnalysisPlugin):
    id = "ts_differences"
    name = "Differences"
    menu_path = ["Stat", "Time Series", "Differences"]
    description = "Calculates lag-d differences (Yt - Yt-d) and appends the differenced numeric column directly into the active worksheet."
    param_schema = DifferencesParams

    def execute(self, df: pd.DataFrame, params: DifferencesParams) -> AnalysisResult:
        var_name = params.variable
        if var_name not in df.columns:
            raise ValueError(f"Column '{var_name}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[var_name], errors="coerce")
        n = len(raw_series)
        lag = params.diff_order

        if lag >= n:
            raise ValueError(f"Differencing order ({lag}) cannot be greater than or equal to sample size ({n}).")

        diff_series = raw_series.diff(periods=lag)

        col_name = params.store_column_name.strip() or f"Diff_{var_name}_lag{lag}"
        col_id = f"diff_{var_name.lower()}_{lag}"

        # Summary statistics
        clean_diff = diff_series.dropna().to_numpy(dtype=float)
        mean_diff = float(np.mean(clean_diff)) if len(clean_diff) > 0 else 0.0
        stdev_diff = float(np.std(clean_diff, ddof=1)) if len(clean_diff) > 1 else 0.0
        min_diff = float(np.min(clean_diff)) if len(clean_diff) > 0 else 0.0
        max_diff = float(np.max(clean_diff)) if len(clean_diff) > 0 else 0.0

        # Plotly trace
        x_indices = list(range(1, n + 1))
        traces = [
            {
                "x": x_indices,
                "y": [None if np.isnan(v) else round(float(v), 4) for v in diff_series],
                "mode": "lines+markers",
                "name": col_name,
                "line": {"color": "#008450", "width": 1.5},
                "marker": {"size": 5, "color": "#008450"}
            }
        ]

        layout = {
            "title": {"text": f"<b>Differenced Series: {col_name} (Order = {lag})</b>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Index", "showgrid": True, "gridcolor": "#f3f2f1", "linecolor": "#201f1e"},
            "yaxis": {"title": "Differenced Value", "showgrid": True, "gridcolor": "#f3f2f1", "linecolor": "#201f1e"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 55, "r": 30, "t": 50, "b": 50}
        }

        table = TableResult(
            title=f"Differenced Series Summary ({col_name})",
            headers=["Variable", "Lag Order", "N Calculated", "Mean", "StDev", "Min", "Max"],
            rows=[
                [var_name, lag, len(clean_diff), round(mean_diff, 4), round(stdev_diff, 4), round(min_diff, 4), round(max_diff, 4)]
            ]
        )

        text_lines = [
            f"Differences for {var_name}",
            f"Lag: {lag} | Output Column: {col_name}",
            "",
            f"  Calculated {len(clean_diff)} differenced values.",
            f"  Mean  : {mean_diff:.4f}",
            f"  StDev : {stdev_diff:.4f}",
            f"  Min   : {min_diff:.4f}",
            f"  Max   : {max_diff:.4f}",
            "",
            f"Appended column '{col_name}' directly into active worksheet."
        ]

        # Prepare storage
        storage_cols = [{"id": col_id, "name": col_name, "type": "numeric"}]
        rows_data = []
        for v in diff_series:
            rows_data.append({col_id: None if pd.isna(v) else round(float(v), 5)})

        return AnalysisResult(
            title="Differences",
            subtitle=f"Lag {lag} Differencing of {var_name}",
            text_output="\n".join(text_lines),
            tables=[table],
            plotly_figure={"data": traces, "layout": layout},
            action_type="worksheet_append_columns",
            worksheet_data={"columns": storage_cols, "rows": rows_data}
        )
