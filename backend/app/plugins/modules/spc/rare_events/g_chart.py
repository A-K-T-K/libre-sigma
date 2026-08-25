import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import build_single_spc_plot


class GChartParams(BaseModel):
    opportunities_col: str = Field(..., description="Opportunities / Days between events column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    historical_g: Optional[float] = Field(None, description="Historical Mean (g_bar)", json_schema_extra={"ui_type": "number"})


class GChartPlugin(AnalysisPlugin):
    id = "g_chart"
    name = "G Chart"
    menu_path = ["Stat", "Control Charts", "Rare Event Charts", "G Chart"]
    description = "Monitors the number of opportunities, days, or items between rare events using the Geometric distribution."
    param_schema = GChartParams

    def execute(self, df: pd.DataFrame, params: GChartParams) -> AnalysisResult:
        if params.opportunities_col not in df.columns:
            raise ValueError(f"Column '{params.opportunities_col}' not found in active worksheet.")

        g_vals = pd.to_numeric(df[params.opportunities_col], errors="coerce").dropna().to_numpy(dtype=float)
        k = len(g_vals)
        if k < 2:
            raise ValueError("G Chart requires at least 2 events.")

        g_bar = float(np.mean(g_vals)) if params.historical_g is None else float(params.historical_g)
        p_est = 1.0 / (g_bar + 1.0) if g_bar > 0 else 0.5

        # Limits (Geometric standard deviation = sqrt(g_bar * (g_bar + 1)))
        se_g = np.sqrt(g_bar * (g_bar + 1.0))
        ucl = g_bar + 3.0 * se_g
        lcl = max(0.0, g_bar - 3.0 * se_g)

        fails = {i: [1] for i in range(k) if g_vals[i] > ucl or g_vals[i] < lcl}
        test_rows = [[i + 1, int(g_vals[i]), f"{ucl:.2f}", f"{lcl:.2f}", "Point beyond control limits"] for i in sorted(fails.keys())]

        fig = build_single_spc_plot(
            title=f"G Chart of {params.opportunities_col}",
            y_label="Opportunities / Days Between Events",
            subgroups=list(range(1, k + 1)),
            values=g_vals,
            cl=g_bar,
            ucl=ucl,
            lcl=lcl,
            failed_points=fails
        )

        return AnalysisResult(
            title="G Chart",
            subtitle=f"{params.opportunities_col} (g_bar={g_bar:.2f})",
            text_output=f"G Chart for {params.opportunities_col}\nCenter Line g_bar = {g_bar:.2f}, UCL = {ucl:.2f}, LCL = {lcl:.2f}\nEstimated Event Probability p = {p_est:.6f}",
            tables=[
                TableResult(title="G Chart Summary", headers=["Metric", "Value"], rows=[
                    ["Center Line (g_bar)", f"{g_bar:.2f}"], ["Upper Control Limit (UCL)", f"{ucl:.2f}"], ["Lower Control Limit (LCL)", f"{lcl:.2f}"], ["Estimated Event Probability", f"{p_est:.6f}"], ["Number of Events", str(k)]
                ]),
                TableResult(title="Test Results / Violations", headers=["Event #", "Opportunities", "UCL", "LCL", "Violation"], rows=test_rows)
            ],
            statistics={"g_bar": g_bar, "ucl": ucl, "lcl": lcl, "p_est": p_est, "failed_count": len(fails)},
            plotly_figure=fig
        )
