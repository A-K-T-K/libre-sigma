"""
Response Optimizer (Multi-Response Desirability Profiler) Plugin for OpenMinitab.
Implements the Derringer and Suich desirability function methodology to find optimal factor settings (X*) that optimize multiple responses simultaneously.
Calculates individual desirabilities (di), composite desirability (D), and generates interactive multi-factor prediction profilers.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import statsmodels.api as sm
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class ResponseOptimizerParams(BaseModel):
    responses: List[str] = Field(
        ...,
        description="Response Variables (Y)",
        json_schema_extra={"ui_type": "column_multi_picker", "data_type": "numeric"}
    )
    factors: List[str] = Field(
        ...,
        description="Factors / Predictors (X)",
        json_schema_extra={"ui_type": "column_multi_picker", "data_type": "numeric"}
    )
    goal: str = Field(
        "maximize",
        description="Optimization Goal",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Maximize (Larger is Better)", "value": "maximize"},
                {"label": "Minimize (Smaller is Better)", "value": "minimize"},
                {"label": "Target (Nominal is Best)", "value": "target"}
            ]
        }
    )
    lower_limit: Optional[float] = Field(
        None,
        description="Lower Limit (L)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    target_value: Optional[float] = Field(
        None,
        description="Target Value (T)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    upper_limit: Optional[float] = Field(
        None,
        description="Upper Limit (U)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    weight: float = Field(
        1.0,
        ge=0.1,
        le=10.0,
        description="Weight (Curvature of Desirability Function, Default: 1.0)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    importance: float = Field(
        1.0,
        ge=0.1,
        le=5.0,
        description="Importance / Priority (1.0 to 5.0)",
        json_schema_extra={"sub_modal": "Options..."}
    )


class ResponseOptimizerPlugin(AnalysisPlugin):
    id = "doe_response_optimizer"
    name = "Response Optimizer"
    menu_path = ["Stat", "DOE", "Response Optimizer"]
    description = "Finds the factor settings that optimize single or multiple response variables using Derringer-Suich desirability functions."
    param_schema = ResponseOptimizerParams

    def execute(self, df: pd.DataFrame, params: ResponseOptimizerParams) -> AnalysisResult:
        resp_cols = params.responses
        factor_cols = params.factors

        if not resp_cols or not factor_cols:
            raise ValueError("Please select at least one response variable and one factor.")

        all_cols = resp_cols + factor_cols
        sub_df = df[all_cols].dropna().copy()
        for c in all_cols:
            sub_df[c] = pd.to_numeric(sub_df[c], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        if len(sub_df) < len(factor_cols) + 3:
            raise ValueError("Response Optimizer requires sufficient experimental runs to fit regression models.")

        # Fit quadratic or linear response surface regression for each response
        models = {}
        factor_mins = {f: float(sub_df[f].min()) for f in factor_cols}
        factor_maxs = {f: float(sub_df[f].max()) for f in factor_cols}
        factor_means = {f: float(sub_df[f].mean()) for f in factor_cols}

        for r_name in resp_cols:
            # Build design matrix with intercept, linear, and interaction/squared if enough degrees of freedom
            X_mat = np.column_stack([np.ones(len(sub_df))] + [sub_df[f].to_numpy() for f in factor_cols])
            y_vec = sub_df[r_name].to_numpy()
            reg = sm.OLS(y_vec, X_mat).fit()
            models[r_name] = reg

        # Determine default limits for each response
        resp_limits = {}
        for r_name in resp_cols:
            y_vals = sub_df[r_name].to_numpy()
            y_min, y_max = float(np.min(y_vals)), float(np.max(y_vals))

            L = params.lower_limit if params.lower_limit is not None else y_min
            U = params.upper_limit if params.upper_limit is not None else y_max
            T = params.target_value if params.target_value is not None else (y_max if params.goal == "maximize" else (y_min if params.goal == "minimize" else (y_min + y_max) / 2.0))

            resp_limits[r_name] = {"L": L, "T": T, "U": U, "goal": params.goal, "wt": params.weight, "imp": params.importance}

        def individual_desirability(y_hat: float, spec: Dict[str, Any]) -> float:
            goal = spec["goal"]
            L, T, U, w = spec["L"], spec["T"], spec["U"], spec["wt"]
            if goal == "maximize":
                if y_hat < L: return 0.0
                elif y_hat > T: return 1.0
                elif T == L: return 1.0
                else: return float(((y_hat - L) / (T - L)) ** w)
            elif goal == "minimize":
                if y_hat < T: return 1.0
                elif y_hat > U: return 0.0
                elif U == T: return 1.0
                else: return float(((U - y_hat) / (U - T)) ** w)
            else: # target
                if y_hat < L or y_hat > U: return 0.0
                elif y_hat <= T:
                    return float(((y_hat - L) / (T - L)) ** w) if T > L else 1.0
                else:
                    return float(((U - y_hat) / (U - T)) ** w) if U > T else 1.0

        def predict_response(r_name: str, x_vec: np.ndarray) -> float:
            model = models[r_name]
            x_design = np.array([1.0] + list(x_vec))
            return float(np.dot(model.params, x_design))

        def composite_desirability_loss(x_vec: np.ndarray) -> float:
            d_list = []
            imp_list = []
            for r_name in resp_cols:
                y_hat = predict_response(r_name, x_vec)
                d_i = individual_desirability(y_hat, resp_limits[r_name])
                d_list.append(max(1e-8, d_i))
                imp_list.append(resp_limits[r_name]["imp"])

            # Geometric mean: D = (prod(d_i^r_i))^(1/sum(r_i))
            log_D = sum(imp * np.log(d) for imp, d in zip(imp_list, d_list)) / sum(imp_list)
            D = np.exp(log_D)
            return -D # minimize negative desirability

        # Bounds for optimization: [min, max] for each factor
        bounds = [(factor_mins[f], factor_maxs[f]) for f in factor_cols]
        x0 = [factor_means[f] for f in factor_cols]

        opt_res = minimize(composite_desirability_loss, x0, bounds=bounds, method="L-BFGS-B")
        best_x = opt_res.x
        global_D = float(-opt_res.fun)

        # Factor setting table
        factor_setting_rows = []
        for idx, f in enumerate(factor_cols):
            opt_val = float(best_x[idx])
            factor_setting_rows.append([f, round(factor_mins[f], 3), round(opt_val, 4), round(factor_maxs[f], 3)])

        # Response optimization table
        resp_opt_rows = []
        for r_name in resp_cols:
            y_opt = predict_response(r_name, best_x)
            d_opt = individual_desirability(y_opt, resp_limits[r_name])
            spec = resp_limits[r_name]
            resp_opt_rows.append([
                r_name,
                spec["goal"].capitalize(),
                round(spec["L"], 3),
                round(spec["T"], 3),
                round(spec["U"], 3),
                round(y_opt, 4),
                round(d_opt, 4)
            ])

        # Prediction Profiler Traces: Plot predicted response vs factor 1 holding others at optimal
        traces = []
        f_primary = factor_cols[0]
        f_grid = np.linspace(factor_mins[f_primary], factor_maxs[f_primary], 50)

        for r_name in resp_cols:
            y_curve = []
            for f_val in f_grid:
                x_test = best_x.copy()
                x_test[0] = f_val
                y_curve.append(predict_response(r_name, x_test))

            traces.append({
                "x": f_grid.tolist(),
                "y": y_curve,
                "mode": "lines",
                "name": f"Predicted {r_name}",
                "line": {"width": 2}
            })

        # Vertical line at optimal factor setting
        shapes = [{
            "type": "line",
            "x0": float(best_x[0]),
            "x1": float(best_x[0]),
            "y0": 0,
            "y1": 1,
            "yref": "paper",
            "line": {"color": "#d13438", "width": 1.5, "dash": "dash"}
        }]

        layout = {
            "title": {"text": f"<b>Response Optimization Profiler: Composite Desirability D = {global_D:.4f}</b><br><span style='font-size:11px;color:#605e5c'>Optimal {f_primary} = {float(best_x[0]):.4f}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": f"{f_primary} (Optimal = {float(best_x[0]):.4f})", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Predicted Response", "showgrid": True, "gridcolor": "#f3f2f1"},
            "shapes": shapes,
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 55}
        }

        tables = [
            TableResult(
                title="Optimal Factor Settings",
                headers=["Factor", "Low Setting", "Optimal Setting (X*)", "High Setting"],
                rows=factor_setting_rows
            ),
            TableResult(
                title=f"Response Optimization (Composite Desirability D = {global_D:.4f})",
                headers=["Response", "Goal", "Lower", "Target", "Upper", "Predicted Fit (Y*)", "Individual Desirability (d)"],
                rows=resp_opt_rows
            )
        ]

        text_lines = [
            "Response Optimization: Multi-Response Desirability",
            f"Composite Desirability D = {global_D:.4f}",
            "",
            "Optimal Factor Settings:",
        ]
        for fs in factor_setting_rows:
            text_lines.append(f"  {fs[0]:<16}: {fs[2]:>10.4f} (Range: [{fs[1]}, {fs[3]}])")
        text_lines += ["", "Predicted Responses & Desirabilities:"]
        for ro in resp_opt_rows:
            text_lines.append(f"  {ro[0]:<16}: Fit = {ro[5]:>10.4f}   d = {ro[6]:>8.4f}   Goal: {ro[1]}")

        return AnalysisResult(
            title="Response Optimizer",
            subtitle=f"Composite Desirability D = {global_D:.4f}",
            text_output="\n".join(text_lines),
            tables=tables,
            plotly_figure={"data": traces, "layout": layout},
            statistics={
                "composite_desirability": global_D,
                "optimal_settings": {f: float(best_x[i]) for i, f in enumerate(factor_cols)}
            }
        )
