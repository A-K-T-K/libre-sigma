"""
Run Chart Plugin for OpenMinitab Quality Tools.
Performs run chart analysis with statistical tests for clustering, mixtures, trends, and oscillation.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class RunChartParams(BaseModel):
    data_column: str = Field(
        ...,
        description="Measurement Variable",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    subgroup_method: str = Field(
        "single",
        description="Subgrouping Option",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Subgroup size (Constant)", "value": "single"},
                {"label": "Subgroup column", "value": "column"}
            ]
        }
    )
    subgroup_size: int = Field(1, ge=1, le=1000, description="Subgroup Size (if constant)")
    subgroup_column: Optional[str] = Field(
        None,
        description="Subgroup Variable (if column selected)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    reference_type: str = Field(
        "median",
        description="Reference Line",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Median", "value": "median"},
                {"label": "Mean", "value": "mean"}
            ]
        }
    )
    historical_value: Optional[float] = Field(None, description="Historical reference value (optional)")


class RunChartPlugin(AnalysisPlugin):
    id = "run_chart"
    name = "Run Chart"
    menu_path = ["Stat", "Quality Tools", "Run Chart"]
    description = "Displays process performance over time with tests for randomness (clustering, mixtures, trends, oscillation)."
    param_schema = RunChartParams

    def execute(self, df: pd.DataFrame, params: RunChartParams) -> AnalysisResult:
        data_col = params.data_column
        if data_col not in df.columns:
            raise ValueError(f"Column '{data_col}' not found in active worksheet.")

        # Extract numeric series
        series = pd.to_numeric(df[data_col], errors="coerce").dropna()
        if len(series) < 4:
            raise ValueError("Run Chart requires at least 4 valid numeric observations.")

        # Handle subgrouping
        if params.subgroup_method == "column" and params.subgroup_column and params.subgroup_column in df.columns:
            sub_col = df.loc[series.index, params.subgroup_column]
            grouped = df.loc[series.index].groupby(sub_col, sort=False)[data_col]
            y_values = grouped.mean().to_numpy(dtype=float) if params.reference_type == "mean" else grouped.median().to_numpy(dtype=float)
            x_labels = [str(k) for k in grouped.groups.keys()]
            subgroup_sizes = grouped.count().to_numpy()
        elif params.subgroup_size > 1:
            k = params.subgroup_size
            vals = series.to_numpy(dtype=float)
            n_chunks = len(vals) // k
            if n_chunks < 2:
                y_values = vals
                x_labels = [str(i + 1) for i in range(len(vals))]
                subgroup_sizes = np.ones(len(vals), dtype=int)
            else:
                chunks = [vals[i * k:(i + 1) * k] for i in range(n_chunks)]
                remainder = vals[n_chunks * k:]
                if len(remainder) > 0:
                    chunks.append(remainder)
                y_values = np.array([np.mean(c) if params.reference_type == "mean" else np.median(c) for c in chunks], dtype=float)
                x_labels = [str(i + 1) for i in range(len(chunks))]
                subgroup_sizes = np.array([len(c) for c in chunks])
        else:
            y_values = series.to_numpy(dtype=float)
            x_labels = [str(i + 1) for i in range(len(y_values))]
            subgroup_sizes = np.ones(len(y_values), dtype=int)

        n_pts = len(y_values)
        if n_pts < 2:
            raise ValueError("Need at least 2 subgrouped points to construct Run Chart.")

        # Reference line value
        if params.historical_value is not None:
            ref_val = float(params.historical_value)
        elif params.reference_type == "mean":
            ref_val = float(np.mean(y_values))
        else:
            ref_val = float(np.median(y_values))

        # --- Test 1: Runs About Reference Line (Median/Mean) ---
        diffs = y_values - ref_val
        # Exclude points exactly on reference line
        valid_mask = np.abs(diffs) > 1e-12
        filtered_diffs = diffs[valid_mask]
        n1 = int(np.sum(filtered_diffs > 0)) # Above
        n2 = int(np.sum(filtered_diffs < 0)) # Below
        N_med = n1 + n2

        if N_med > 1 and n1 > 0 and n2 > 0:
            # Count observed runs
            signs = np.sign(filtered_diffs)
            runs_med_obs = 1 + int(np.sum(signs[:-1] != signs[1:]))
            mu_med = 1.0 + (2.0 * n1 * n2) / N_med
            var_med = (2.0 * n1 * n2 * (2.0 * n1 * n2 - N_med)) / (N_med ** 2 * (N_med - 1))
            sigma_med = math.sqrt(max(1e-12, var_med))

            # Continuity correction
            z_clust = (runs_med_obs - mu_med + 0.5) / sigma_med
            z_mix = (runs_med_obs - mu_med - 0.5) / sigma_med

            p_clustering = float(stats.norm.cdf(z_clust))
            p_mixture = float(1.0 - stats.norm.cdf(z_mix))
        else:
            runs_med_obs = 1
            mu_med = 1.0
            p_clustering = 1.0
            p_mixture = 1.0

        # --- Test 2: Runs Up / Down ---
        diffs_updown = np.diff(y_values)
        valid_ud = diffs_updown[np.abs(diffs_updown) > 1e-12]
        N_ud = len(valid_ud) + 1

        if N_ud >= 3 and len(valid_ud) > 0:
            signs_ud = np.sign(valid_ud)
            runs_ud_obs = 1 + int(np.sum(signs_ud[:-1] != signs_ud[1:]))
            mu_ud = (2.0 * N_ud - 1.0) / 3.0
            var_ud = (16.0 * N_ud - 29.0) / 90.0
            sigma_ud = math.sqrt(max(1e-12, var_ud))

            z_trend = (runs_ud_obs - mu_ud + 0.5) / sigma_ud
            z_osc = (runs_ud_obs - mu_ud - 0.5) / sigma_ud

            p_trend = float(stats.norm.cdf(z_trend))
            p_oscillation = float(1.0 - stats.norm.cdf(z_osc))
        else:
            runs_ud_obs = 1
            mu_ud = 1.0
            p_trend = 1.0
            p_oscillation = 1.0

        # Construct Minitab-style session log tables
        runs_table = TableResult(
            title="Number of Runs About Median and Up/Down",
            headers=["Test", "Observed Runs", "Expected Runs", "Longest Run", "Approx p-Value (Test 1)", "Approx p-Value (Test 2)"],
            rows=[
                [
                    "Runs About Median",
                    str(runs_med_obs),
                    f"{mu_med:.2f}",
                    "---",
                    f"Clustering: {p_clustering:.4f}",
                    f"Mixture: {p_mixture:.4f}"
                ],
                [
                    "Runs Up or Down",
                    str(runs_ud_obs),
                    f"{mu_ud:.2f}",
                    "---",
                    f"Trends: {p_trend:.4f}",
                    f"Oscillation: {p_oscillation:.4f}"
                ]
            ]
        )

        summary_table = TableResult(
            title="Run Chart Statistics",
            headers=["Metric", "Value"],
            rows=[
                ["Variable", data_col],
                ["Number of Observations", str(len(series))],
                ["Subgroup Size (mean)", f"{float(np.mean(subgroup_sizes)):.1f}"],
                ["Reference Line (" + params.reference_type.capitalize() + ")", f"{ref_val:.4f}"],
                ["Number of Points Plotted", str(n_pts)]
            ]
        )

        # Plotly Time-series Trace + Reference Line + Step line
        plotly_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": list(range(1, n_pts + 1)),
                    "y": y_values.tolist(),
                    "name": "Subgroup " + params.reference_type.capitalize(),
                    "line": {"color": "#0078d4", "width": 1.5},
                    "marker": {"size": 6, "color": "#004d2c", "symbol": "circle"}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [1, n_pts],
                    "y": [ref_val, ref_val],
                    "name": f"{params.reference_type.capitalize()} ({ref_val:.4f})",
                    "line": {"color": "#d13438", "width": 2, "dash": "solid"}
                }
            ],
            "layout": {
                "title": f"Run Chart of {data_col}",
                "xaxis": {"title": "Subgroup / Observation Index", "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": data_col, "showgrid": True, "gridcolor": "#ececec"},
                "showlegend": True,
                "legend": {"orientation": "h", "y": -0.2},
                "annotations": [
                    {
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.02,
                        "y": 0.98,
                        "text": f"<b>Runs About Median:</b> p(Cluster)={p_clustering:.3f}, p(Mix)={p_mixture:.3f}<br><b>Runs Up/Down:</b> p(Trend)={p_trend:.3f}, p(Osc)={p_oscillation:.3f}",
                        "showarrow": False,
                        "bgcolor": "rgba(255,255,255,0.85)",
                        "bordercolor": "#d2d0ce",
                        "borderwidth": 1,
                        "font": {"size": 11}
                    }
                ]
            }
        }

        return AnalysisResult(
            title=f"Run Chart of {data_col}",
            subtitle=f"Reference = {ref_val:.4f} | N = {n_pts}",
            tables=[summary_table, runs_table],
            plotly_figure=plotly_fig,
            statistics={
                "ref_val": ref_val,
                "n_points": n_pts,
                "runs_med_obs": runs_med_obs,
                "p_clustering": p_clustering,
                "p_mixture": p_mixture,
                "runs_ud_obs": runs_ud_obs,
                "p_trend": p_trend,
                "p_oscillation": p_oscillation
            }
        )
