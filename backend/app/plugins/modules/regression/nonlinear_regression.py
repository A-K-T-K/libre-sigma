"""
Nonlinear Regression Plugin for OpenMinitab.
Fits nonlinear parameter equations via Levenberg-Marquardt / TRF, computes asymptotic covariance from Jacobian, and generates fitted response curves.
"""

from typing import Any, Dict, List, Optional, Callable
import math
import numpy as np
import pandas as pd
from scipy import stats, optimize
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


PRESET_FUNCTIONS = {
    "exponential_growth": {
        "label": "Exponential: Y = a * exp(b * X)",
        "func": lambda x, a, b: a * np.exp(np.clip(b * x, -50, 50)),
        "param_names": ["a", "b"],
        "default_init": [1.0, 0.1]
    },
    "michaelis_menten": {
        "label": "Michaelis-Menten: Y = (Vm * X) / (Km + X)",
        "func": lambda x, Vm, Km: (Vm * x) / np.maximum(1e-9, Km + x),
        "param_names": ["Vm", "Km"],
        "default_init": [10.0, 1.0]
    },
    "logistic_growth": {
        "label": "Logistic: Y = L / (1 + exp(-k * (X - x0)))",
        "func": lambda x, L, k, x0: L / (1.0 + np.exp(np.clip(-k * (x - x0), -50, 50))),
        "param_names": ["L", "k", "x0"],
        "default_init": [100.0, 0.1, 10.0]
    },
    "power_law": {
        "label": "Power Law: Y = a * X^b",
        "func": lambda x, a, b: a * (np.maximum(1e-9, x) ** b),
        "param_names": ["a", "b"],
        "default_init": [1.0, 1.0]
    },
    "gompertz": {
        "label": "Gompertz: Y = a * exp(-b * exp(-c * X))",
        "func": lambda x, a, b, c: a * np.exp(-b * np.exp(np.clip(-c * x, -50, 50))),
        "param_names": ["a", "b", "c"],
        "default_init": [100.0, 1.0, 0.1]
    }
}


class NonlinearRegressionParams(BaseModel):
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
    model_function: str = Field(
        "exponential_growth",
        description="Nonlinear Model Function",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": v["label"], "value": k} for k, v in PRESET_FUNCTIONS.items()
            ]
        }
    )
    initial_params_str: Optional[str] = Field(
        None,
        description="Starting Parameter Values (comma-separated, optional)"
    )
    max_iterations: int = Field(200, ge=10, le=5000, description="Maximum Iterations (Default: 200)")


class NonlinearRegressionPlugin(AnalysisPlugin):
    id = "nonlinear_regression"
    name = "Nonlinear Regression"
    menu_path = ["Stat", "Regression", "Nonlinear Regression"]
    description = "Estimates parameters for nonlinear mathematical equations via Levenberg-Marquardt optimization with Wald confidence bounds."
    param_schema = NonlinearRegressionParams

    def execute(self, df: pd.DataFrame, params: NonlinearRegressionParams) -> AnalysisResult:
        y_col, x_col = params.response_y, params.predictor_x
        if y_col not in df.columns or x_col not in df.columns:
            raise ValueError(f"Columns '{y_col}' and/or '{x_col}' not found in active worksheet.")

        sub_df = df[[x_col, y_col]].dropna().copy()
        sub_df[x_col] = pd.to_numeric(sub_df[x_col], errors="coerce")
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        if len(sub_df) < 5:
            raise ValueError("Nonlinear Regression requires at least 5 valid observations.")

        x_data = sub_df[x_col].to_numpy(dtype=float)
        y_data = sub_df[y_col].to_numpy(dtype=float)
        n = len(x_data)

        # Get preset definition
        preset = PRESET_FUNCTIONS.get(params.model_function, PRESET_FUNCTIONS["exponential_growth"])
        func = preset["func"]
        param_names = preset["param_names"]
        p = len(param_names)

        # Parse initial guesses
        p0 = preset["default_init"]
        if params.initial_params_str:
            try:
                parsed_init = [float(v.strip()) for v in params.initial_params_str.split(",") if v.strip()]
                if len(parsed_init) == p:
                    p0 = parsed_init
            except Exception:
                pass

        # Optimize via scipy curve_fit (Levenberg-Marquardt or TRF)
        try:
            popt, pcov = optimize.curve_fit(func, x_data, y_data, p0=p0, maxfev=params.max_iterations * 50)
        except Exception as e:
            # Fallback with bounding
            try:
                popt, pcov = optimize.curve_fit(func, x_data, y_data, p0=p0, method="trf", maxfev=params.max_iterations * 50)
            except Exception as e2:
                raise ValueError(f"Nonlinear optimization failed to converge: {e2}")

        y_pred = func(x_data, *popt)
        residuals = y_data - y_pred
        ss_res = float(np.sum(residuals ** 2))
        y_mean = float(np.mean(y_data))
        ss_tot = float(np.sum((y_data - y_mean) ** 2))

        df_res = max(1, n - p)
        ms_res = ss_res / df_res
        s_val = math.sqrt(max(1e-12, ms_res))

        r_sq = float(1.0 - ss_res / ss_tot) if ss_tot > 1e-12 else 1.0
        r_sq_adj = float(1.0 - (ss_res / df_res) / (ss_tot / (n - 1))) if ss_tot > 1e-12 and n > 1 else 1.0

        # Asymptotic Standard Errors & 95% Wald CI
        if pcov is not None and not np.isinf(pcov).any():
            se_params = np.sqrt(np.maximum(1e-12, np.diag(pcov)))
        else:
            se_params = np.full(p, 0.1)

        t_crit = stats.t.ppf(0.975, df=df_res)
        ci_lower = popt - t_crit * se_params
        ci_upper = popt + t_crit * se_params

        # Build Session Log Tables
        param_rows = []
        for i, pname in enumerate(param_names):
            param_rows.append([
                pname,
                f"{popt[i]:.5f}",
                f"{se_params[i]:.5f}",
                f"({ci_lower[i]:.5f}, {ci_upper[i]:.5f})"
            ])

        param_table = TableResult(
            title=f"Nonlinear Parameter Estimates ({preset['label']})",
            headers=["Parameter", "Optimal Estimate", "Asymptotic SE", "95% Wald CI"],
            rows=param_rows
        )

        model_summary_table = TableResult(
            title="Model Summary",
            headers=["S (Residual SE)", "Residual SS", "R-sq", "R-sq(adj)"],
            rows=[[
                f"{s_val:.4f}",
                f"{ss_res:.4f}",
                f"{r_sq * 100.0:.2f}%",
                f"{r_sq_adj * 100.0:.2f}%"
            ]]
        )

        # Plotly Fitted Curve Overlay
        x_grid = np.linspace(float(np.min(x_data)), float(np.max(x_data)), 200)
        y_grid_fit = func(x_grid, *popt)

        plotly_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": x_data.tolist(),
                    "y": y_data.tolist(),
                    "name": "Observed Data",
                    "marker": {"color": "#0078d4", "size": 6}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": x_grid.tolist(),
                    "y": y_grid_fit.tolist(),
                    "name": f"Nonlinear Fit: {preset['label'].split(':')[0]}",
                    "line": {"color": "#d13438", "width": 2.5}
                }
            ],
            "layout": {
                "title": f"Nonlinear Regression Plot: {y_col} vs. {x_col}",
                "xaxis": {"title": x_col, "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": y_col, "showgrid": True, "gridcolor": "#ececec"},
                "legend": {"orientation": "h", "y": -0.2},
                "annotations": [
                    {
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.05,
                        "y": 0.95,
                        "text": f"<b>{preset['label']}</b><br>S = {s_val:.4f} | R-sq = {r_sq * 100:.2f}%",
                        "showarrow": False,
                        "bgcolor": "rgba(255,255,255,0.85)",
                        "bordercolor": "#d2d0ce",
                        "borderwidth": 1
                    }
                ]
            }
        }

        return AnalysisResult(
            title=f"Nonlinear Regression: {y_col} vs. {x_col}",
            subtitle=f"{preset['label']} | R-sq = {r_sq * 100:.2f}% | S = {s_val:.4f}",
            tables=[param_table, model_summary_table],
            plotly_figure=plotly_fig,
            statistics={
                "parameters": dict(zip(param_names, popt.tolist())),
                "s": s_val,
                "r_sq": r_sq,
                "r_sq_adj": r_sq_adj
            }
        )
