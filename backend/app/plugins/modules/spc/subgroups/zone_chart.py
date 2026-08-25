import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import get_spc_factors


class ZoneChartParams(BaseModel):
    measurement_col: str = Field(..., description="Measurement Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    subgroup_size: int = Field(1, description="Subgroup size (n >= 1)", json_schema_extra={"ui_type": "number"})
    reset_score_on_signal: bool = Field(True, description="Reset cumulative score to 0 after out-of-control signal (Score >= 8)", json_schema_extra={"ui_type": "checkbox"})


class ZoneChartPlugin(AnalysisPlugin):
    id = "zone_chart"
    name = "Zone Chart"
    menu_path = ["Stat", "Control Charts", "Variables Charts for Subgroups", "Zone Chart"]
    description = "Tracks cumulative process scores across 1σ, 2σ, and 3σ zones and signals when cumulative score reaches 8."
    param_schema = ZoneChartParams

    def execute(self, df: pd.DataFrame, params: ZoneChartParams) -> AnalysisResult:
        if params.measurement_col not in df.columns:
            raise ValueError(f"Column '{params.measurement_col}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[params.measurement_col], errors="coerce").dropna().to_numpy(dtype=float)
        n = max(1, int(params.subgroup_size))

        if len(raw_series) < n * 2:
            raise ValueError(f"Zone Chart requires at least 2 complete subgroups.")

        k = len(raw_series) // n
        trimmed = raw_series[: k * n].reshape(k, n)
        means = np.mean(trimmed, axis=1)

        if n > 1:
            ranges = np.ptp(trimmed, axis=1)
            sigma_est = float(np.mean(ranges) / get_spc_factors(n)["d2"])
        else:
            mr = np.abs(np.diff(means))
            sigma_est = float(np.mean(mr) / 1.128) if len(mr) > 0 else float(np.std(means, ddof=1))

        cl = float(np.mean(means))
        se_mean = sigma_est / np.sqrt(n)

        # Compute Zone Scores:
        # Zone 1 (0 to 1s): Score = 0
        # Zone 2 (1s to 2s): Score = 2
        # Zone 3 (2s to 3s): Score = 4
        # Beyond 3s: Score = 8
        zone_scores = np.zeros(k, dtype=int)
        cum_scores = np.zeros(k, dtype=int)
        signal_flags = np.zeros(k, dtype=bool)

        current_side = 0  # +1 for above CL, -1 for below CL
        running_score = 0

        for i in range(k):
            diff = means[i] - cl
            z = abs(diff) / se_mean if se_mean > 0 else 0.0

            if z <= 1.0:
                pt_score = 0
            elif z <= 2.0:
                pt_score = 2
            elif z <= 3.0:
                pt_score = 4
            else:
                pt_score = 8

            zone_scores[i] = pt_score
            side = 1 if diff >= 0 else -1

            if side == current_side:
                running_score += pt_score
            else:
                current_side = side
                running_score = pt_score

            if running_score >= 8:
                signal_flags[i] = True
                cum_scores[i] = running_score
                if params.reset_score_on_signal:
                    running_score = 0
            else:
                cum_scores[i] = running_score

        # Plot: Cumulative Zone Score Chart
        x_axis = [str(i + 1) for i in range(k)]
        colors = ["#dc2626" if signal_flags[i] else "#1d4ed8" for i in range(k)]
        hover_texts = [
            f"Subgroup: {x_axis[i]}<br>Value: {means[i]:.4f}<br>Zone Score: {zone_scores[i]}<br><b>Cumulative Score: {cum_scores[i]}</b>" + ("<br><b style='color:red;'>SIGNAL: Score >= 8</b>" if signal_flags[i] else "")
            for i in range(k)
        ]

        plot_data = [
            {
                "type": "scatter",
                "mode": "lines+markers+text",
                "x": x_axis,
                "y": cum_scores.tolist(),
                "text": [str(c) for c in cum_scores],
                "textposition": "top center",
                "line": {"color": "#64748b", "width": 1.5},
                "marker": {"color": colors, "size": 8},
                "hovertext": hover_texts,
                "hoverinfo": "text",
            }
        ]

        layout = {
            "title": {"text": f"<b>Zone Control Chart for {params.measurement_col}</b>", "x": 0.5},
            "showlegend": False,
            "margin": {"l": 70, "r": 90, "t": 70, "b": 50},
            "height": 400,
            "xaxis": {"title": {"text": "Subgroup"}, "showgrid": True, "gridcolor": "#ececec"},
            "yaxis": {"title": {"text": "Cumulative Score"}, "range": [0, max(10, np.max(cum_scores) + 2)], "showgrid": True, "gridcolor": "#ececec"},
            "shapes": [
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": 8, "y1": 8, "line": {"color": "#dc2626", "width": 2, "dash": "dash"}},
            ],
            "annotations": [
                {"xref": "paper", "x": 1.01, "y": 8, "text": "<b>Limit = 8</b>", "showarrow": False, "font": {"color": "#dc2626", "size": 11}, "xanchor": "left"},
            ]
        }

        # Tables
        summary_headers = ["Subgroup", "Sample Value", "Zone Score", "Cumulative Score", "Signal Status"]
        summary_rows = [
            [i + 1, f"{means[i]:.4f}", int(zone_scores[i]), int(cum_scores[i]), "SIGNAL (Out of Control)" if signal_flags[i] else "In Control"]
            for i in range(k)
        ]

        text_lines = [
            f"Zone Chart for {params.measurement_col}",
            f"Subgroup size n = {n}, Centerline = {cl:.4f}, Estimated Sigma = {sigma_est:.4f}",
            "",
            f"Found {int(np.sum(signal_flags))} out-of-control signals (Cumulative Score >= 8).",
        ]

        return AnalysisResult(
            title="Zone Chart",
            subtitle=f"{params.measurement_col} (Limit=8)",
            text_output="\n".join(text_lines),
            tables=[TableResult(title="Zone Score Tracking Table", headers=summary_headers, rows=summary_rows)],
            statistics={"signals": int(np.sum(signal_flags)), "cl": cl, "sigma_est": sigma_est},
            plotly_figure={"data": plot_data, "layout": layout}
        )
