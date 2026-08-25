"""
Tolerance Intervals Plugin for OpenMinitab Quality Tools.
Calculates statistical tolerance intervals (Normal and Non-parametric) guaranteeing minimum population coverage at specified confidence.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class ToleranceIntervalsParams(BaseModel):
    data_column: str = Field(
        ...,
        description="Measurement Variable",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    coverage_percent: float = Field(
        90.0,
        ge=50.0,
        le=99.99,
        description="Minimum Population Coverage (%) - e.g. 90.0"
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%) - e.g. 95.0"
    )
    method: str = Field(
        "normal",
        description="Method / Distribution",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Normal Distribution", "value": "normal"},
                {"label": "Non-parametric (Order Statistics)", "value": "nonparametric"}
            ]
        }
    )


class ToleranceIntervalsPlugin(AnalysisPlugin):
    id = "tolerance_intervals"
    name = "Tolerance Intervals"
    menu_path = ["Stat", "Quality Tools", "Tolerance Intervals"]
    description = "Calculates statistical tolerance intervals containing a specified proportion of the population with a given confidence level."
    param_schema = ToleranceIntervalsParams

    def execute(self, df: pd.DataFrame, params: ToleranceIntervalsParams) -> AnalysisResult:
        data_col = params.data_column
        if data_col not in df.columns:
            raise ValueError(f"Column '{data_col}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[data_col], errors="coerce").dropna()
        if len(raw_series) < 4:
            raise ValueError("Tolerance Intervals require at least 4 observations.")

        x = np.sort(raw_series.to_numpy(dtype=float))
        n = len(x)
        P = params.coverage_percent / 100.0
        conf = params.confidence_level / 100.0
        alpha = 1.0 - conf

        mean_val = float(np.mean(x))
        s_val = float(np.std(x, ddof=1))

        if s_val < 1e-12:
            raise ValueError("Data has zero variance; cannot compute tolerance intervals.")

        # --- 1. Normal Tolerance Interval (Howe-Guenther / Exact Non-central t) ---
        z_p = stats.norm.ppf((1.0 + P) / 2.0)
        chi2_crit = stats.chi2.ppf(alpha, df=n - 1)
        # Howe-Guenther factor for 2-sided
        k_2sided = float(z_p * math.sqrt((n - 1) / max(1e-6, chi2_crit)) * (1.0 + 1.0 / (2.0 * n)))

        lower_tol_norm = mean_val - k_2sided * s_val
        upper_tol_norm = mean_val + k_2sided * s_val

        # 1-Sided k-factor via non-central t
        try:
            nc_param = stats.norm.ppf(P) * math.sqrt(n)
            nct_val = stats.nct.ppf(conf, df=n - 1, nc=nc_param)
            k_1sided = float(nct_val / math.sqrt(n))
        except Exception:
            k_1sided = k_2sided

        lower_1s_norm = mean_val - k_1sided * s_val
        upper_1s_norm = mean_val + k_1sided * s_val

        # --- 2. Non-parametric Tolerance Interval ---
        # Find order statistics (r, s) minimizing s - r such that sum_{i=0}^{s-r-1} binom(n, i) P^i (1-P)^{n-i} >= conf
        best_r, best_s, achieved_conf = 1, n, 0.0
        for r in range(1, n // 2 + 1):
            for s in range(n, n // 2, -1):
                k_covered = s - r
                achieved = 1.0 - stats.binom.cdf(k_covered - 1, n, P)
                if achieved >= conf:
                    best_r, best_s = r, s
                    achieved_conf = float(achieved)
                    break

        lower_np = float(x[best_r - 1])
        upper_np = float(x[best_s - 1])

        # Select Output according to method
        is_normal = params.method == "normal"
        active_lower = lower_tol_norm if is_normal else lower_np
        active_upper = upper_tol_norm if is_normal else upper_np

        # Build Session Log Tables
        tol_table = TableResult(
            title=f"Statistical Tolerance Intervals for {data_col} ({params.coverage_percent:.1f}% Coverage, {params.confidence_level:.1f}% Confidence)",
            headers=["Method", "Sample Mean", "Sample StDev", "k-Factor", "Two-Sided Interval", "Achieved Conf."],
            rows=[
                [
                    "Normal Distribution",
                    f"{mean_val:.4f}",
                    f"{s_val:.4f}",
                    f"{k_2sided:.3f}",
                    f"({lower_tol_norm:.4f}, {upper_tol_norm:.4f})",
                    f"{params.confidence_level:.1f}%"
                ],
                [
                    "Non-parametric",
                    f"{mean_val:.4f}",
                    f"{s_val:.4f}",
                    f"[{best_r}, {best_s}]",
                    f"({lower_np:.4f}, {upper_np:.4f})",
                    f"{achieved_conf * 100.0:.2f}%"
                ]
            ]
        )

        onesided_table = TableResult(
            title="One-Sided Normal Tolerance Limits",
            headers=["Direction", "k-Factor", "Tolerance Bound"],
            rows=[
                ["Lower Bound Only", f"{k_1sided:.3f}", f">= {lower_1s_norm:.4f}"],
                ["Upper Bound Only", f"{k_1sided:.3f}", f"<= {upper_1s_norm:.4f}"]
            ]
        )

        # Plotly Density + Shaded Tolerance Region
        x_grid = np.linspace(min(x[0], active_lower) - 0.5 * s_val, max(x[-1], active_upper) + 0.5 * s_val, 300)
        pdf_y = stats.norm.pdf(x_grid, loc=mean_val, scale=s_val)

        # Shaded region mask
        shade_mask = (x_grid >= active_lower) & (x_grid <= active_upper)

        plotly_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": x_grid.tolist(),
                    "y": pdf_y.tolist(),
                    "name": "Fitted Normal Distribution",
                    "line": {"color": "#0078d4", "width": 2}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": x_grid[shade_mask].tolist(),
                    "y": pdf_y[shade_mask].tolist(),
                    "fill": "tozeroy",
                    "name": f"Covered Region ({params.coverage_percent:.0f}%)",
                    "fillcolor": "rgba(0, 132, 80, 0.25)",
                    "line": {"color": "#008450", "width": 1.5}
                },
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": x.tolist(),
                    "y": [0.0] * n,
                    "name": "Sample Observations",
                    "marker": {"color": "#323130", "size": 6, "symbol": "circle"}
                }
            ],
            "layout": {
                "title": f"Tolerance Interval Plot for {data_col} ({params.coverage_percent:.0f}% Coverage / {params.confidence_level:.0f}% Confidence)",
                "xaxis": {"title": data_col, "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": "Density", "showgrid": True, "gridcolor": "#ececec"},
                "shapes": [
                    {"type": "line", "x0": active_lower, "y0": 0, "x1": active_lower, "y1": max(pdf_y) * 1.1, "line": {"color": "#d13438", "width": 2, "dash": "dash"}},
                    {"type": "line", "x0": active_upper, "y0": 0, "x1": active_upper, "y1": max(pdf_y) * 1.1, "line": {"color": "#d13438", "width": 2, "dash": "dash"}}
                ],
                "annotations": [
                    {"x": active_lower, "y": max(pdf_y) * 1.12, "text": f"Lower: {active_lower:.3f}", "showarrow": False, "font": {"color": "#d13438", "size": 10}},
                    {"x": active_upper, "y": max(pdf_y) * 1.12, "text": f"Upper: {active_upper:.3f}", "showarrow": False, "font": {"color": "#d13438", "size": 10}}
                ],
                "legend": {"orientation": "h", "y": -0.2}
            }
        }

        return AnalysisResult(
            title=f"Tolerance Intervals for {data_col}",
            subtitle=f"{params.confidence_level:.0f}% Confidence that at least {params.coverage_percent:.0f}% of population is between ({active_lower:.4f}, {active_upper:.4f})",
            tables=[tol_table, onesided_table],
            plotly_figure=plotly_fig,
            statistics={
                "mean": mean_val,
                "stdev": s_val,
                "k_2sided": k_2sided,
                "lower_tol_normal": lower_tol_norm,
                "upper_tol_normal": upper_tol_norm,
                "lower_tol_np": lower_np,
                "upper_tol_np": upper_np,
                "achieved_conf_np": achieved_conf
            }
        )
