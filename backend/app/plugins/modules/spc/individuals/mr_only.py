import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import (
    evaluate_nelson_rules,
    build_single_spc_plot
)


class MROnlyParams(BaseModel):
    measurement_col: str = Field(..., description="Measurement Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    historical_sigma: Optional[float] = Field(None, description="Historical Standard Deviation (sigma)", json_schema_extra={"ui_type": "number"})


class MROnlyPlugin(AnalysisPlugin):
    id = "mr_only"
    name = "Moving Range Chart"
    menu_path = ["Stat", "Control Charts", "Variables Charts for Individuals", "Moving Range Chart"]
    description = "Displays the Moving Range (MR) chart alone."
    param_schema = MROnlyParams

    def execute(self, df: pd.DataFrame, params: MROnlyParams) -> AnalysisResult:
        if params.measurement_col not in df.columns:
            raise ValueError(f"Column '{params.measurement_col}' not found in active worksheet.")

        values = pd.to_numeric(df[params.measurement_col], errors="coerce").dropna().to_numpy(dtype=float)
        n = len(values)
        if n < 3:
            raise ValueError("Moving Range chart requires at least 3 data values.")

        mr = np.abs(np.diff(values))
        d2_2 = 1.128
        d3_2 = 0.8525
        D4_2 = 3.267

        mr_bar = float(np.mean(mr))
        sigma_est = (mr_bar / d2_2) if not params.historical_sigma else float(params.historical_sigma)

        cl = (d2_2 * sigma_est) if params.historical_sigma else mr_bar
        ucl = D4_2 * cl if not params.historical_sigma else (d2_2 + 3.0 * d3_2) * sigma_est
        lcl = 0.0

        fails = evaluate_nelson_rules(mr, cl, d3_2 * sigma_est, [1])

        test_rows = []
        for idx, tests in sorted(fails.items()):
            test_rows.append([idx + 2, f"{mr[idx]:.4f}", "Point > 3 standard deviations from CL"])

        fig = build_single_spc_plot(
            title=f"Moving Range Chart of {params.measurement_col}",
            y_label="Moving Range (MR)",
            subgroups=list(range(2, n + 1)),
            values=mr,
            cl=cl,
            ucl=ucl,
            lcl=lcl,
            failed_points=fails
        )

        return AnalysisResult(
            title="Moving Range Chart",
            subtitle=params.measurement_col,
            text_output=f"Moving Range Chart for {params.measurement_col}\nUCL = {ucl:.4f}, CL = {cl:.4f}, LCL = {lcl:.4f}\nEstimated Sigma = {sigma_est:.4f}",
            tables=[
                TableResult(title="Control Limits Summary", headers=["Metric", "Value"], rows=[
                    ["Center Line (CL)", f"{cl:.4f}"], ["Upper Control Limit (UCL)", f"{ucl:.4f}"], ["Lower Control Limit (LCL)", f"{lcl:.4f}"], ["Estimated Sigma", f"{sigma_est:.4f}"]
                ]),
                TableResult(title="Test Results / Violations", headers=["Observation", "Value", "Failed Test"], rows=test_rows)
            ],
            statistics={"cl": cl, "ucl": ucl, "lcl": lcl, "sigma_est": sigma_est},
            plotly_figure=fig
        )
