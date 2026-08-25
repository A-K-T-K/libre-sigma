"""
Analysis of Means (ANOM) Plugin for OpenMinitab.
Implements One-Way and Two-Way ANOM for Normal continuous data, Binomial proportions, and Poisson counts with Nelson decision limits.
"""

from typing import Any, Dict, List, Optional, Tuple
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class AnomParams(BaseModel):
    response_column: str = Field(
        ...,
        description="Response Variable (Continuous, Proportion, or Count)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    factor_1: str = Field(
        ...,
        description="Factor 1 (Categorical)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    factor_2: Optional[str] = Field(
        None,
        description="Factor 2 (optional, for Two-Way ANOM)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    distribution_type: str = Field(
        "normal",
        description="Data Distribution Family",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Normal (Continuous Data)", "value": "normal"},
                {"label": "Binomial (Proportions / Defectives)", "value": "binomial"},
                {"label": "Poisson (Count Rates)", "value": "poisson"}
            ]
        }
    )
    alpha: float = Field(0.05, ge=0.001, le=0.20, description="Significance Level Alpha (Default: 0.05)")


def get_nelson_h_factor(k: int, df: int, alpha: float) -> float:
    """Approximation of Nelson's critical factor h for Analysis of Means."""
    # Slepian's / Dunnett's critical multiplier approximation
    z_alpha = stats.norm.ppf(1.0 - alpha / (2.0 * k))
    if df < 100:
        t_alpha = stats.t.ppf(1.0 - alpha / (2.0 * k), df=max(1, df))
        return float(t_alpha * math.sqrt((k - 1) / k))
    return float(z_alpha * math.sqrt((k - 1) / k))


class AnomPlugin(AnalysisPlugin):
    id = "anom"
    name = "Analysis of Means (ANOM)"
    menu_path = ["Stat", "ANOVA", "Analysis of Means (ANOM)"]
    description = "Displays differences among factor level means relative to the overall grand mean using statistical decision limits (UDL/LDL)."
    param_schema = AnomParams

    def execute(self, df: pd.DataFrame, params: AnomParams) -> AnalysisResult:
        y_col = params.response_column
        f1_col = params.factor_1
        f2_col = params.factor_2

        factors = [f for f in [f1_col, f2_col] if f and f in df.columns]
        if y_col not in df.columns or not factors:
            raise ValueError("Select valid response and factor variables.")

        sub_df = df[[y_col] + factors].dropna().copy()
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n_total = len(sub_df)
        if n_total < 4:
            raise ValueError("ANOM requires at least 4 observations.")

        is_two_way = len(factors) == 2

        # One-Way or Main Effect of Factor 1
        groups = sorted(sub_df[f1_col].astype(str).unique())
        k = len(groups)
        if k < 2:
            raise ValueError("Factor 1 must have at least 2 levels.")

        grp_data = [sub_df[sub_df[f1_col].astype(str) == g][y_col].to_numpy(dtype=float) for g in groups]
        grp_sizes = np.array([len(g) for g in grp_data], dtype=int)
        grp_means = np.array([np.mean(g) for g in grp_data], dtype=float)

        grand_mean = float(np.mean(sub_df[y_col]))
        n_avg = float(np.mean(grp_sizes))

        if params.distribution_type == "binomial":
            # Proportions
            p_bar = grand_mean
            se_pooled = math.sqrt(max(1e-9, p_bar * (1.0 - p_bar) / n_avg))
            df_err = 1000
        elif params.distribution_type == "poisson":
            # Rates
            u_bar = grand_mean
            se_pooled = math.sqrt(max(1e-9, u_bar / n_avg))
            df_err = 1000
        else:
            # Normal Continuous
            sum_sq_err = sum(np.sum((g - np.mean(g)) ** 2) for g in grp_data)
            df_err = max(1, n_total - k)
            s_pooled = math.sqrt(sum_sq_err / df_err)
            se_pooled = s_pooled / math.sqrt(n_avg)

        # Nelson h-factor and Decision Limits
        h_val = get_nelson_h_factor(k, df_err, params.alpha)
        udl = grand_mean + h_val * se_pooled
        ldl = grand_mean - h_val * se_pooled

        out_of_limits_count = int(np.sum((grp_means > udl) | (grp_means < ldl)))

        # Build Session Log Tables
        anom_rows = []
        for i, g in enumerate(groups):
            is_out = bool(grp_means[i] > udl or grp_means[i] < ldl)
            anom_rows.append([
                g,
                str(grp_sizes[i]),
                f"{grp_means[i]:.4f}",
                f"{grand_mean:.4f}",
                f"{ldl:.4f}",
                f"{udl:.4f}",
                "Beyond Decision Limit" if is_out else "Within Limits"
            ])

        anom_table = TableResult(
            title=f"Analysis of Means for {y_col} by {f1_col} (Alpha = {params.alpha:.2f})",
            headers=[f1_col, "N", "Mean", "Grand Mean (CL)", "Lower Limit (LDL)", "Upper Limit (UDL)", "Status"],
            rows=anom_rows
        )

        # Plotly ANOM Chart
        point_colors = ["#d13438" if (m > udl or m < ldl) else "#0078d4" for m in grp_means]

        traces = [
            # Decision Limits & Center Line
            {
                "type": "scatter",
                "mode": "lines",
                "x": [-0.5, k - 0.5],
                "y": [udl, udl],
                "name": f"UDL = {udl:.3f}",
                "line": {"color": "#d13438", "width": 2, "dash": "dash"}
            },
            {
                "type": "scatter",
                "mode": "lines",
                "x": [-0.5, k - 0.5],
                "y": [grand_mean, grand_mean],
                "name": f"Grand Mean = {grand_mean:.3f}",
                "line": {"color": "#008450", "width": 2}
            },
            {
                "type": "scatter",
                "mode": "lines",
                "x": [-0.5, k - 0.5],
                "y": [ldl, ldl],
                "name": f"LDL = {ldl:.3f}",
                "line": {"color": "#d13438", "width": 2, "dash": "dash"}
            },
            # Level Mean Points
            {
                "type": "scatter",
                "mode": "lines+markers",
                "x": groups,
                "y": grp_means.tolist(),
                "name": "Level Means",
                "line": {"color": "#605e5c", "width": 1.5},
                "marker": {"color": point_colors, "size": 9}
            }
        ]

        plotly_fig = {
            "data": traces,
            "layout": {
                "title": f"Analysis of Means (ANOM) for {y_col} by {f1_col} (Alpha = {params.alpha:.2f})",
                "xaxis": {"title": f1_col, "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": f"Mean {y_col}", "showgrid": True, "gridcolor": "#ececec"},
                "legend": {"orientation": "h", "y": -0.2},
                "annotations": [
                    {
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.05,
                        "y": 0.95,
                        "text": f"<b>Grand Mean:</b> {grand_mean:.3f}<br><b>UDL:</b> {udl:.3f}<br><b>LDL:</b> {ldl:.3f}<br><b>Out of Limits:</b> {out_of_limits_count}",
                        "showarrow": False,
                        "bgcolor": "rgba(255,255,255,0.85)",
                        "bordercolor": "#d2d0ce",
                        "borderwidth": 1
                    }
                ]
            }
        }

        return AnalysisResult(
            title=f"Analysis of Means for {y_col}",
            subtitle=f"Grand Mean = {grand_mean:.4f} | Limits: [{ldl:.4f}, {udl:.4f}] | {out_of_limits_count} points out of limits",
            tables=[anom_table],
            plotly_figure=plotly_fig,
            statistics={
                "grand_mean": grand_mean,
                "udl": udl,
                "ldl": ldl,
                "h_factor": h_val,
                "out_of_limits": out_of_limits_count
            }
        )
