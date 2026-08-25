"""
Time Series Decomposition Plugin for OpenMinitab.
Performs Classical Additive and Multiplicative seasonal decomposition.
Generates 4-panel decomposition charts, Seasonal Indices table, accuracy measures, and future forecasts.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import seasonal_decompose
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class DecompositionParams(BaseModel):
    variable: str = Field(
        ...,
        description="Variable (Series Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    seasonal_length: int = Field(
        12,
        ge=2,
        le=365,
        description="Seasonal Length (e.g. 4 for Quarterly, 12 for Monthly)"
    )
    model_type: str = Field(
        "multiplicative",
        description="Model Type",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Multiplicative (Y = Trend × Seasonal × Irregular)", "value": "multiplicative"},
                {"label": "Additive (Y = Trend + Seasonal + Irregular)", "value": "additive"}
            ]
        }
    )
    model_components: str = Field(
        "trend_seasonal",
        description="Model Components",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Trend plus Seasonal", "value": "trend_seasonal"},
                {"label": "Seasonal only", "value": "seasonal_only"}
            ]
        }
    )
    n_forecasts: int = Field(
        12,
        ge=0,
        le=100,
        description="Number of Forecast Periods"
    )
    # Storage Sub-Modal
    store_trend: bool = Field(
        False,
        description="Store Trend Line",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_seasonal: bool = Field(
        False,
        description="Store Seasonal Indices",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_deseasonalized: bool = Field(
        False,
        description="Store Deseasonalized Data",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_fits: bool = Field(
        False,
        description="Store Fits",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_residuals: bool = Field(
        False,
        description="Store Residuals",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_forecasts: bool = Field(
        False,
        description="Store Forecasts",
        json_schema_extra={"sub_modal": "Storage..."}
    )


class DecompositionPlugin(AnalysisPlugin):
    id = "ts_decomposition"
    name = "Decomposition"
    menu_path = ["Stat", "Time Series", "Decomposition"]
    description = "Decomposes a time series into Trend, Seasonal, and Irregular/Noise components with seasonal indices and forecasting."
    param_schema = DecompositionParams

    def execute(self, df: pd.DataFrame, params: DecompositionParams) -> AnalysisResult:
        var_name = params.variable
        if var_name not in df.columns:
            raise ValueError(f"Column '{var_name}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[var_name], errors="coerce").dropna()
        n = len(raw_series)
        s_len = max(2, params.seasonal_length)

        if n < 2 * s_len:
            raise ValueError(f"Decomposition requires at least 2 full seasonal cycles (at least {2 * s_len} observations).")

        y = raw_series.to_numpy(dtype=float)
        if params.model_type == "multiplicative" and np.any(y <= 0):
            raise ValueError("Multiplicative decomposition requires all strictly positive values.")

        t = np.arange(1, n + 1, dtype=float)

        # Decompose using statsmodels
        res = seasonal_decompose(y, model=params.model_type, period=s_len, extrapolate_trend="freq")
        trend_comp = np.array(res.trend, dtype=float)
        seasonal_comp = np.array(res.seasonal, dtype=float)
        resid_comp = np.array(res.resid, dtype=float)

        # Seasonal Indices (average index per period in season)
        indices_list = []
        for p in range(s_len):
            idx_vals = seasonal_comp[p::s_len]
            indices_list.append(float(np.mean(idx_vals)))

        # Deseasonalized Data
        if params.model_type == "multiplicative":
            deseasonalized = y / np.where(seasonal_comp != 0, seasonal_comp, 1e-6)
            fits = trend_comp * seasonal_comp
        else:
            deseasonalized = y - seasonal_comp
            fits = trend_comp + seasonal_comp

        residuals = y - fits

        # Fit trend equation on deseasonalized or raw data
        poly = np.polyfit(t, deseasonalized if params.model_components == "trend_seasonal" else y, 1)
        b1, b0 = poly[0], poly[1]
        sign1 = "+" if b1 >= 0 else "-"
        eq_str = f"Trend Line: Yt = {b0:.5g} {sign1} {abs(b1):.5g} × t"

        # Accuracy
        mape = float(np.mean(np.abs(residuals / np.where(y != 0, y, 1e-6))) * 100.0)
        mad = float(np.mean(np.abs(residuals)))
        msd = float(np.mean(residuals ** 2))

        # Future forecasts
        n_fc = params.n_forecasts
        t_fc = np.arange(n + 1, n + n_fc + 1, dtype=float)
        forecast_vals = []
        for idx, t_val in enumerate(t_fc):
            trend_val = b0 + b1 * t_val if params.model_components == "trend_seasonal" else float(np.mean(y))
            season_idx = indices_list[int((t_val - 1) % s_len)]
            if params.model_type == "multiplicative":
                fc_val = trend_val * season_idx
            else:
                fc_val = trend_val + season_idx
            forecast_vals.append(fc_val)

        forecast_vals = np.array(forecast_vals, dtype=float)

        # 4-Panel Plotly Figure (Original, Trend, Seasonal, Noise)
        x_axis_all = [int(i) for i in t]
        x_fc = [int(i) for i in t_fc]

        traces = [
            # 1. Original vs Fits
            {"x": x_axis_all, "y": y.tolist(), "mode": "lines+markers", "name": "Actual Data", "xaxis": "x", "yaxis": "y", "line": {"color": "#005a9e"}},
            {"x": x_axis_all, "y": fits.tolist(), "mode": "lines", "name": "Fits", "xaxis": "x", "yaxis": "y", "line": {"color": "#008450", "dash": "solid"}},
            # 2. Trend
            {"x": x_axis_all, "y": trend_comp.tolist(), "mode": "lines", "name": "Trend Component", "xaxis": "x2", "yaxis": "y2", "line": {"color": "#d13438", "width": 2}},
            # 3. Seasonal
            {"x": x_axis_all, "y": seasonal_comp.tolist(), "mode": "lines", "name": "Seasonal Component", "xaxis": "x3", "yaxis": "y3", "line": {"color": "#8764b8"}},
            # 4. Irregular / Residual
            {"x": x_axis_all, "y": resid_comp.tolist(), "mode": "lines+markers", "name": "Irregular / Residual", "xaxis": "x4", "yaxis": "y4", "line": {"color": "#ffaa44"}}
        ]

        if n_fc > 0:
            traces.append({
                "x": x_fc,
                "y": forecast_vals.tolist(),
                "mode": "lines+markers",
                "name": "Forecasts",
                "xaxis": "x",
                "yaxis": "y",
                "line": {"color": "#d13438", "dash": "dash"},
                "marker": {"symbol": "diamond", "size": 6}
            })

        layout = {
            "title": {"text": f"<b>Time Series Decomposition Plot for {var_name}</b><br><span style='font-size:11px;color:#605e5c'>{params.model_type.capitalize()} Model (Period = {s_len})</span>", "font": {"size": 13, "color": "#201f1e"}},
            "grid": {"rows": 4, "columns": 1, "pattern": "independent"},
            "xaxis": {"title": "Original & Fits", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Actual", "showgrid": True, "gridcolor": "#f3f2f1"},
            "xaxis2": {"title": "Trend Component", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis2": {"title": "Trend", "showgrid": True, "gridcolor": "#f3f2f1"},
            "xaxis3": {"title": "Seasonal Component", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis3": {"title": "Seasonal", "showgrid": True, "gridcolor": "#f3f2f1"},
            "xaxis4": {"title": "Irregular Component", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis4": {"title": "Irregular", "showgrid": True, "gridcolor": "#f3f2f1"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "showlegend": True,
            "legend": {"orientation": "h", "y": -0.15, "x": 0.5, "xanchor": "center"},
            "margin": {"l": 55, "r": 30, "t": 65, "b": 60}
        }

        # Tables
        season_rows = [[f"Period {p + 1}", round(float(indices_list[p]), 5)] for p in range(s_len)]
        season_table = TableResult(
            title=f"Seasonal Indices ({params.model_type.capitalize()})",
            headers=["Period", "Seasonal Index"],
            rows=season_rows
        )

        acc_table = TableResult(
            title="Accuracy Measures",
            headers=["Measure", "Value"],
            rows=[
                ["MAPE (Mean Absolute Percentage Error)", f"{mape:.4f}%"],
                ["MAD (Mean Absolute Deviation)", f"{mad:.4f}"],
                ["MSD (Mean Squared Deviation)", f"{msd:.4f}"]
            ]
        )

        fc_rows = [[int(t_fc[i]), round(float(forecast_vals[i]), 4)] for i in range(n_fc)]
        tables = [season_table, acc_table]
        if n_fc > 0:
            tables.append(TableResult(
                title=f"Forecasts ({n_fc} Periods)",
                headers=["Period", "Forecast"],
                rows=fc_rows
            ))

        text_lines = [
            f"Time Series Decomposition for {var_name}",
            f"Model Type: {params.model_type.capitalize()} | Seasonal Length: {s_len}",
            "",
            eq_str,
            "",
            "Seasonal Indices:",
        ]
        for r in season_rows:
            text_lines.append(f"  {r[0]:<12} {r[1]:>12.5f}")
        text_lines += [
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

        if params.store_trend:
            storage_cols.append({"id": f"trend_{var_name.lower()}", "name": f"TREND_{var_name}", "type": "numeric"})
            new_cols_dict[f"trend_{var_name.lower()}"] = [round(float(v), 4) for v in trend_comp]

        if params.store_seasonal:
            storage_cols.append({"id": f"seas_{var_name.lower()}", "name": f"SEAS_{var_name}", "type": "numeric"})
            new_cols_dict[f"seas_{var_name.lower()}"] = [round(float(v), 4) for v in seasonal_comp]

        if params.store_deseasonalized:
            storage_cols.append({"id": f"deseas_{var_name.lower()}", "name": f"DESEAS_{var_name}", "type": "numeric"})
            new_cols_dict[f"deseas_{var_name.lower()}"] = [round(float(v), 4) for v in deseasonalized]

        if params.store_fits:
            storage_cols.append({"id": f"fits_{var_name.lower()}", "name": f"FITS_{var_name}", "type": "numeric"})
            new_cols_dict[f"fits_{var_name.lower()}"] = [round(float(v), 4) for v in fits]

        if params.store_residuals:
            storage_cols.append({"id": f"resi_{var_name.lower()}", "name": f"RESI_{var_name}", "type": "numeric"})
            new_cols_dict[f"resi_{var_name.lower()}"] = [round(float(v), 4) for v in residuals]

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
            title="Time Series Decomposition",
            subtitle=f"{params.model_type.capitalize()} Decomposition for {var_name}",
            text_output="\n".join(text_lines),
            tables=tables,
            plotly_figure={"data": traces, "layout": layout},
            action_type=action_type,
            worksheet_data=worksheet_data
        )
