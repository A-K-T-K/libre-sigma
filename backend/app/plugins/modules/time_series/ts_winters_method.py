"""
Winters' Method (Triple Exponential Smoothing) Plugin for OpenMinitab.
Fits Additive and Multiplicative Holt-Winters models accounting for Level (Alpha), Trend (Gamma), and Seasonal (Delta) components.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class WintersMethodParams(BaseModel):
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
    method_type: str = Field(
        "multiplicative",
        description="Method / Type",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Multiplicative (Seasonal amplitude proportional to level)", "value": "multiplicative"},
                {"label": "Additive (Seasonal amplitude constant)", "value": "additive"}
            ]
        }
    )
    weight_type: str = Field(
        "optimize",
        description="Weights to Use",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Optimize (Optimal Alpha, Gamma, Delta)", "value": "optimize"},
                {"label": "User-Specified Weights", "value": "user"}
            ]
        }
    )
    user_alpha: float = Field(
        0.2,
        ge=0.0001,
        le=1.0,
        description="Alpha (α - Level)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    user_gamma: float = Field(
        0.1,
        ge=0.0001,
        le=1.0,
        description="Gamma (γ - Trend)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    user_delta: float = Field(
        0.2,
        ge=0.0001,
        le=1.0,
        description="Delta (δ - Seasonal)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    generate_forecasts: bool = Field(
        True,
        description="Generate Forecasts"
    )
    n_forecasts: int = Field(
        12,
        ge=1,
        le=100,
        description="Number of Forecast Periods",
        json_schema_extra={"sub_modal": "Options..."}
    )
    # Storage Sub-Modal
    store_fits: bool = Field(
        False,
        description="Store Fits in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_residuals: bool = Field(
        False,
        description="Store Residuals in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_forecasts: bool = Field(
        False,
        description="Store Forecasts in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_limits: bool = Field(
        False,
        description="Store 95% Prediction Limits",
        json_schema_extra={"sub_modal": "Storage..."}
    )


class WintersMethodPlugin(AnalysisPlugin):
    id = "ts_winters_method"
    name = "Winters' Method"
    menu_path = ["Stat", "Time Series", "Winters' Method"]
    description = "Triple exponential smoothing for seasonal and trending time series data (Multiplicative and Additive)."
    param_schema = WintersMethodParams

    def execute(self, df: pd.DataFrame, params: WintersMethodParams) -> AnalysisResult:
        var_name = params.variable
        if var_name not in df.columns:
            raise ValueError(f"Column '{var_name}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[var_name], errors="coerce").dropna()
        n = len(raw_series)
        s_len = max(2, params.seasonal_length)

        if n < 2 * s_len:
            raise ValueError(f"Winters' Method requires at least 2 full seasonal cycles (at least {2 * s_len} observations).")

        y = raw_series.to_numpy(dtype=float)
        if params.method_type == "multiplicative" and np.any(y <= 0):
            raise ValueError("Multiplicative Winters' Method requires all strictly positive data values.")

        t = np.arange(1, n + 1, dtype=int)

        # Fit Exponential Smoothing
        model = ExponentialSmoothing(
            y,
            trend="add",
            seasonal=params.method_type,
            seasonal_periods=s_len,
            initialization_method="estimated"
        )

        if params.weight_type == "user":
            fit_res = model.fit(
                smoothing_level=params.user_alpha,
                smoothing_trend=params.user_gamma,
                smoothing_seasonal=params.user_delta,
                optimized=False
            )
            alpha_val = params.user_alpha
            gamma_val = params.user_gamma
            delta_val = params.user_delta
        else:
            fit_res = model.fit(optimized=True)
            alpha_val = float(fit_res.params.get("smoothing_level", 0.2))
            gamma_val = float(fit_res.params.get("smoothing_trend", 0.1))
            delta_val = float(fit_res.params.get("smoothing_seasonal", 0.2))

        fits = np.array(fit_res.fittedvalues, dtype=float)
        residuals = y - fits

        # Accuracy
        mape = float(np.mean(np.abs(residuals / np.where(y != 0, y, 1e-6))) * 100.0)
        mad = float(np.mean(np.abs(residuals)))
        msd = float(np.mean(residuals ** 2))
        stdev_res = float(np.std(residuals, ddof=1)) if n > 1 else float(np.std(residuals))

        # Forecasts
        n_fc = params.n_forecasts if params.generate_forecasts else 0
        forecast_vals = np.array(fit_res.forecast(n_fc), dtype=float) if n_fc > 0 else np.array([])
        t_fc = [n + 1 + i for i in range(n_fc)]

        # 95% Prediction limits approximation
        lower_limits = []
        upper_limits = []
        for k_step in range(1, n_fc + 1):
            se_k = stdev_res * np.sqrt(1.0 + 0.1 * k_step)
            lower_limits.append(float(forecast_vals[k_step - 1] - 1.96 * se_k))
            upper_limits.append(float(forecast_vals[k_step - 1] + 1.96 * se_k))

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
                "y": [round(float(v), 4) for v in fits],
                "mode": "lines",
                "name": f"Fits ({params.method_type.capitalize()})",
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
            traces.append({
                "x": t_fc + t_fc[::-1],
                "y": [round(v, 4) for v in upper_limits] + [round(v, 4) for v in lower_limits[::-1]],
                "fill": "toself",
                "fillcolor": "rgba(209, 52, 56, 0.12)",
                "line": {"color": "rgba(209, 52, 56, 0.3)", "width": 1, "dash": "dot"},
                "name": "95% Prediction Limits"
            })

        layout = {
            "title": {"text": f"<b>Winters' Method Plot for {var_name}</b><br><span style='font-size:11px;color:#605e5c'>{params.method_type.capitalize()} Model (Period = {s_len})</span>", "font": {"size": 13, "color": "#201f1e"}},
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
            title="Model Parameters",
            headers=["Parameter", "Estimate"],
            rows=[
                ["Alpha (α - Level)", f"{alpha_val:.5f}"],
                ["Gamma (γ - Trend)", f"{gamma_val:.5f}"],
                ["Delta (δ - Seasonal)", f"{delta_val:.5f}"]
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

        fc_rows = [[t_fc[i], round(float(forecast_vals[i]), 4), round(lower_limits[i], 4), round(upper_limits[i], 4)] for i in range(n_fc)]
        tables = [param_table, acc_table]
        if n_fc > 0:
            tables.append(TableResult(
                title=f"Forecasts ({n_fc} Periods Ahead)",
                headers=["Period", "Forecast", "95% Lower Limit", "95% Upper Limit"],
                rows=fc_rows
            ))

        text_lines = [
            f"Winters' Method for {var_name}",
            f"Model Type: {params.method_type.capitalize()} | Period: {s_len}",
            "",
            "Smoothing Constants:",
            f"  Alpha (α - Level)    : {alpha_val:.5f}",
            f"  Gamma (γ - Trend)    : {gamma_val:.5f}",
            f"  Delta (δ - Seasonal) : {delta_val:.5f}",
            "",
            "Accuracy Measures:",
            f"  MAPE : {mape:.4f}%",
            f"  MAD  : {mad:.4f}",
            f"  MSD  : {msd:.4f}",
        ]
        if n_fc > 0:
            text_lines.append("")
            text_lines.append(f"  {'Period':<8} {'Forecast':>12} {'95% Lower':>12} {'95% Upper':>12}")
            text_lines.append(f"  {'-'*8} {'-'*12} {'-'*12} {'-'*12}")
            for r in fc_rows:
                text_lines.append(f"  {r[0]:<8} {r[1]:>12.4f} {r[2]:>12.4f} {r[3]:>12.4f}")

        # Worksheet Storage
        storage_cols = []
        new_cols_dict: Dict[str, List[Any]] = {}

        if params.store_fits:
            storage_cols.append({"id": f"fits_{var_name.lower()}", "name": f"FITS_{var_name}", "type": "numeric"})
            new_cols_dict[f"fits_{var_name.lower()}"] = [round(float(v), 4) for v in fits]

        if params.store_residuals:
            storage_cols.append({"id": f"resi_{var_name.lower()}", "name": f"RESI_{var_name}", "type": "numeric"})
            new_cols_dict[f"resi_{var_name.lower()}"] = [round(float(v), 4) for v in residuals]

        if params.store_forecasts and n_fc > 0:
            storage_cols.append({"id": f"fore_{var_name.lower()}", "name": f"FORE_{var_name}", "type": "numeric"})
            new_cols_dict[f"fore_{var_name.lower()}"] = [None] * n + [round(float(v), 4) for v in forecast_vals]

        if params.store_limits and n_fc > 0:
            storage_cols.append({"id": f"l95_{var_name.lower()}", "name": f"L95_{var_name}", "type": "numeric"})
            storage_cols.append({"id": f"u95_{var_name.lower()}", "name": f"U95_{var_name}", "type": "numeric"})
            new_cols_dict[f"l95_{var_name.lower()}"] = [None] * n + [round(float(v), 4) for v in lower_limits]
            new_cols_dict[f"u95_{var_name.lower()}"] = [None] * n + [round(float(v), 4) for v in upper_limits]

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
            title="Winters' Method",
            subtitle=f"{params.method_type.capitalize()} Triple Exp Smoothing for {var_name}",
            text_output="\n".join(text_lines),
            tables=tables,
            plotly_figure={"data": traces, "layout": layout},
            action_type=action_type,
            worksheet_data=worksheet_data
        )
