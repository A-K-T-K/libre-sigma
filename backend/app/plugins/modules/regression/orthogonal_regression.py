"""
Orthogonal Regression (Deming Regression) Plugin for OpenMinitab.
Accounts for measurement errors in both X and Y variables, computes Jackknife standard errors, and tests for method equivalence.
"""

from typing import Any, Dict, List, Optional, Tuple
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class OrthogonalRegressionParams(BaseModel):
    response_y: str = Field(
        ...,
        description="Response Variable Y (e.g. New Method / Device 2)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    predictor_x: str = Field(
        ...,
        description="Predictor Variable X (e.g. Reference Method / Device 1)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    error_variance_ratio: float = Field(
        1.0,
        gt=0.001,
        le=1000.0,
        description="Error Variance Ratio lambda = Var(e_y) / Var(e_x) (Default: 1.0)"
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%) - Default: 95.0"
    )


def fit_deming_slope_intercept(x: np.ndarray, y: np.ndarray, lam: float) -> Tuple[float, float]:
    """Computes exact Deming regression slope beta1 and intercept beta0."""
    x_bar, y_bar = float(np.mean(x)), float(np.mean(y))
    s_xx = float(np.var(x, ddof=1))
    s_yy = float(np.var(y, ddof=1))
    s_xy = float(np.cov(x, y)[0, 1])

    if abs(s_xy) < 1e-12:
        return 1.0, y_bar - x_bar

    # Analytical Deming slope formula
    term = (s_yy - lam * s_xx) ** 2 + 4.0 * lam * (s_xy ** 2)
    b1 = ((s_yy - lam * s_xx) + math.sqrt(max(0.0, term))) / (2.0 * s_xy)
    b0 = y_bar - b1 * x_bar
    return b1, b0


class OrthogonalRegressionPlugin(AnalysisPlugin):
    id = "orthogonal_regression"
    name = "Orthogonal Regression (Deming)"
    menu_path = ["Stat", "Regression", "Orthogonal Regression"]
    description = "Fits Deming orthogonal regression modeling measurement error in both X and Y with method equivalence testing."
    param_schema = OrthogonalRegressionParams

    def execute(self, df: pd.DataFrame, params: OrthogonalRegressionParams) -> AnalysisResult:
        y_col, x_col = params.response_y, params.predictor_x
        lam = params.error_variance_ratio

        if y_col not in df.columns or x_col not in df.columns:
            raise ValueError(f"Columns '{y_col}' and/or '{x_col}' not found in active worksheet.")

        sub_df = df[[x_col, y_col]].dropna().copy()
        sub_df[x_col] = pd.to_numeric(sub_df[x_col], errors="coerce")
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n = len(sub_df)
        if n < 5:
            raise ValueError("Orthogonal Regression requires at least 5 observation pairs.")

        x = sub_df[x_col].to_numpy(dtype=float)
        y = sub_df[y_col].to_numpy(dtype=float)

        b1_hat, b0_hat = fit_deming_slope_intercept(x, y, lam)

        # Jackknife Resampling for Standard Errors & Confidence Intervals
        jack_b0 = []
        jack_b1 = []
        for i in range(n):
            x_i = np.delete(x, i)
            y_i = np.delete(y, i)
            b1_i, b0_i = fit_deming_slope_intercept(x_i, y_i, lam)
            jack_b0.append(b0_i)
            jack_b1.append(b1_i)

        jack_b0 = np.array(jack_b0)
        jack_b1 = np.array(jack_b1)

        se_b0 = math.sqrt(((n - 1) / n) * np.sum((jack_b0 - np.mean(jack_b0)) ** 2))
        se_b1 = math.sqrt(((n - 1) / n) * np.sum((jack_b1 - np.mean(jack_b1)) ** 2))

        df_res = n - 2
        alpha_conf = 1.0 - (params.confidence_level / 100.0)
        t_crit = stats.t.ppf(1.0 - alpha_conf / 2.0, df=df_res)

        ci_b0 = (b0_hat - t_crit * se_b0, b0_hat + t_crit * se_b0)
        ci_b1 = (b1_hat - t_crit * se_b1, b1_hat + t_crit * se_b1)

        # Hypothesis Tests:
        # Test 1: Intercept = 0 (Constant Bias)
        t_stat_b0 = b0_hat / max(1e-12, se_b0)
        p_b0_zero = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat_b0), df=df_res)))

        # Test 2: Slope = 1 (Proportional Bias)
        t_stat_b1 = (b1_hat - 1.0) / max(1e-12, se_b1)
        p_b1_one = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat_b1), df=df_res)))

        # Equivalence Interpretation
        is_equivalent = bool(ci_b0[0] <= 0 <= ci_b0[1] and ci_b1[0] <= 1.0 <= ci_b1[1])

        # Orthogonal Projections for error line segments
        # x_proj = (x + b1*(y - b0)) / (1 + b1^2)
        x_proj = (x + (b1_hat / lam) * (y - b0_hat)) / (1.0 + (b1_hat ** 2) / lam)
        y_proj = b0_hat + b1_hat * x_proj

        # Build Session Log Tables
        coef_table = TableResult(
            title="Coefficients and Hypothesis Tests (Method Equivalence)",
            headers=["Parameter", "Estimate", "SE (Jackknife)", f"{params.confidence_level:.0f}% CI", "Test H0", "p-Value"],
            rows=[
                ["Intercept (Beta0)", f"{b0_hat:.4f}", f"{se_b0:.4f}", f"({ci_b0[0]:.4f}, {ci_b0[1]:.4f})", "Beta0 = 0", f"{p_b0_zero:.4f}" if p_b0_zero >= 0.0001 else "< 0.0001"],
                ["Slope (Beta1)", f"{b1_hat:.4f}", f"{se_b1:.4f}", f"({ci_b1[0]:.4f}, {ci_b1[1]:.4f})", "Beta1 = 1", f"{p_b1_one:.4f}" if p_b1_one >= 0.0001 else "< 0.0001"]
            ]
        )

        eq_table = TableResult(
            title="Orthogonal Regression Equation & Equivalence Assessment",
            headers=["Equation", "Error Ratio Lambda", "Methods Equivalent (No Bias)?"],
            rows=[[
                f"{y_col} = {b0_hat:.4f} + {b1_hat:.4f} * {x_col}",
                f"{lam:.3f}",
                "Yes (95% CI includes Intercept=0 and Slope=1)" if is_equivalent else "No (Statistically Significant Bias Detected)"
            ]]
        )

        # Plotly Orthogonal Line Plot + Error Vectors
        x_min, x_max = float(np.min(x)), float(np.max(x))
        x_grid = np.linspace(x_min, x_max, 150)
        y_grid = b0_hat + b1_hat * x_grid

        shapes = []
        # Draw error segments for first 30 points
        for i in range(min(40, n)):
            shapes.append({
                "type": "line",
                "x0": float(x[i]),
                "y0": float(y[i]),
                "x1": float(x_proj[i]),
                "y1": float(y_proj[i]),
                "line": {"color": "rgba(96, 94, 92, 0.4)", "width": 1}
            })

        plotly_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": x.tolist(),
                    "y": y.tolist(),
                    "name": f"Observed ({x_col}, {y_col})",
                    "marker": {"color": "#0078d4", "size": 6}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": x_grid.tolist(),
                    "y": y_grid.tolist(),
                    "name": f"Deming Fit: Y = {b0_hat:.3f} + {b1_hat:.3f}*X",
                    "line": {"color": "#d13438", "width": 2}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": x_grid.tolist(),
                    "y": x_grid.tolist(),
                    "name": "Identity Line (Y = X)",
                    "line": {"color": "#004d2c", "width": 1.5, "dash": "dash"}
                }
            ],
            "layout": {
                "title": f"Orthogonal Regression (Deming) Plot: {y_col} vs. {x_col}",
                "xaxis": {"title": x_col, "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": y_col, "showgrid": True, "gridcolor": "#ececec"},
                "shapes": shapes,
                "legend": {"orientation": "h", "y": -0.2},
                "annotations": [
                    {
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.05,
                        "y": 0.95,
                        "text": f"<b>{y_col} = {b0_hat:.4f} + {b1_hat:.4f} * {x_col}</b><br>Lambda = {lam:.2f} | Method Equivalence: {'Yes' if is_equivalent else 'No'}",
                        "showarrow": False,
                        "bgcolor": "rgba(255,255,255,0.85)",
                        "bordercolor": "#d2d0ce",
                        "borderwidth": 1
                    }
                ]
            }
        }

        return AnalysisResult(
            title=f"Orthogonal Regression: {y_col} vs. {x_col}",
            subtitle=f"Slope = {b1_hat:.4f} | Intercept = {b0_hat:.4f} | Equivalence: {'Yes' if is_equivalent else 'No'}",
            tables=[coef_table, eq_table],
            plotly_figure=plotly_fig,
            statistics={
                "intercept": b0_hat,
                "slope": b1_hat,
                "se_intercept": se_b0,
                "se_slope": se_b1,
                "p_intercept_zero": p_b0_zero,
                "p_slope_one": p_b1_one,
                "is_equivalent": is_equivalent
            }
        )
