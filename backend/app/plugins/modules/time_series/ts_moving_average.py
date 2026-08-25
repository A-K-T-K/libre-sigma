"""
Moving Average Plugin for OpenMinitab.
Calculates standard and centered Moving Averages, computes forecast values with MAPE/MAD/MSD, and supports worksheet storage.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class MovingAverageParams(BaseModel):
    variable: str = Field(
        ...,
        description="Variable (Series Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    ma_length: int = Field(
        3,
        ge=1,
        le=100,
        description="MA Length (Window size)"
    )
    center_ma: bool = Field(
        False,
        description="Center the moving averages"
    )
    generate_forecasts: bool = Field(
        True,
        description="Generate Forecasts"
    )
    n_forecasts: int = Field(
        6,
        ge=1,
        le=50,
        description="Number of Forecasts"
    )
    # Storage Sub-Modal
    store_smoothed: bool = Field(
        False,
        description="Store Smoothed Values in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_forecasts: bool = Field(
        False,
        description="Store Forecasts in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_residuals: bool = Field(
        False,
        description="Store Residuals in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )


class MovingAveragePlugin(AnalysisPlugin):
    id = "ts_moving_average"
    name = "Moving Average"
    menu_path = ["Stat", "Time Series", "Moving Average"]
    description = "Smooths data by averaging consecutive values across a moving window with forecasting capability."
    param_schema = MovingAverageParams

    def execute(self, df: pd.DataFrame, params: MovingAverageParams) -> AnalysisResult:
        var_name = params.variable
        if var_name not in df.columns:
            raise ValueError(f"Column '{var_name}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[var_name], errors="coerce").dropna()
        n = len(raw_series)
        k = params.ma_length

        if n < k:
            raise ValueError(f"Series has {n} observations, which is less than MA length ({k}).")

        y = raw_series.to_numpy(dtype=float)
        t = np.arange(1, n + 1, dtype=int)

        # Compute MA
        series_pd = pd.Series(y)
        if params.center_ma:
            smoothed = series_pd.rolling(window=k, center=True).mean().to_numpy()
        else:
            smoothed = series_pd.rolling(window=k).mean().to_numpy()

        # Fits & Residuals for non-centered standard MA
        fits = np.roll(smoothed, 1)
        fits[0] = np.nan
        valid_mask = ~np.isnan(fits) & ~np.isnan(y)
        residuals = np.where(valid_mask, y - fits, np.nan)

        valid_resids = residuals[valid_mask]
        valid_y = y[valid_mask]

        if len(valid_resids) > 0:
            mape = float(np.mean(np.abs(valid_resids / np.where(valid_y != 0, valid_y, 1e-6))) * 100.0)
            mad = float(np.mean(np.abs(valid_resids)))
            msd = float(np.mean(valid_resids ** 2))
        else:
            mape, mad, msd = 0.0, 0.0, 0.0

        # Forecasts
        n_fc = params.n_forecasts if params.generate_forecasts else 0
        last_ma = float(np.nanmean(y[-k:]))
        forecast_vals = [last_ma] * n_fc
        t_fc = [n + 1 + i for i in range(n_fc)]

        # Plotly chart
        traces = [
            {
                "x": t.tolist(),
                "y": y.tolist(),
                "mode": "lines+markers",
                "name": "Actual",
                "line": {"color": "#005a9e", "width": 2},
                "marker": {"size": 6, "color": "#005a9e"}
            },
            {
                "x": t.tolist(),
                "y": [None if np.isnan(v) else round(float(v), 4) for v in smoothed],
                "mode": "lines",
                "name": f"Smoothed (MA={k})",
                "line": {"color": "#008450", "width": 2}
            }
        ]

        if n_fc > 0:
            traces.append({
                "x": t_fc,
                "y": forecast_vals,
                "mode": "lines+markers",
                "name": "Forecast",
                "line": {"color": "#d13438", "width": 2, "dash": "dash"},
                "marker": {"size": 6, "symbol": "diamond", "color": "#d13438"}
            })

        layout = {
            "title": {"text": f"<b>Moving Average Plot for {var_name}</b><br><span style='font-size:11px;color:#605e5c'>MA Length = {k}{' (Centered)' if params.center_ma else ''}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Index / Time (t)", "showgrid": True, "gridcolor": "#f3f2f1", "linecolor": "#201f1e"},
            "yaxis": {"title": var_name, "showgrid": True, "gridcolor": "#f3f2f1", "linecolor": "#201f1e"},
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 55, "r": 30, "t": 60, "b": 55},
            "hovermode": "x unified"
        }

        # Tables
        acc_table = TableResult(
            title="Accuracy Measures",
            headers=["Measure", "Value"],
            rows=[
                ["MAPE (Mean Absolute Percentage Error)", f"{mape:.4f}%"],
                ["MAD (Mean Absolute Deviation)", f"{mad:.4f}"],
                ["MSD (Mean Squared Deviation)", f"{msd:.4f}"]
            ]
        )

        fc_rows = [[t_fc[i], round(float(forecast_vals[i]), 4)] for i in range(n_fc)]
        tables = [acc_table]
        if n_fc > 0:
            tables.append(TableResult(
                title=f"Forecasts ({n_fc} Periods Ahead)",
                headers=["Period", "Forecast"],
                rows=fc_rows
            ))

        text_lines = [
            f"Moving Average for {var_name}",
            f"Length: {k} {'(Centered)' if params.center_ma else ''}",
            "",
            "Accuracy Measures:",
            f"  MAPE : {mape:.4f}%",
            f"  MAD  : {mad:.4f}",
            f"  MSD  : {msd:.4f}",
        ]
        if n_fc > 0:
            text_lines.append("")
            text_lines.append("Forecasts:")
            for r in fc_rows:
                text_lines.append(f"  Period {r[0]:<6} : {r[1]:>12.4f}")

        # Worksheet Storage
        storage_cols = []
        new_cols_dict: Dict[str, List[Any]] = {}

        if params.store_smoothed:
            storage_cols.append({"id": f"smooth_{var_name.lower()}", "name": f"SMOOTH_{var_name}", "type": "numeric"})
            new_cols_dict[f"smooth_{var_name.lower()}"] = [None if np.isnan(v) else round(float(v), 4) for v in smoothed]

        if params.store_residuals:
            storage_cols.append({"id": f"resi_{var_name.lower()}", "name": f"RESI_{var_name}", "type": "numeric"})
            new_cols_dict[f"resi_{var_name.lower()}"] = [None if np.isnan(v) else round(float(v), 4) for v in residuals]

        if params.store_forecasts and n_fc > 0:
            storage_cols.append({"id": f"fore_{var_name.lower()}", "name": f"FORE_{var_name}", "type": "numeric"})
            new_cols_dict[f"fore_{var_name.lower()}"] = [None] * n + [round(float(v), 4) for v in forecast_vals]

        action_type = None
        worksheet_data = None
        if storage_cols:
            max_r = max(n, n + n_fc)
            rows_data = []
            for r_i in range(max_r):
                r_dict = {}
                for col_spec in storage_cols:
                    c_id = col_spec["id"]
                    val_list = new_cols_dict.get(c_id, [])
                    r_dict[c_id] = val_list[r_i] if r_i < len(val_list) else None
                rows_data.append(r_dict)

            action_type = "worksheet_append_columns"
            worksheet_data = {"columns": storage_cols, "rows": rows_data}

        return AnalysisResult(
            title="Moving Average",
            subtitle=f"MA({k}) Smoothing for {var_name}",
            text_output="\n".join(text_lines),
            tables=tables,
            plotly_figure={"data": traces, "layout": layout},
            action_type=action_type,
            worksheet_data=worksheet_data
        )
