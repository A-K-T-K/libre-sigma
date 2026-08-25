"""
Trend Analysis Plugin for OpenMinitab.
Fits Linear, Quadratic, Exponential Growth, and S-Curve (Logistic) trend models.
Computes MAPE, MAD, MSD accuracy measures and generates forecasts with prediction limits.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import optimize, stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class TrendAnalysisParams(BaseModel):
    variable: str = Field(
        ...,
        description="Variable (Series Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    model_type: str = Field(
        "linear",
        description="Trend Model Type",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Linear (Yt = b0 + b1*t)", "value": "linear"},
                {"label": "Quadratic (Yt = b0 + b1*t + b2*t^2)", "value": "quadratic"},
                {"label": "Exponential Growth (Yt = b0 * (b1^t))", "value": "exponential"},
                {"label": "S-Curve / Logistic (Yt = 10^a / (b0 + b1*(b2^t)))", "value": "scurve"}
            ]
        }
    )
    generate_forecasts: bool = Field(
        True,
        description="Generate Forecasts"
    )
    n_forecasts: int = Field(
        6,
        ge=1,
        le=100,
        description="Number of Forecasts",
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
    # Time Scale Sub-Modal
    time_column: Optional[str] = Field(
        None,
        description="Time Stamp / Date Column (optional)",
        json_schema_extra={"ui_type": "column_picker", "sub_modal": "Time Scale..."}
    )


class TrendAnalysisPlugin(AnalysisPlugin):
    id = "ts_trend_analysis"
    name = "Trend Analysis"
    menu_path = ["Stat", "Time Series", "Trend Analysis"]
    description = "Fits Linear, Quadratic, Exponential Growth, or Logistic S-Curve trend models with accuracy metrics and future forecasting."
    param_schema = TrendAnalysisParams

    def execute(self, df: pd.DataFrame, params: TrendAnalysisParams) -> AnalysisResult:
        var_name = params.variable
        if var_name not in df.columns:
            raise ValueError(f"Column '{var_name}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[var_name], errors="coerce").dropna()
        n = len(raw_series)
        if n < 4:
            raise ValueError("Trend Analysis requires at least 4 valid numeric observations.")

        y = raw_series.to_numpy(dtype=float)
        t = np.arange(1, n + 1, dtype=float)

        # Fit model
        model = params.model_type
        eq_str = ""
        fits = np.zeros(n)

        if model == "linear":
            # Y = b0 + b1*t
            poly = np.polyfit(t, y, 1)  # poly[0]*t + poly[1]
            b1, b0 = poly[0], poly[1]
            fits = b0 + b1 * t
            sign1 = "+" if b1 >= 0 else "-"
            eq_str = f"Yt = {b0:.5g} {sign1} {abs(b1):.5g} × t"
            forecast_func = lambda t_f: b0 + b1 * t_f

        elif model == "quadratic":
            # Y = b0 + b1*t + b2*t^2
            poly = np.polyfit(t, y, 2)  # poly[0]*t^2 + poly[1]*t + poly[2]
            b2, b1, b0 = poly[0], poly[1], poly[2]
            fits = b0 + b1 * t + b2 * (t ** 2)
            sign1 = "+" if b1 >= 0 else "-"
            sign2 = "+" if b2 >= 0 else "-"
            eq_str = f"Yt = {b0:.5g} {sign1} {abs(b1):.5g} × t {sign2} {abs(b2):.5g} × t²"
            forecast_func = lambda t_f: b0 + b1 * t_f + b2 * (t_f ** 2)

        elif model == "exponential":
            # Yt = b0 * (b1^t) => ln(Yt) = ln(b0) + ln(b1)*t
            if np.any(y <= 0):
                raise ValueError("Exponential Growth model requires all positive data values.")
            ln_y = np.log(y)
            poly = np.polyfit(t, ln_y, 1)
            ln_b1, ln_b0 = poly[0], poly[1]
            b0 = np.exp(ln_b0)
            b1 = np.exp(ln_b1)
            fits = b0 * (b1 ** t)
            eq_str = f"Yt = {b0:.5g} × ({b1:.5g})^t"
            forecast_func = lambda t_f: b0 * (b1 ** t_f)

        elif model == "scurve":
            # S-Curve (Logistic): Yt = 10^a / (b0 + b1*(b2^t)) or standard logistic: L / (1 + exp(-k*(t - t0)))
            def logistic_fn(t_val, L, k, t0):
                return L / (1.0 + np.exp(-np.clip(k * (t_val - t0), -50, 50)))

            try:
                L_init = float(np.max(y) * 1.2) if np.max(y) > 0 else 10.0
                popt, _ = optimize.curve_fit(
                    logistic_fn, t, y,
                    p0=[L_init, 0.1, float(np.median(t))],
                    maxfev=5000
                )
                L_est, k_est, t0_est = popt
                fits = logistic_fn(t, L_est, k_est, t0_est)
                eq_str = f"Yt = {L_est:.5g} / [1 + exp(-{k_est:.4g} × (t - {t0_est:.4g}))]"
                forecast_func = lambda t_f: logistic_fn(t_f, L_est, k_est, t0_est)
            except Exception:
                # Fallback to linear if non-linear optimization fails
                poly = np.polyfit(t, y, 1)
                b1, b0 = poly[0], poly[1]
                fits = b0 + b1 * t
                eq_str = f"Yt = {b0:.5g} + {b1:.5g} × t (Linear Fallback)"
                forecast_func = lambda t_f: b0 + b1 * t_f

        residuals = y - fits

        # Accuracy measures
        mape = float(np.mean(np.abs(residuals / np.where(y != 0, y, 1e-6))) * 100.0)
        mad = float(np.mean(np.abs(residuals)))
        msd = float(np.mean(residuals ** 2))
        stdev_res = float(np.std(residuals, ddof=2)) if n > 2 else float(np.std(residuals))

        # Forecasts
        n_fc = params.n_forecasts if params.generate_forecasts else 0
        t_future = np.arange(n + 1, n + n_fc + 1, dtype=float)
        forecast_vals = forecast_func(t_future) if n_fc > 0 else np.array([])
        
        # Prediction Limits (95%)
        t_crit = stats.t.ppf(0.975, df=max(1, n - 2))
        lower_limits = forecast_vals - t_crit * stdev_res * np.sqrt(1 + 1.0 / n + ((t_future - np.mean(t)) ** 2) / max(1e-6, np.sum((t - np.mean(t)) ** 2)))
        upper_limits = forecast_vals + t_crit * stdev_res * np.sqrt(1 + 1.0 / n + ((t_future - np.mean(t)) ** 2) / max(1e-6, np.sum((t - np.mean(t)) ** 2)))

        # Plotly traces
        x_actual = [int(i) for i in t]
        x_forecast = [int(i) for i in t_future]

        traces = [
            {
                "x": x_actual,
                "y": y.tolist(),
                "mode": "lines+markers",
                "name": "Actual",
                "line": {"color": "#005a9e", "width": 2},
                "marker": {"size": 6, "color": "#005a9e"}
            },
            {
                "x": x_actual,
                "y": fits.tolist(),
                "mode": "lines",
                "name": "Fits",
                "line": {"color": "#008450", "width": 2, "dash": "solid"}
            }
        ]

        if n_fc > 0:
            traces.append({
                "x": x_forecast,
                "y": forecast_vals.tolist(),
                "mode": "lines+markers",
                "name": "Forecast",
                "line": {"color": "#d13438", "width": 2, "dash": "dash"},
                "marker": {"size": 6, "symbol": "diamond", "color": "#d13438"}
            })
            traces.append({
                "x": x_forecast + x_forecast[::-1],
                "y": upper_limits.tolist() + lower_limits.tolist()[::-1],
                "fill": "toself",
                "fillcolor": "rgba(209, 52, 56, 0.12)",
                "line": {"color": "rgba(209, 52, 56, 0.3)", "width": 1, "dash": "dot"},
                "name": "95% Prediction Limits",
                "showlegend": True
            })

        layout = {
            "title": {"text": f"<b>Trend Analysis Plot for {var_name}</b><br><span style='font-size:11px;color:#605e5c'>{eq_str}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Time / Period (t)", "showgrid": True, "gridcolor": "#f3f2f1", "linecolor": "#201f1e"},
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

        fc_rows = []
        for idx in range(n_fc):
            fc_rows.append([
                int(t_future[idx]),
                round(float(forecast_vals[idx]), 4),
                round(float(lower_limits[idx]), 4),
                round(float(upper_limits[idx]), 4)
            ])

        tables = [acc_table]
        if n_fc > 0:
            tables.append(TableResult(
                title="Forecasts with 95% Prediction Limits",
                headers=["Period", "Forecast", "95% Lower Limit", "95% Upper Limit"],
                rows=fc_rows
            ))

        text_lines = [
            f"Trend Analysis for {var_name}",
            "",
            f"Fitted Trend Equation: {eq_str}",
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
            # Pad with blanks for existing rows then forecast values
            fore_full = [None] * n + [round(float(v), 4) for v in forecast_vals]
            new_cols_dict[f"fore_{var_name.lower()}"] = fore_full

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
            title="Trend Analysis",
            subtitle=f"{model.capitalize()} Model for {var_name}",
            text_output="\n".join(text_lines),
            tables=tables,
            plotly_figure={"data": traces, "layout": layout},
            action_type=action_type,
            worksheet_data=worksheet_data
        )
