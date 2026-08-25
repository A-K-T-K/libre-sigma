"""
Time Series Plot Plugin for OpenMinitab.
Supports Simple, Multiple, and Grouped time series plots with custom time scales, reference lines, and interactive Plotly visualization.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class TimeSeriesPlotParams(BaseModel):
    variables: List[str] = Field(
        ...,
        description="Series / Variables (Y)",
        json_schema_extra={"ui_type": "column_multi_picker", "data_type": "numeric"}
    )
    plot_type: str = Field(
        "simple",
        description="Plot Type",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Simple (Single or Overlay Series)", "value": "simple"},
                {"label": "Multiple Panels (Separate subplots)", "value": "multiple"},
                {"label": "With Groups (Stratified by Category)", "value": "groups"}
            ]
        }
    )
    group_variable: Optional[str] = Field(
        None,
        description="Grouping Variable (for 'With Groups')",
        json_schema_extra={"ui_type": "column_picker"}
    )
    # Time Scale Sub-Modal
    time_scale_type: str = Field(
        "index",
        description="Time Scale / X-Axis",
        json_schema_extra={
            "ui_type": "select",
            "sub_modal": "Time Scale...",
            "options": [
                {"label": "Index (1, 2, 3...)", "value": "index"},
                {"label": "Date / Time Column", "value": "date_col"},
                {"label": "Calendar (Year / Month / Quarter)", "value": "calendar"}
            ]
        }
    )
    time_column: Optional[str] = Field(
        None,
        description="Date / Time Column",
        json_schema_extra={"ui_type": "column_picker", "sub_modal": "Time Scale..."}
    )
    start_period: int = Field(
        1,
        description="Start Period / Year",
        json_schema_extra={"sub_modal": "Time Scale..."}
    )
    calendar_unit: str = Field(
        "month",
        description="Calendar Frequency",
        json_schema_extra={
            "ui_type": "select",
            "sub_modal": "Time Scale...",
            "options": [
                {"label": "Month (1-12)", "value": "month"},
                {"label": "Quarter (1-4)", "value": "quarter"},
                {"label": "Day (1-365)", "value": "day"},
                {"label": "Yearly", "value": "year"}
            ]
        }
    )
    # Graph Options Sub-Modal
    show_markers: bool = Field(
        True,
        description="Show Point Markers",
        json_schema_extra={"sub_modal": "Graph Options..."}
    )
    line_style: str = Field(
        "solid",
        description="Line Style",
        json_schema_extra={
            "ui_type": "select",
            "sub_modal": "Graph Options...",
            "options": [
                {"label": "Solid Line", "value": "solid"},
                {"label": "Dashed Line", "value": "dash"},
                {"label": "Dotted Line", "value": "dot"},
                {"label": "Step Line", "value": "hv"}
            ]
        }
    )
    reference_lines: Optional[str] = Field(
        None,
        description="Reference Lines Y-Values (comma-separated, e.g. 100, 150)",
        json_schema_extra={"sub_modal": "Graph Options..."}
    )
    custom_title: Optional[str] = Field(
        None,
        description="Custom Chart Title",
        json_schema_extra={"sub_modal": "Graph Options..."}
    )


class TimeSeriesPlotPlugin(AnalysisPlugin):
    id = "ts_plot"
    name = "Time Series Plot"
    menu_path = ["Stat", "Time Series", "Time Series Plot"]
    description = "Plots one or more time series across time indices, dates, or grouped factors with custom reference lines."
    param_schema = TimeSeriesPlotParams

    def execute(self, df: pd.DataFrame, params: TimeSeriesPlotParams) -> AnalysisResult:
        if not params.variables:
            raise ValueError("Select at least one variable to plot.")

        for v in params.variables:
            if v not in df.columns:
                raise ValueError(f"Column '{v}' not found in active worksheet.")

        n_rows = len(df)
        if n_rows == 0:
            raise ValueError("Active worksheet is empty.")

        # Resolve X axis values
        x_vals = []
        x_title = "Index"
        if params.time_scale_type == "date_col" and params.time_column and params.time_column in df.columns:
            x_vals = df[params.time_column].astype(str).tolist()
            x_title = params.time_column
        elif params.time_scale_type == "calendar":
            x_title = f"Time ({params.calendar_unit.capitalize()})"
            start = params.start_period
            if params.calendar_unit == "month":
                x_vals = [f"M{(i % 12) + 1}-{(start + i // 12)}" for i in range(n_rows)]
            elif params.calendar_unit == "quarter":
                x_vals = [f"Q{(i % 4) + 1}-{(start + i // 4)}" for i in range(n_rows)]
            elif params.calendar_unit == "year":
                x_vals = [f"Year {start + i}" for i in range(n_rows)]
            else:
                x_vals = [f"Day {start + i}" for i in range(n_rows)]
        else:
            x_vals = list(range(1, n_rows + 1))
            x_title = "Index"

        # Build Plotly traces
        colors = ["#008450", "#005a9e", "#d13438", "#8764b8", "#ffaa44", "#00b7c3", "#744da9", "#498205"]
        traces = []
        summary_rows = []

        plot_mode = "lines+markers" if params.show_markers else "lines"

        if params.plot_type == "groups" and params.group_variable and params.group_variable in df.columns:
            grp_col = params.group_variable
            unique_groups = df[grp_col].dropna().unique()
            y_col = params.variables[0]

            for g_idx, grp_val in enumerate(unique_groups):
                mask = df[grp_col] == grp_val
                grp_df = df[mask]
                y_series = pd.to_numeric(grp_df[y_col], errors="coerce")
                valid_mask = y_series.notna()
                sub_x = [x_vals[i] for i in grp_df.index[valid_mask]]
                sub_y = y_series[valid_mask].tolist()

                col_color = colors[g_idx % len(colors)]
                line_dict = {"color": col_color, "width": 2}
                if params.line_style in ["dash", "dot"]:
                    line_dict["dash"] = params.line_style
                elif params.line_style == "hv":
                    line_dict["shape"] = "hv"

                traces.append({
                    "x": sub_x,
                    "y": sub_y,
                    "mode": plot_mode,
                    "name": f"{grp_col}={grp_val}",
                    "line": line_dict,
                    "marker": {"size": 6, "color": col_color}
                })

                if len(sub_y) > 0:
                    summary_rows.append([
                        f"{y_col} ({grp_val})",
                        len(sub_y),
                        round(float(np.mean(sub_y)), 4),
                        round(float(np.std(sub_y, ddof=1)) if len(sub_y) > 1 else 0.0, 4),
                        round(float(np.min(sub_y)), 4),
                        round(float(np.max(sub_y)), 4)
                    ])
        else:
            for idx, var_name in enumerate(params.variables):
                series = pd.to_numeric(df[var_name], errors="coerce")
                valid_idx = series.notna()
                sub_x = [x_vals[i] for i in range(len(series)) if valid_idx.iloc[i]]
                sub_y = series[valid_idx].tolist()

                col_color = colors[idx % len(colors)]
                line_dict = {"color": col_color, "width": 2}
                if params.line_style in ["dash", "dot"]:
                    line_dict["dash"] = params.line_style
                elif params.line_style == "hv":
                    line_dict["shape"] = "hv"

                traces.append({
                    "x": sub_x,
                    "y": sub_y,
                    "mode": plot_mode,
                    "name": var_name,
                    "line": line_dict,
                    "marker": {"size": 6, "color": col_color}
                })

                if len(sub_y) > 0:
                    summary_rows.append([
                        var_name,
                        len(sub_y),
                        round(float(np.mean(sub_y)), 4),
                        round(float(np.std(sub_y, ddof=1)) if len(sub_y) > 1 else 0.0, 4),
                        round(float(np.min(sub_y)), 4),
                        round(float(np.max(sub_y)), 4)
                    ])

        # Shapes / Reference Lines
        shapes = []
        if params.reference_lines:
            for ref_str in params.reference_lines.split(","):
                try:
                    ref_val = float(ref_str.strip())
                    shapes.append({
                        "type": "line",
                        "xref": "paper",
                        "x0": 0,
                        "x1": 1,
                        "y0": ref_val,
                        "y1": ref_val,
                        "line": {"color": "#d13438", "width": 1.5, "dash": "dash"}
                    })
                except ValueError:
                    pass

        chart_title = params.custom_title or (
            f"Time Series Plot of {', '.join(params.variables)}"
        )

        layout = {
            "title": {"text": f"<b>{chart_title}</b>", "font": {"size": 14, "color": "#201f1e"}},
            "xaxis": {
                "title": x_title,
                "showgrid": True,
                "gridcolor": "#f3f2f1",
                "linecolor": "#201f1e",
                "zeroline": False,
            },
            "yaxis": {
                "title": "Values",
                "showgrid": True,
                "gridcolor": "#f3f2f1",
                "linecolor": "#201f1e",
                "zeroline": False,
            },
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "shapes": shapes,
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 55, "r": 30, "t": 45, "b": 55},
            "hovermode": "x unified"
        }

        text_lines = [
            "Time Series Plot",
            "",
            f"Variables: {', '.join(params.variables)}",
            f"Time scale: {params.time_scale_type.capitalize()}",
            "",
            f"  {'Variable':<20} {'N':>6} {'Mean':>12} {'StDev':>12} {'Min':>12} {'Max':>12}",
            f"  {'-'*20} {'-'*6} {'-'*12} {'-'*12} {'-'*12} {'-'*12}",
        ]
        for r in summary_rows:
            text_lines.append(f"  {r[0]:<20} {r[1]:>6} {r[2]:>12.4f} {r[3]:>12.4f} {r[4]:>12.4f} {r[5]:>12.4f}")

        return AnalysisResult(
            title="Time Series Plot",
            subtitle=f"Series: {', '.join(params.variables)}",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(
                    title="Series Summary Statistics",
                    headers=["Variable", "N", "Mean", "StDev", "Min", "Max"],
                    rows=summary_rows
                )
            ],
            plotly_figure={"data": traces, "layout": layout}
        )
