"""
ARIMA Plugin for OpenMinitab.
Fits customized ARIMA(p, d, q) x (P, D, Q)_s models with drift/constant terms.
Generates full parameter regression table with z-statistics and p-values, 4-in-1 residual diagnostic plots, and future forecast intervals.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class ARIMAParams(BaseModel):
    variable: str = Field(
        ...,
        description="Series / Variable (Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    # Non-seasonal
    p: int = Field(1, ge=0, le=10, description="Autoregressive Order (p)")
    d: int = Field(1, ge=0, le=4, description="Difference Order (d)")
    q: int = Field(1, ge=0, le=10, description="Moving Average Order (q)")
    # Seasonal
    P: int = Field(0, ge=0, le=5, description="Seasonal AR (P)", json_schema_extra={"sub_modal": "Seasonal..."})
    D: int = Field(0, ge=0, le=2, description="Seasonal Diff (D)", json_schema_extra={"sub_modal": "Seasonal..."})
    Q: int = Field(0, ge=0, le=5, description="Seasonal MA (Q)", json_schema_extra={"sub_modal": "Seasonal..."})
    S: int = Field(12, ge=1, le=365, description="Seasonal Period (S)", json_schema_extra={"sub_modal": "Seasonal..."})
    # Settings
    include_constant: bool = Field(True, description="Include Constant / Trend Term")
    generate_forecasts: bool = Field(True, description="Generate Forecasts")
    n_forecasts: int = Field(12, ge=1, le=100, description="Forecast Lead Periods")
    confidence_level: float = Field(95.0, ge=50.0, le=99.99, description="Confidence Level (%)")
    # Graphs Sub-Modal
    show_four_in_one: bool = Field(True, description="Generate 4-in-1 Residual Diagnostic Plots", json_schema_extra={"sub_modal": "Graphs..."})
    # Storage Sub-Modal
    store_residuals: bool = Field(False, description="Store Residuals", json_schema_extra={"sub_modal": "Storage..."})
    store_fits: bool = Field(False, description="Store Fits", json_schema_extra={"sub_modal": "Storage..."})
    store_forecasts: bool = Field(False, description="Store Forecasts", json_schema_extra={"sub_modal": "Storage..."})
    store_limits: bool = Field(False, description="Store 95% Prediction Limits", json_schema_extra={"sub_modal": "Storage..."})


class ARIMAPlugin(AnalysisPlugin):
    id = "ts_arima"
    name = "ARIMA"
    menu_path = ["Stat", "Time Series", "ARIMA"]
    description = "Fits custom non-seasonal and seasonal Box-Jenkins ARIMA models with parameter tests, 4-in-1 diagnostic plots, and forecasts."
    param_schema = ARIMAParams

    def execute(self, df: pd.DataFrame, params: ARIMAParams) -> AnalysisResult:
        var_name = params.variable
        if var_name not in df.columns:
            raise ValueError(f"Column '{var_name}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[var_name], errors="coerce").dropna()
        n = len(raw_series)
        if n < 8:
            raise ValueError("ARIMA requires at least 8 observations.")

        y = raw_series.to_numpy(dtype=float)
        trend_arg = "c" if params.include_constant and params.d == 0 else "t" if params.include_constant and params.d > 0 else "n"

        order = (params.p, params.d, params.q)
        seasonal_order = (params.P, params.D, params.Q, params.S) if (params.P > 0 or params.D > 0 or params.Q > 0) else (0, 0, 0, 0)

        # Fit statsmodels ARIMA
        try:
            model = ARIMA(
                y,
                order=order,
                seasonal_order=seasonal_order if seasonal_order[3] > 1 else (0, 0, 0, 0),
                trend=trend_arg
            )
            fit_res = model.fit()
        except Exception as e:
            # If fitting with constant failed, try with trend=None
            model = ARIMA(y, order=order, seasonal_order=seasonal_order if seasonal_order[3] > 1 else (0, 0, 0, 0))
            fit_res = model.fit()

        fitted_vals = np.array(fit_res.fittedvalues, dtype=float)
        residuals = np.array(fit_res.resid, dtype=float)
        log_lik = float(fit_res.llf)
        aic_val = float(fit_res.aic)
        bic_val = float(fit_res.bic)
        sigma2_val = float(fit_res.scale if hasattr(fit_res, "scale") and fit_res.scale is not None else np.var(residuals))

        # Forecasts
        n_fc = params.n_forecasts if params.generate_forecasts else 0
        if n_fc > 0:
            fc_obj = fit_res.get_forecast(steps=n_fc)
            fc_vals = np.array(fc_obj.predicted_mean, dtype=float)
            alpha_level = 1.0 - params.confidence_level / 100.0
            ci_df = fc_obj.conf_int(alpha=alpha_level)
            lower_limits = [float(v) for v in ci_df[:, 0] if not isinstance(ci_df, pd.DataFrame)] if not isinstance(ci_df, pd.DataFrame) else ci_df.iloc[:, 0].tolist()
            upper_limits = [float(v) for v in ci_df[:, 1] if not isinstance(ci_df, pd.DataFrame)] if not isinstance(ci_df, pd.DataFrame) else ci_df.iloc[:, 1].tolist()
        else:
            fc_vals, lower_limits, upper_limits = np.array([]), [], []

        # Parameters table
        param_names = fit_res.param_names
        param_coefs = fit_res.params
        param_bse = fit_res.bse
        param_pvals = fit_res.pvalues
        param_zvals = fit_res.tvalues

        coef_rows = []
        for i in range(len(param_names)):
            p_n = param_names[i]
            c_v = float(param_coefs[i])
            se_v = float(param_bse[i]) if i < len(param_bse) else 0.0
            z_v = float(param_zvals[i]) if i < len(param_zvals) else (c_v / se_v if se_v > 0 else 0.0)
            pv_v = float(param_pvals[i]) if i < len(param_pvals) else 0.0
            coef_rows.append([p_n, round(c_v, 5), round(se_v, 5), round(z_v, 4), round(pv_v, 5)])

        # 4-in-1 Residual Plot or Forecast Plot
        figures = []
        t_actual = list(range(1, n + 1))
        t_fc = [n + 1 + i for i in range(n_fc)]

        # 1. Main Forecast Plot
        traces_fc = [
            {"x": t_actual, "y": y.tolist(), "mode": "lines+markers", "name": "Actual", "line": {"color": "#005a9e", "width": 2}, "marker": {"size": 5}},
            {"x": t_actual, "y": [round(float(v), 4) for v in fitted_vals], "mode": "lines", "name": "Fits", "line": {"color": "#008450", "width": 2}}
        ]
        if n_fc > 0:
            traces_fc.append({
                "x": t_fc, "y": [round(float(v), 4) for v in fc_vals], "mode": "lines+markers", "name": "Forecast",
                "line": {"color": "#d13438", "width": 2, "dash": "dash"}, "marker": {"size": 6, "symbol": "diamond", "color": "#d13438"}
            })
            traces_fc.append({
                "x": t_fc + t_fc[::-1],
                "y": [round(v, 4) for v in upper_limits] + [round(v, 4) for v in lower_limits[::-1]],
                "fill": "toself",
                "fillcolor": "rgba(209, 52, 56, 0.12)",
                "line": {"color": "rgba(209, 52, 56, 0.3)", "width": 1, "dash": "dot"},
                "name": f"{params.confidence_level:.0f}% Prediction Limits"
            })

        order_str = f"({params.p},{params.d},{params.q})"
        s_order_str = f"({params.P},{params.D},{params.Q})[{params.S}]" if seasonal_order[3] > 1 else ""
        full_model_name = f"ARIMA{order_str}{s_order_str}"

        layout_fc = {
            "title": {"text": f"<b>ARIMA Forecast Plot for {var_name}</b><br><span style='font-size:11px;color:#605e5c'>Model: {full_model_name}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Index / Period", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": var_name, "showgrid": True, "gridcolor": "#f3f2f1"},
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 55, "r": 30, "t": 60, "b": 55}
        }

        # 2. 4-in-1 Residual Plot
        clean_res = residuals[~np.isnan(residuals)]
        sorted_res = np.sort(clean_res)
        n_res = len(sorted_res)
        p_vals_norm = [(i - 0.375) / (n_res + 0.25) for i in range(1, n_res + 1)]
        norm_quantiles = stats.norm.ppf(p_vals_norm)

        traces_diag = [
            # 1. Normal Prob Plot
            {"x": sorted_res.tolist(), "y": norm_quantiles.tolist(), "mode": "markers", "name": "Normal Prob", "xaxis": "x", "yaxis": "y", "marker": {"color": "#005a9e", "size": 5}},
            # 2. Residuals vs Fits
            {"x": fitted_vals.tolist(), "y": residuals.tolist(), "mode": "markers", "name": "Res vs Fits", "xaxis": "x2", "yaxis": "y2", "marker": {"color": "#008450", "size": 5}},
            # 3. Histogram
            {"x": clean_res.tolist(), "type": "histogram", "name": "Histogram", "xaxis": "x3", "yaxis": "y3", "marker": {"color": "#8764b8"}},
            # 4. Residuals vs Order
            {"x": t_actual, "y": residuals.tolist(), "mode": "lines+markers", "name": "Res vs Order", "xaxis": "x4", "yaxis": "y4", "line": {"color": "#d13438"}, "marker": {"size": 4}}
        ]

        layout_diag = {
            "title": {"text": f"<b>Residual Diagnostic Plots for {var_name} (4-in-1)</b><br><span style='font-size:11px;color:#605e5c'>Model: {full_model_name}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "grid": {"rows": 2, "columns": 2, "pattern": "independent"},
            "xaxis": {"title": "Residual", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Normal Quantile", "showgrid": True, "gridcolor": "#f3f2f1"},
            "xaxis2": {"title": "Fitted Value", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis2": {"title": "Residual", "showgrid": True, "gridcolor": "#f3f2f1"},
            "xaxis3": {"title": "Residual", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis3": {"title": "Frequency", "showgrid": True, "gridcolor": "#f3f2f1"},
            "xaxis4": {"title": "Observation Order", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis4": {"title": "Residual", "showgrid": True, "gridcolor": "#f3f2f1"},
            "showlegend": False,
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 55, "r": 30, "t": 60, "b": 50}
        }

        # Tables
        fit_table = TableResult(
            title="Model Fit Summary",
            headers=["Statistic / Metric", "Value"],
            rows=[
                ["Model", full_model_name],
                ["Log-Likelihood", f"{log_lik:.4f}"],
                ["AIC", f"{aic_val:.4f}"],
                ["BIC", f"{bic_val:.4f}"],
                ["Residual Variance (Sigma^2)", f"{sigma2_val:.5f}"],
                ["Number of Observations", str(n)]
            ]
        )

        coef_table = TableResult(
            title="Parameter Estimates",
            headers=["Parameter", "Estimate (Coef)", "Std Error", "Z-Statistic", "P-Value"],
            rows=coef_rows
        )

        fc_rows = []
        for i in range(n_fc):
            fc_rows.append([
                t_fc[i],
                round(float(fc_vals[i]), 4),
                round(float(lower_limits[i]), 4),
                round(float(upper_limits[i]), 4)
            ])

        tables = [fit_table, coef_table]
        if n_fc > 0:
            tables.append(TableResult(
                title=f"Forecasts ({n_fc} Periods Ahead with {params.confidence_level:.0f}% Limits)",
                headers=["Period", "Forecast", f"{params.confidence_level:.0f}% Lower Limit", f"{params.confidence_level:.0f}% Upper Limit"],
                rows=fc_rows
            ))

        text_lines = [
            f"ARIMA Model for {var_name}",
            f"Model Specification: {full_model_name}",
            "",
            "Estimates at Each Iteration:",
            f"  Log-Likelihood : {log_lik:.4f}",
            f"  AIC            : {aic_val:.4f}",
            f"  BIC            : {bic_val:.4f}",
            f"  Sigma^2        : {sigma2_val:.5f}",
            "",
            f"  {'Parameter':<16} {'Coef':>10} {'SE':>10} {'Z-Stat':>10} {'P-Value':>10}",
            f"  {'-'*16} {'-'*10} {'-'*10} {'-'*10} {'-'*10}",
        ]
        for r in coef_rows:
            text_lines.append(f"  {r[0]:<16} {r[1]:>10.5f} {r[2]:>10.5f} {r[3]:>10.4f} {r[4]:>10.5f}")

        if n_fc > 0:
            text_lines += [
                "",
                f"Forecasts from period {n}:",
                f"  {'Period':<8} {'Forecast':>12} {'Lower':>12} {'Upper':>12}",
                f"  {'-'*8} {'-'*12} {'-'*12} {'-'*12}"
            ]
            for r in fc_rows:
                text_lines.append(f"  {r[0]:<8} {r[1]:>12.4f} {r[2]:>12.4f} {r[3]:>12.4f}")

        # Worksheet Storage
        storage_cols = []
        new_cols_dict: Dict[str, List[Any]] = {}

        if params.store_fits:
            storage_cols.append({"id": f"fits_{var_name.lower()}", "name": f"FITS_{var_name}", "type": "numeric"})
            new_cols_dict[f"fits_{var_name.lower()}"] = [round(float(v), 4) for v in fitted_vals]

        if params.store_residuals:
            storage_cols.append({"id": f"resi_{var_name.lower()}", "name": f"RESI_{var_name}", "type": "numeric"})
            new_cols_dict[f"resi_{var_name.lower()}"] = [round(float(v), 4) for v in residuals]

        if params.store_forecasts and n_fc > 0:
            storage_cols.append({"id": f"fore_{var_name.lower()}", "name": f"FORE_{var_name}", "type": "numeric"})
            new_cols_dict[f"fore_{var_name.lower()}"] = [None] * n + [round(float(v), 4) for v in fc_vals]

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

        selected_plot = {"data": traces_diag, "layout": layout_diag} if params.show_four_in_one else {"data": traces_fc, "layout": layout_fc}

        return AnalysisResult(
            title="ARIMA",
            subtitle=f"{full_model_name} Model for {var_name}",
            text_output="\n".join(text_lines),
            tables=tables,
            plotly_figure=selected_plot,
            plotly_figures=[
                {"data": traces_fc, "layout": layout_fc},
                {"data": traces_diag, "layout": layout_diag}
            ],
            action_type=action_type,
            worksheet_data=worksheet_data
        )
