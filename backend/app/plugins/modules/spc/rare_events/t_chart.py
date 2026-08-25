import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import build_single_spc_plot


class TChartParams(BaseModel):
    time_col: str = Field(..., description="Time Elapsed Between Events Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    historical_t: Optional[float] = Field(None, description="Historical Mean Time (t_bar)", json_schema_extra={"ui_type": "number"})


class TChartPlugin(AnalysisPlugin):
    id = "t_chart"
    name = "T Chart"
    menu_path = ["Stat", "Control Charts", "Rare Event Charts", "T Chart"]
    description = "Monitors time between rare events using power transformation y = t^(1/3.6) for Exponential/Weibull data."
    param_schema = TChartParams

    def execute(self, df: pd.DataFrame, params: TChartParams) -> AnalysisResult:
        if params.time_col not in df.columns:
            raise ValueError(f"Column '{params.time_col}' not found in active worksheet.")

        raw_t = pd.to_numeric(df[params.time_col], errors="coerce").dropna().to_numpy(dtype=float)
        # Ensure positive values
        t_vals = raw_t[raw_t > 0]
        k = len(t_vals)
        if k < 3:
            raise ValueError("T Chart requires at least 3 positive time elapsed observations.")

        # Power transformation: y = t^(1 / 3.6) = t^(0.2777778)
        y_vals = np.power(t_vals, 1.0 / 3.6)
        mr_y = np.abs(np.diff(y_vals))
        sigma_y = float(np.mean(mr_y) / 1.128) if len(mr_y) > 0 else float(np.std(y_vals, ddof=1))

        y_cl = float(np.mean(y_vals))
        y_ucl = y_cl + 3.0 * sigma_y
        y_lcl = max(0.0, y_cl - 3.0 * sigma_y)

        # Invert limits back to time scale
        t_cl = float(np.power(y_cl, 3.6))
        t_ucl = float(np.power(y_ucl, 3.6))
        t_lcl = float(np.power(y_lcl, 3.6)) if y_lcl > 0 else 0.0

        fails = {i: [1] for i in range(k) if t_vals[i] > t_ucl or t_vals[i] < t_lcl}
        test_rows = [[i + 1, f"{t_vals[i]:.4f}", f"{t_ucl:.4f}", f"{t_lcl:.4f}", "Time beyond control limits"] for i in sorted(fails.keys())]

        fig = build_single_spc_plot(
            title=f"T Chart of {params.time_col} (Time Between Events)",
            y_label="Time Between Events (T)",
            subgroups=list(range(1, k + 1)),
            values=t_vals,
            cl=t_cl,
            ucl=t_ucl,
            lcl=t_lcl,
            failed_points=fails
        )

        return AnalysisResult(
            title="T Chart",
            subtitle=f"{params.time_col} (CL={t_cl:.4f})",
            text_output=f"T Chart for {params.time_col}\nCenter Line = {t_cl:.4f}, UCL = {t_ucl:.4f}, LCL = {t_lcl:.4f}\nTransformation: y = t^(1/3.6), sigma_y = {sigma_y:.4f}",
            tables=[
                TableResult(title="T Chart Control Limits", headers=["Metric", "Original Time Scale", "Transformed Scale (y)"], rows=[
                    ["Center Line (CL)", f"{t_cl:.4f}", f"{y_cl:.4f}"],
                    ["Upper Control Limit (UCL)", f"{t_ucl:.4f}", f"{y_ucl:.4f}"],
                    ["Lower Control Limit (LCL)", f"{t_lcl:.4f}", f"{y_lcl:.4f}"],
                ]),
                TableResult(title="Test Results / Violations", headers=["Event #", "Time Elapsed", "UCL", "LCL", "Violation"], rows=test_rows)
            ],
            statistics={"t_cl": t_cl, "t_ucl": t_ucl, "t_lcl": t_lcl, "failed_count": len(fails)},
            plotly_figure=fig
        )
