"""
Fitted Line Plot Plugin for OpenMinitab Regression.
Performs linear, quadratic, and cubic polynomial regression with data transformations and exact 95% CI & PI prediction bands.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class FittedLinePlotParams(BaseModel):
    response_y: str = Field(
        ...,
        description="Response Variable (Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    predictor_x: str = Field(
        ...,
        description="Predictor Variable (X)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    model_type: str = Field(
        "linear",
        description="Polynomial Model Type",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Linear: Y = b0 + b1*X", "value": "linear"},
                {"label": "Quadratic: Y = b0 + b1*X + b2*X^2", "value": "quadratic"},
                {"label": "Cubic: Y = b0 + b1*X + b2*X^2 + b3*X^3", "value": "cubic"}
            ]
        }
    )
    x_transform: str = Field(
        "none",
        description="Transform X",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "None", "value": "none"},
                {"label": "Natural log (ln X)", "value": "ln"},
                {"label": "Base 10 log (log10 X)", "value": "log10"}
            ]
        }
    )
    y_transform: str = Field(
        "none",
        description="Transform Y",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "None", "value": "none"},
                {"label": "Natural log (ln Y)", "value": "ln"},
                {"label": "Base 10 log (log10 Y)", "value": "log10"}
            ]
        }
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%) - Default: 95.0"
    )


class FittedLinePlotPlugin(AnalysisPlugin):
    id = "fitted_line_plot"
    name = "Fitted Line Plot"
    menu_path = ["Stat", "Regression", "Fitted Line Plot"]
    description = "Fits linear, quadratic, or cubic regression models with transformations and displays 95% confidence and prediction intervals."
    param_schema = FittedLinePlotParams

    def execute(self, df: pd.DataFrame, params: FittedLinePlotParams) -> AnalysisResult:
        y_col, x_col = params.response_y, params.predictor_x
        if y_col not in df.columns or x_col not in df.columns:
            raise ValueError(f"Columns '{y_col}' and/or '{x_col}' not found in active worksheet.")

        sub_df = df[[x_col, y_col]].dropna().copy()
        sub_df[x_col] = pd.to_numeric(sub_df[x_col], errors="coerce")
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        if len(sub_df) < 4:
            raise ValueError("Fitted Line Plot requires at least 4 valid numeric observation pairs.")

        # Transformations
        x_raw = sub_df[x_col].to_numpy(dtype=float)
        y_raw = sub_df[y_col].to_numpy(dtype=float)

        x_vals = x_raw.copy()
        y_vals = y_raw.copy()

        x_label = x_col
        y_label = y_col

        if params.x_transform == "ln":
            if np.any(x_vals <= 0):
                raise ValueError("Cannot apply Natural Log transformation to X: non-positive values found.")
            x_vals = np.log(x_vals)
            x_label = f"ln({x_col})"
        elif params.x_transform == "log10":
            if np.any(x_vals <= 0):
                raise ValueError("Cannot apply Log10 transformation to X: non-positive values found.")
            x_vals = np.log10(x_vals)
            x_label = f"log10({x_col})"

        if params.y_transform == "ln":
            if np.any(y_vals <= 0):
                raise ValueError("Cannot apply Natural Log transformation to Y: non-positive values found.")
            y_vals = np.log(y_vals)
            y_label = f"ln({y_col})"
        elif params.y_transform == "log10":
            if np.any(y_vals <= 0):
                raise ValueError("Cannot apply Log10 transformation to Y: non-positive values found.")
            y_vals = np.log10(y_vals)
            y_label = f"log10({y_col})"

        n = len(x_vals)
        order = 1 if params.model_type == "linear" else (2 if params.model_type == "quadratic" else 3)
        if n <= order + 1:
            raise ValueError(f"Need at least {order + 2} data points to fit a {params.model_type} model.")

        # Build Design Matrix X
        cols = [np.ones(n, dtype=float)]
        term_names = ["Constant"]
        for deg in range(1, order + 1):
            cols.append(x_vals ** deg)
            term_names.append(f"{x_label}" if deg == 1 else f"{x_label}^{deg}")

        X_mat = np.column_stack(cols)
        p = X_mat.shape[1]

        # OLS Estimation
        xtx = X_mat.T @ X_mat
        try:
            xtx_inv = np.linalg.pinv(xtx)
            beta = xtx_inv @ (X_mat.T @ y_vals)
        except Exception:
            beta = np.linalg.lstsq(X_mat, y_vals, rcond=None)[0]
            xtx_inv = np.linalg.pinv(xtx)

        y_hat = X_mat @ beta
        residuals = y_vals - y_hat
        ss_res = float(np.sum(residuals ** 2))
        y_mean = float(np.mean(y_vals))
        ss_tot = float(np.sum((y_vals - y_mean) ** 2))

        df_reg = p - 1
        df_res = n - p
        ms_res = ss_res / max(1, df_res)
        s_val = math.sqrt(max(1e-12, ms_res))

        r_sq = float(1.0 - ss_res / ss_tot) if ss_tot > 1e-12 else 1.0
        r_sq_adj = float(1.0 - (ss_res / max(1, df_res)) / (ss_tot / (n - 1))) if ss_tot > 1e-12 and n > 1 else 1.0

        # Hat matrix & PRESS
        H = X_mat @ xtx_inv @ X_mat.T
        h_diag = np.diag(H)
        press_res = residuals / np.maximum(1e-6, 1.0 - h_diag)
        press = float(np.sum(press_res ** 2))
        r_sq_pred = max(0.0, float(1.0 - press / ss_tot)) if ss_tot > 1e-12 else 0.0

        # Coefficients and standard errors
        se_beta = np.sqrt(np.maximum(1e-12, np.diag(ms_res * xtx_inv)))
        t_stats = beta / np.maximum(1e-12, se_beta)
        p_vals = [float(2.0 * (1.0 - stats.t.cdf(abs(t), df=df_res))) for t in t_stats]

        # Regression Equation String
        eq_parts = [f"{beta[0]:.4f}"]
        for i in range(1, p):
            sign_str = " + " if beta[i] >= 0 else " - "
            eq_parts.append(f"{sign_str}{abs(beta[i]):.4f} * {term_names[i]}")
        eq_str = f"{y_label} = " + "".join(eq_parts)

        # Build Session Log Tables
        coef_rows = []
        for i, tname in enumerate(term_names):
            coef_rows.append([
                tname,
                f"{beta[i]:.4f}",
                f"{se_beta[i]:.4f}",
                f"{t_stats[i]:.2f}",
                f"{p_vals[i]:.4f}" if p_vals[i] >= 0.0001 else "< 0.0001"
            ])

        coef_table = TableResult(
            title=f"Coefficients for {params.model_type.capitalize()} Model",
            headers=["Term", "Coef", "SE Coef", "t-Value", "p-Value"],
            rows=coef_rows
        )

        model_summary_table = TableResult(
            title="Model Summary",
            headers=["S", "R-sq", "R-sq(adj)", "R-sq(pred)"],
            rows=[[
                f"{s_val:.4f}",
                f"{r_sq * 100.0:.2f}%",
                f"{r_sq_adj * 100.0:.2f}%",
                f"{r_sq_pred * 100.0:.2f}%"
            ]]
        )

        ss_reg = max(0.0, ss_tot - ss_res)
        ms_reg = ss_reg / max(1, df_reg)
        f_stat = ms_reg / max(1e-12, ms_res)
        p_model = float(1.0 - stats.f.cdf(f_stat, df_reg, df_res))

        anova_table = TableResult(
            title="Analysis of Variance (ANOVA)",
            headers=["Source", "DF", "SS", "MS", "F-Value", "p-Value"],
            rows=[
                ["Regression", str(df_reg), f"{ss_reg:.4f}", f"{ms_reg:.4f}", f"{f_stat:.2f}", f"{p_model:.4f}" if p_model >= 0.0001 else "< 0.0001"],
                ["Error", str(df_res), f"{ss_res:.4f}", f"{ms_res:.4f}", "---", "---"],
                ["Total", str(n - 1), f"{ss_tot:.4f}", "---", "---", "---"]
            ]
        )

        # Plotly Curve with 95% CI and PI Bands
        x_min, x_max = float(np.min(x_vals)), float(np.max(x_vals))
        x_grid = np.linspace(x_min, x_max, 200)
        X_grid_mat = np.column_stack([x_grid ** deg for deg in range(order + 1)])
        y_grid_fit = X_grid_mat @ beta

        # t critical for bands
        alpha_conf = 1.0 - (params.confidence_level / 100.0)
        t_crit = stats.t.ppf(1.0 - alpha_conf / 2.0, df=df_res)

        # Leverage of grid points
        h_grid = np.sum((X_grid_mat @ xtx_inv) * X_grid_mat, axis=1)
        ci_half = t_crit * s_val * np.sqrt(np.maximum(0.0, h_grid))
        pi_half = t_crit * s_val * np.sqrt(np.maximum(0.0, 1.0 + h_grid))

        ci_upper = (y_grid_fit + ci_half).tolist()
        ci_lower = (y_grid_fit - ci_half).tolist()
        pi_upper = (y_grid_fit + pi_half).tolist()
        pi_lower = (y_grid_fit - pi_half).tolist()

        plotly_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": x_vals.tolist(),
                    "y": y_vals.tolist(),
                    "name": "Observed Data",
                    "marker": {"color": "#0078d4", "size": 6}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": x_grid.tolist(),
                    "y": y_grid_fit.tolist(),
                    "name": f"Fit: {params.model_type.capitalize()}",
                    "line": {"color": "#d13438", "width": 2}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": x_grid.tolist() + x_grid[::-1].tolist(),
                    "y": ci_upper + ci_lower[::-1],
                    "fill": "toself",
                    "name": f"{params.confidence_level:.0f}% CI Band",
                    "fillcolor": "rgba(0, 132, 80, 0.15)",
                    "line": {"color": "rgba(0,0,0,0)"}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": x_grid.tolist(),
                    "y": pi_upper,
                    "name": f"{params.confidence_level:.0f}% PI Band",
                    "line": {"color": "#605e5c", "dash": "dash", "width": 1.5}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": x_grid.tolist(),
                    "y": pi_lower,
                    "showlegend": False,
                    "line": {"color": "#605e5c", "dash": "dash", "width": 1.5}
                }
            ],
            "layout": {
                "title": f"Fitted Line Plot for {y_label} vs. {x_label}",
                "xaxis": {"title": x_label, "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": y_label, "showgrid": True, "gridcolor": "#ececec"},
                "legend": {"orientation": "h", "y": -0.2},
                "annotations": [
                    {
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.05,
                        "y": 0.95,
                        "text": f"<b>{eq_str}</b><br>S = {s_val:.4f} | R-sq = {r_sq * 100:.2f}% | R-sq(adj) = {r_sq_adj * 100:.2f}%",
                        "showarrow": False,
                        "bgcolor": "rgba(255,255,255,0.85)",
                        "bordercolor": "#d2d0ce",
                        "borderwidth": 1
                    }
                ]
            }
        }

        return AnalysisResult(
            title=f"Fitted Line Plot: {y_label} vs. {x_label}",
            subtitle=f"{eq_str} | R-sq = {r_sq * 100:.2f}%",
            tables=[coef_table, model_summary_table, anova_table],
            plotly_figure=plotly_fig,
            statistics={
                "equation": eq_str,
                "s": s_val,
                "r_sq": r_sq,
                "r_sq_adj": r_sq_adj,
                "r_sq_pred": r_sq_pred,
                "coefficients": beta.tolist(),
                "p_values": p_vals
            }
        )
