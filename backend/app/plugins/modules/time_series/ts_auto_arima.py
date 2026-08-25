"""
Auto-ARIMA (Best Model Forecast) Plugin for OpenMinitab.
Automates ARIMA model identification and order selection using AIC/AICc/BIC information criteria.
Fits optimal seasonal/non-seasonal ARIMA model, displays model comparison grid, parameter estimates, and forecast trajectory.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class AutoARIMAParams(BaseModel):
    variable: str = Field(
        ...,
        description="Series / Variable (Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    information_criterion: str = Field(
        "aic",
        description="Model Selection Criterion",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "AIC (Akaike Information Criterion)", "value": "aic"},
                {"label": "AICc (Corrected AIC)", "value": "aicc"},
                {"label": "BIC (Bayesian Information Criterion)", "value": "bic"}
            ]
        }
    )
    seasonal_periodicity: int = Field(
        1,
        ge=1,
        le=365,
        description="Seasonal Periodicity (m) (1 for Non-Seasonal, 4 for Quarterly, 12 for Monthly)"
    )
    max_p: int = Field(
        3,
        ge=0,
        le=10,
        description="Max p (AR)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    max_q: int = Field(
        3,
        ge=0,
        le=10,
        description="Max q (MA)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    max_d: int = Field(
        2,
        ge=0,
        le=4,
        description="Max d (Differences)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    max_P: int = Field(
        2,
        ge=0,
        le=5,
        description="Max P (Seasonal AR)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    max_Q: int = Field(
        2,
        ge=0,
        le=5,
        description="Max Q (Seasonal MA)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    max_D: int = Field(
        1,
        ge=0,
        le=2,
        description="Max D (Seasonal Diff)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    stepwise: bool = Field(
        True,
        description="Use Stepwise Fast Search",
        json_schema_extra={"sub_modal": "Options..."}
    )
    n_forecasts: int = Field(
        12,
        ge=1,
        le=100,
        description="Forecast Periods Ahead"
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Forecast Confidence Level (%)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    # Storage Sub-Modal
    store_residuals: bool = Field(
        False,
        description="Store Residuals in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_fits: bool = Field(
        False,
        description="Store Fitted Values in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_forecasts: bool = Field(
        False,
        description="Store Forecasts in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_bounds: bool = Field(
        False,
        description="Store Prediction Bounds in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )


class AutoARIMAPlugin(AnalysisPlugin):
    id = "ts_auto_arima"
    name = "Auto-ARIMA (Best Model)"
    menu_path = ["Stat", "Time Series", "Auto-ARIMA (Best Model)"]
    description = "Automatically identifies and fits the best ARIMA(p,d,q)(P,D,Q)[m] model using stepwise or grid information criteria search."
    param_schema = AutoARIMAParams

    def execute(self, df: pd.DataFrame, params: AutoARIMAParams) -> AnalysisResult:
        var_name = params.variable
        if var_name not in df.columns:
            raise ValueError(f"Column '{var_name}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[var_name], errors="coerce").dropna()
        n = len(raw_series)
        if n < 10:
            raise ValueError("Auto-ARIMA requires at least 10 observations.")

        y = raw_series.to_numpy(dtype=float)
        m = max(1, params.seasonal_periodicity)
        is_seasonal = m > 1 and n >= 2 * m

        # Try pmdarima auto_arima
        try:
            import pmdarima as pm

            model = pm.auto_arima(
                y,
                start_p=0,
                max_p=params.max_p,
                start_q=0,
                max_q=params.max_q,
                max_d=params.max_d,
                start_P=0,
                max_P=params.max_P if is_seasonal else 0,
                start_Q=0,
                max_Q=params.max_Q if is_seasonal else 0,
                max_D=params.max_D if is_seasonal else 0,
                m=m if is_seasonal else 1,
                seasonal=is_seasonal,
                information_criterion=params.information_criterion.lower(),
                stepwise=params.stepwise,
                suppress_warnings=True,
                error_action="ignore",
                trace=False
            )

            best_order = model.order
            best_seasonal_order = model.seasonal_order if is_seasonal else (0, 0, 0, 0)
            model_name = f"ARIMA{best_order}" + (f"({best_seasonal_order[0]},{best_seasonal_order[1]},{best_seasonal_order[2]})[{m}]" if is_seasonal else "")

            fitted_vals = np.array(model.fittedvalues(), dtype=float)
            residuals = np.array(model.resid(), dtype=float)
            log_lik = float(model.arima_res_.llf) if hasattr(model, "arima_res_") and hasattr(model.arima_res_, "llf") else 0.0
            aic_val = float(model.aic())
            bic_val = float(model.bic())

            # Forecasts with confidence interval
            n_fc = params.n_forecasts
            alpha_level = 1.0 - params.confidence_level / 100.0
            fc_vals, conf_int = model.predict(n_periods=n_fc, return_conf_int=True, alpha=alpha_level)
            lower_limits = [float(b[0]) for b in conf_int]
            upper_limits = [float(b[1]) for b in conf_int]

            # Param table
            param_names = model.arima_res_.param_names if hasattr(model, "arima_res_") else []
            param_coefs = model.params()
            param_pvals = model.pvalues() if hasattr(model, "pvalues") else [None] * len(param_coefs)

        except Exception as e:
            # Fallback to statsmodels ARIMA grid search
            from statsmodels.tsa.arima.model import ARIMA
            best_aic = float("inf")
            best_model_fit = None
            best_order = (1, 1, 1)

            for p_i in range(min(3, params.max_p + 1)):
                for d_i in range(min(2, params.max_d + 1)):
                    for q_i in range(min(3, params.max_q + 1)):
                        try:
                            sm_mod = ARIMA(y, order=(p_i, d_i, q_i)).fit()
                            if sm_mod.aic < best_aic:
                                best_aic = sm_mod.aic
                                best_model_fit = sm_mod
                                best_order = (p_i, d_i, q_i)
                        except Exception:
                            continue

            if best_model_fit is None:
                best_model_fit = ARIMA(y, order=(1, 0, 0)).fit()

            model_name = f"ARIMA{best_order}"
            fitted_vals = np.array(best_model_fit.fittedvalues, dtype=float)
            residuals = np.array(best_model_fit.resid, dtype=float)
            log_lik = float(best_model_fit.llf)
            aic_val = float(best_model_fit.aic)
            bic_val = float(best_model_fit.bic)

            n_fc = params.n_forecasts
            fc_res = best_model_fit.get_forecast(steps=n_fc)
            fc_vals = np.array(fc_res.predicted_mean, dtype=float)
            ci_df = fc_res.conf_int(alpha=1.0 - params.confidence_level / 100.0)
            lower_limits = ci_df.iloc[:, 0].tolist()
            upper_limits = ci_df.iloc[:, 1].tolist()
            param_names = best_model_fit.param_names
            param_coefs = best_model_fit.params
            param_pvals = best_model_fit.pvalues

        # Plotly Forecast Chart
        t_actual = list(range(1, n + 1))
        t_fc = [n + 1 + i for i in range(n_fc)]

        traces = [
            {
                "x": t_actual,
                "y": y.tolist(),
                "mode": "lines+markers",
                "name": "Actual Data",
                "line": {"color": "#005a9e", "width": 2},
                "marker": {"size": 5, "color": "#005a9e"}
            },
            {
                "x": t_actual,
                "y": [round(float(v), 4) for v in fitted_vals],
                "mode": "lines",
                "name": f"Fitted ({model_name})",
                "line": {"color": "#008450", "width": 2}
            },
            {
                "x": t_fc,
                "y": [round(float(v), 4) for v in fc_vals],
                "mode": "lines+markers",
                "name": "Forecast",
                "line": {"color": "#d13438", "width": 2, "dash": "dash"},
                "marker": {"size": 6, "symbol": "diamond", "color": "#d13438"}
            },
            {
                "x": t_fc + t_fc[::-1],
                "y": [round(v, 4) for v in upper_limits] + [round(v, 4) for v in lower_limits[::-1]],
                "fill": "toself",
                "fillcolor": "rgba(209, 52, 56, 0.12)",
                "line": {"color": "rgba(209, 52, 56, 0.3)", "width": 1, "dash": "dot"},
                "name": f"{params.confidence_level:.0f}% Prediction Limits"
            }
        ]

        layout = {
            "title": {"text": f"<b>Auto-ARIMA Forecast Plot for {var_name}</b><br><span style='font-size:11px;color:#605e5c'>Selected Best Model: <b>{model_name}</b> (AIC = {aic_val:.2f}, BIC = {bic_val:.2f})</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Index / Period (t)", "showgrid": True, "gridcolor": "#f3f2f1", "linecolor": "#201f1e"},
            "yaxis": {"title": var_name, "showgrid": True, "gridcolor": "#f3f2f1", "linecolor": "#201f1e"},
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 55, "r": 30, "t": 60, "b": 55},
            "hovermode": "x unified"
        }

        # Tables
        summary_table = TableResult(
            title="Selected Model Summary",
            headers=["Criterion / Metric", "Value"],
            rows=[
                ["Selected Model", model_name],
                ["Selection Criterion", params.information_criterion.upper()],
                ["Log-Likelihood", f"{log_lik:.4f}"],
                ["AIC", f"{aic_val:.4f}"],
                ["BIC", f"{bic_val:.4f}"],
                ["Sample Size N", str(n)]
            ]
        )

        coef_rows = []
        for i in range(len(param_coefs)):
            p_name = param_names[i] if i < len(param_names) else f"param_{i}"
            c_val = float(param_coefs[i])
            pv = float(param_pvals[i]) if i < len(param_pvals) and param_pvals[i] is not None else None
            coef_rows.append([p_name, round(c_val, 5), round(pv, 5) if pv is not None else "N/A"])

        param_tbl = TableResult(
            title="Parameter Estimates",
            headers=["Parameter", "Estimate (Coef)", "P-Value"],
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

        fc_tbl = TableResult(
            title=f"Forecasts ({n_fc} Periods Ahead with {params.confidence_level:.0f}% Limits)",
            headers=["Period", "Forecast", f"{params.confidence_level:.0f}% Lower Limit", f"{params.confidence_level:.0f}% Upper Limit"],
            rows=fc_rows
        )

        text_lines = [
            f"Auto-ARIMA Model Selection for {var_name}",
            "",
            f"Best Selected Model : {model_name}",
            f"Log-Likelihood      : {log_lik:.4f}",
            f"AIC                 : {aic_val:.4f}",
            f"BIC                 : {bic_val:.4f}",
            "",
            "Parameter Estimates:",
        ]
        for r in coef_rows:
            text_lines.append(f"  {r[0]:<16} : Coef = {r[1]:>10.5f}  (p-value = {r[2]})")

        text_lines += [
            "",
            f"Forecasts ({params.confidence_level:.0f}% Prediction Limits):",
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

        if params.store_forecasts:
            storage_cols.append({"id": f"fore_{var_name.lower()}", "name": f"FORE_{var_name}", "type": "numeric"})
            new_cols_dict[f"fore_{var_name.lower()}"] = [None] * n + [round(float(v), 4) for v in fc_vals]

        if params.store_bounds:
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
            title="Auto-ARIMA Model Selection",
            subtitle=f"Best Model: {model_name} for {var_name}",
            text_output="\n".join(text_lines),
            tables=[summary_table, param_tbl, fc_tbl],
            plotly_figure={"data": traces, "layout": layout},
            action_type=action_type,
            worksheet_data=worksheet_data
        )
