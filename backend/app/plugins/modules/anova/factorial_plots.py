"""
Factorial Visualization Plots Plugin Suite for OpenMinitab.
Implements Main Effects Plot, Interaction Plot, and Interval Plot for multi-factor ANOVA designs.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


# =====================================================================
# 1. MAIN EFFECTS PLOT
# =====================================================================
class MainEffectsPlotParams(BaseModel):
    response_column: str = Field(
        ...,
        description="Response Variable (Continuous Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    factors: List[str] = Field(
        ...,
        description="Factors to Plot (Categorical / Discrete)",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )


class MainEffectsPlotPlugin(AnalysisPlugin):
    id = "main_effects_plot"
    name = "Main Effects Plot"
    menu_path = ["Stat", "ANOVA", "Main Effects Plot"]
    description = "Displays the response mean across levels of each factor with a reference line for the overall Grand Mean."
    param_schema = MainEffectsPlotParams

    def execute(self, df: pd.DataFrame, params: MainEffectsPlotParams) -> AnalysisResult:
        y_col = params.response_column
        factors = [f for f in params.factors if f in df.columns]

        if y_col not in df.columns or not factors:
            raise ValueError("Select a response variable and at least one factor.")

        sub_df = df[[y_col] + factors].dropna().copy().reset_index(drop=True)
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        if len(sub_df) < 2:
            raise ValueError("Main Effects Plot requires at least 2 data points.")

        grand_mean = float(np.mean(sub_df[y_col]))

        traces = []
        table_rows = []

        for f in factors:
            grp = sub_df.groupby(f)[y_col]
            lvls = [str(idx) for idx in grp.mean().index]
            means = grp.mean().values.tolist()
            counts = grp.count().values.tolist()

            traces.append({
                "type": "scatter",
                "mode": "lines+markers",
                "x": lvls,
                "y": means,
                "name": f"Factor: {f}",
                "marker": {"size": 8}
            })

            for lvl, m, n_cnt in zip(lvls, means, counts):
                table_rows.append([f, lvl, str(n_cnt), f"{m:.4f}", f"{m - grand_mean:.4f}"])

        traces.append({
            "type": "scatter",
            "mode": "lines",
            "x": [str(idx) for idx in sub_df.groupby(factors[0])[y_col].mean().index],
            "y": [grand_mean] * len(sub_df[factors[0]].unique()),
            "name": f"Grand Mean ({grand_mean:.3f})",
            "line": {"color": "#004d2c", "dash": "dash"}
        })

        summary_table = TableResult(
            title=f"Main Effects Summary for {y_col} (Grand Mean = {grand_mean:.4f})",
            headers=["Factor", "Level", "N", "Mean", "Effect (Mean - Grand Mean)"],
            rows=table_rows
        )

        plotly_fig = {
            "data": traces,
            "layout": {
                "title": f"Main Effects Plot for {y_col}",
                "xaxis": {"title": "Factor Level", "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": f"Mean {y_col}", "showgrid": True, "gridcolor": "#ececec"},
                "legend": {"orientation": "h", "y": -0.2}
            }
        }

        return AnalysisResult(
            title=f"Main Effects Plot: {y_col}",
            subtitle=f"Overall Grand Mean = {grand_mean:.4f} | {len(factors)} Factors Plotted",
            tables=[summary_table],
            plotly_figure=plotly_fig,
            statistics={"grand_mean": grand_mean, "num_factors": len(factors)}
        )


# =====================================================================
# 2. INTERACTION PLOT
# =====================================================================
class InteractionPlotParams(BaseModel):
    response_column: str = Field(
        ...,
        description="Response Variable (Continuous Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    factor_x: str = Field(
        ...,
        description="X-Axis Factor",
        json_schema_extra={"ui_type": "column_picker"}
    )
    factor_trace: str = Field(
        ...,
        description="Legend / Trace Factor (Lines)",
        json_schema_extra={"ui_type": "column_picker"}
    )


class InteractionPlotPlugin(AnalysisPlugin):
    id = "interaction_plot"
    name = "Interaction Plot"
    menu_path = ["Stat", "ANOVA", "Interaction Plot"]
    description = "Displays the response means for two factors simultaneously to evaluate interaction effects (non-parallel lines)."
    param_schema = InteractionPlotParams

    def execute(self, df: pd.DataFrame, params: InteractionPlotParams) -> AnalysisResult:
        y_col = params.response_column
        fx = params.factor_x
        ft = params.factor_trace

        if y_col not in df.columns or fx not in df.columns or ft not in df.columns:
            raise ValueError("Select valid response, X-axis factor, and legend trace factor.")

        sub_df = df[[y_col, fx, ft]].dropna().copy().reset_index(drop=True)
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        if len(sub_df) < 4:
            raise ValueError("Interaction Plot requires at least 4 observations.")

        x_levels = sorted(sub_df[fx].astype(str).unique())
        trace_levels = sorted(sub_df[ft].astype(str).unique())

        traces = []
        cell_rows = []

        for t_lvl in trace_levels:
            t_sub = sub_df[sub_df[ft].astype(str) == t_lvl]
            grp = t_sub.groupby(t_sub[fx].astype(str))[y_col]
            m_dict = grp.mean().to_dict()
            c_dict = grp.count().to_dict()

            y_vals = [m_dict.get(x_lvl, None) for x_lvl in x_levels]

            traces.append({
                "type": "scatter",
                "mode": "lines+markers",
                "x": x_levels,
                "y": y_vals,
                "name": f"{ft} = {t_lvl}",
                "marker": {"size": 8}
            })

            for x_lvl in x_levels:
                if x_lvl in m_dict:
                    cell_rows.append([fx, x_lvl, ft, t_lvl, str(c_dict[x_lvl]), f"{m_dict[x_lvl]:.4f}"])

        cell_table = TableResult(
            title=f"Interaction Cell Means for {y_col} by ({fx}, {ft})",
            headers=["Factor X", "Level X", "Factor Trace", "Level Trace", "N", "Cell Mean"],
            rows=cell_rows
        )

        plotly_fig = {
            "data": traces,
            "layout": {
                "title": f"Interaction Plot for {y_col} ({fx} × {ft})",
                "xaxis": {"title": fx, "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": f"Mean {y_col}", "showgrid": True, "gridcolor": "#ececec"},
                "legend": {"title": {"text": ft}, "orientation": "h", "y": -0.2}
            }
        }

        return AnalysisResult(
            title=f"Interaction Plot: {y_col}",
            subtitle=f"X-Axis: {fx} | Legend: {ft} | Total Cells = {len(x_levels) * len(trace_levels)}",
            tables=[cell_table],
            plotly_figure=plotly_fig,
            statistics={"x_levels": x_levels, "trace_levels": trace_levels}
        )


# =====================================================================
# 3. INTERVAL PLOT
# =====================================================================
class IntervalPlotParams(BaseModel):
    response_column: str = Field(
        ...,
        description="Response Variable (Continuous Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    factor_column: str = Field(
        ...,
        description="Grouping Factor",
        json_schema_extra={"ui_type": "column_picker"}
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%) - Default: 95.0"
    )


class IntervalPlotPlugin(AnalysisPlugin):
    id = "interval_plot"
    name = "Interval Plot"
    menu_path = ["Stat", "ANOVA", "Interval Plot"]
    description = "Displays group means with confidence interval error bars (t-distribution) to evaluate differences among groups."
    param_schema = IntervalPlotParams

    def execute(self, df: pd.DataFrame, params: IntervalPlotParams) -> AnalysisResult:
        y_col = params.response_column
        f_col = params.factor_column

        if y_col not in df.columns or f_col not in df.columns:
            raise ValueError("Select valid response and factor variables.")

        sub_df = df[[y_col, f_col]].dropna().copy().reset_index(drop=True)
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        if len(sub_df) < 4:
            raise ValueError("Interval Plot requires at least 4 observations.")

        groups = sorted(sub_df[f_col].astype(str).unique())
        alpha = 1.0 - (params.confidence_level / 100.0)

        means = []
        stds = []
        sizes = []
        ci_half_widths = []
        table_rows = []

        for g in groups:
            g_vals = sub_df[sub_df[f_col].astype(str) == g][y_col].to_numpy(dtype=float)
            n_g = len(g_vals)
            m_g = float(np.mean(g_vals))
            s_g = float(np.std(g_vals, ddof=1)) if n_g > 1 else 0.0

            if n_g > 1 and s_g > 1e-12:
                t_crit = stats.t.ppf(1.0 - alpha / 2.0, df=n_g - 1)
                hw = t_crit * (s_g / math.sqrt(n_g))
            else:
                hw = 0.0

            means.append(m_g)
            stds.append(s_g)
            sizes.append(n_g)
            ci_half_widths.append(hw)

            table_rows.append([
                g,
                str(n_g),
                f"{m_g:.4f}",
                f"{s_g:.4f}",
                f"({m_g - hw:.4f}, {m_g + hw:.4f})"
            ])

        summary_table = TableResult(
            title=f"Interval Summary Table ({params.confidence_level:.0f}% Confidence Intervals)",
            headers=[f_col, "N", "Mean", "StDev", f"{params.confidence_level:.0f}% CI for Mean"],
            rows=table_rows
        )

        plotly_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": groups,
                    "y": means,
                    "error_y": {
                        "type": "data",
                        "array": ci_half_widths,
                        "visible": True,
                        "color": "#0078d4",
                        "thickness": 2,
                        "width": 6
                    },
                    "name": "Mean with 95% CI",
                    "marker": {"color": "#0078d4", "size": 8}
                }
            ],
            "layout": {
                "title": f"Interval Plot of {y_col} by {f_col} ({params.confidence_level:.0f}% CI for the Mean)",
                "xaxis": {"title": f_col, "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": f"{y_col}", "showgrid": True, "gridcolor": "#ececec"},
            }
        }

        return AnalysisResult(
            title=f"Interval Plot: {y_col} by {f_col}",
            subtitle=f"{len(groups)} Groups | Confidence Level: {params.confidence_level:.1f}%",
            tables=[summary_table],
            plotly_figure=plotly_fig,
            statistics={
                "group_means": dict(zip(groups, means)),
                "group_stds": dict(zip(groups, stds)),
                "ci_widths": dict(zip(groups, ci_half_widths))
            }
        )
