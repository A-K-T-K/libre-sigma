"""
Double Exponential Smoothing Plugin for OpenMinitab (Holt's Linear Trend).
Fits Holt's linear exponential smoothing model with automated optimization or user-specified Alpha (Level) and Gamma (Trend).
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import Holt
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class DoubleExpSmoothingParams(BaseModel):
    variable: str = Field(
        ...,
        description="Variable (Series Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    weight_type: str = Field(
        "optimize",
        description="Weights to Use",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Optimize (Optimal Alpha & Gamma)", "value": "optimize"},
                {"label": "User-Specified Weights", "value": "user"}
            ]
        }
    )
    user_alpha: float = Field(
        0.2,
        ge=0.0001,
        le=1.0,
        description="User Alpha (α - Level)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    user_gamma: float = Field(
        0.1,
        ge=0.0001,
        le=1.0,
        description="User Gamma (γ - Trend)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    generate_forecasts: bool = Field(
        True,
        description="Generate Forecasts"
    )
    n_forecasts: int = Field(
        6,
        ge=1,
        le=100,
        description="Number of Forecast Periods (Lead Time)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    # Storage Sub-Modal
    store_smoothed: bool = Field(
        False,
        description="Store Smoothed / Fits",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_level: bool = Field(
        False,
        description="Store Level Estimates",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_trend: bool = Field(
        False,
        description="Store Trend Estimates",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_forecasts: bool = Field(
        False,
        description="Store Forecasts",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_residuals: bool = Field(
        False,
        description="Store Residuals",
        json_schema_extra={"sub_modal": "Storage..."}
    )


class DoubleExpSmoothingPlugin(AnalysisPlugin):
    id = "ts_double_exp_smoothing"
    name = "Double Exp Smoothing"
    menu_path = ["Stat", "Time Series", "Double Exp Smoothing"]
    description = "Holt's linear exponential smoothing for time series data exhibiting a linear trend."
    param_schema = DoubleExpSmoothingParams

    def execute(self, df: pd.DataFrame, params: DoubleExpSmoothingParams) -> AnalysisResult:
        var_name = params.variable
        if var_name not in df.columns:
            raise ValueError(f"Column '{var_name}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[var_name], errors="coerce").dropna()
        n = len(raw_series)
        if n < 4:
            raise ValueError("Double Exponential Smoothing requires at least 4 observations.")

        y = raw_series.to_numpy(dtype=float)
        t = np.arange(1, n + 1, dtype=int)

        # Fit Holt's Linear Trend Model
        model = Holt(y, initialization_method="estimated")
        if params.weight_type == "user":
            fit_res = model.fit(
                smoothing_level=params.user_alpha,
                smoothing_trend=params.user_gamma,
                optimized=False
            )
            alpha_val = params.user_alpha
            gamma_val = params.user_gamma
        else:
            fit_res = model.fit(optimized=True)
            alpha_val = float(fit_res.params.get("smoothing_level", 0.2))
            gamma_val = float(fit_res.params.get("smoothing_trend", 0.1))

        smoothed = np.array(fit_res.fittedvalues, dtype=float)
        level_vals = np.array(fit_res.level, dtype=float) if hasattr(fit_res, "level") else smoothed
        trend_vals = np.array(fit_res.trend, dtype=float) if hasattr(fit_res, "trend") else np.zeros(n)
        residuals = y - smoothed

        # Accuracy
        mape = float(np.mean(np.abs(residuals / np.where(y != 0, y, 1e-6))) * 100.0)
        mad = float(np.mean(np.abs(residuals)))
        msd = float(np.mean(residuals ** 2))

        # Forecasts
        n_fc = params.n_forecasts if params.generate_forecasts else 0
        forecast_vals = np.array(fit_res.forecast(n_fc), dtype=float) if n_fc > 0 else np.array([])
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
                "y": [round(float(v), 4) for v in smoothed],
                "mode": "lines",
                "name": f"Fitted Trend (α={alpha_val:.3f}, γ={gamma_val:.3f})",
                "line": {"color": "#008450", "width": 2}
            }
        ]

        if n_fc > 0:
            traces.append({
                "x": t_fc,
                "y": [round(float(v), 4) for v in forecast_vals],
                "mode": "lines+markers",
                "name": "Forecast",
                "line": {"color": "#d13438", "width": 2, "dash": "dash"},
                "marker": {"size": 6, "symbol": "diamond", "color": "#d13438"}
            })

        layout = {
            "title": {"text": f"<b>Double Exponential Smoothing Plot for {var_name}</b><br><span style='font-size:11px;color:#605e5c'>Alpha (α) = {alpha_val:.4f}, Gamma (γ) = {gamma_val:.4f}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Index / Time (t)", "showgrid": True, "gridcolor": "#f3f2f1", "linecolor": "#201f1e"},
            "yaxis": {"title": var_name, "showgrid": True, "gridcolor": "#f3f2f1", "linecolor": "#201f1e"},
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 55, "r": 30, "t": 60, "b": 55},
            "hovermode": "x unified"
        }

        # Tables
        param_table = TableResult(
            title="Smoothing Constants",
            headers=["Parameter", "Estimate"],
            rows=[
                ["Alpha (α - Level)", f"{alpha_val:.5f}"],
                ["Gamma (γ - Trend)", f"{gamma_val:.5f}"]
            ]
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

        fc_rows = [[t_fc[i], round(float(forecast_vals[i]), 4)] for i in range(n_fc)]
        tables = [param_table, acc_table]
        if n_fc > 0:
            tables.append(TableResult(
                title=f"Forecasts ({n_fc} Periods Ahead)",
                headers=["Period", "Forecast"],
                rows=fc_rows
            ))

        text_lines = [
            f"Double Exponential Smoothing for {var_name}",
            "",
            "Smoothing Constants:",
            f"  Alpha (α - Level) : {alpha_val:.5f}",
            f"  Gamma (γ - Trend) : {gamma_val:.5f}",
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
            storage_cols.append({"id": f"smooth_{var_name.lower()}", "name": f"FITS_{var_name}", "type": "numeric"})
            new_cols_dict[f"smooth_{var_name.lower()}"] = [round(float(v), 4) for v in smoothed]

        if params.store_level:
            storage_cols.append({"id": f"level_{var_name.lower()}", "name": f"LEVEL_{var_name}", "type": "numeric"})
            new_cols_dict[f"level_{var_name.lower()}"] = [round(float(v), 4) for v in level_vals]

        if params.store_trend:
            storage_cols.append({"id": f"trend_{var_name.lower()}", "name": f"TREND_{var_name}", "type": "numeric"})
            new_cols_dict[f"trend_{var_name.lower()}"] = [round(float(v), 4) for v in trend_vals]

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
            title="Double Exponential Smoothing",
            subtitle=f"Holt's Trend Model for {var_name}",
            text_output="\n".join(text_lines),
            tables=tables,
            plotly_figure={"data": traces, "layout": layout},
            action_type=action_type,
            worksheet_data=worksheet_data
        )
