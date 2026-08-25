import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import (
    get_spc_factors,
    evaluate_nelson_rules,
    build_single_spc_plot
)


class RChartParams(BaseModel):
    measurement_col: str = Field(..., description="Measurement Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    subgroup_size: int = Field(5, description="Subgroup size (n >= 2)", json_schema_extra={"ui_type": "number"})
    historical_sigma: Optional[float] = Field(None, description="Historical Sigma (sigma)", json_schema_extra={"ui_type": "number"})


class RChartPlugin(AnalysisPlugin):
    id = "r_chart"
    name = "R Chart"
    menu_path = ["Stat", "Control Charts", "Variables Charts for Subgroups", "R Chart"]
    description = "Displays the R chart for subgroup ranges."
    param_schema = RChartParams

    def execute(self, df: pd.DataFrame, params: RChartParams) -> AnalysisResult:
        if params.measurement_col not in df.columns:
            raise ValueError(f"Column '{params.measurement_col}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[params.measurement_col], errors="coerce").dropna().to_numpy(dtype=float)
        n = max(2, int(params.subgroup_size))

        if len(raw_series) < n * 2:
            raise ValueError(f"R Chart requires at least 2 complete subgroups of size {n}.")

        k = len(raw_series) // n
        trimmed = raw_series[: k * n].reshape(k, n)
        ranges = np.ptp(trimmed, axis=1)

        factors = get_spc_factors(n)
        d2, d3 = factors["d2"], factors["d3"]

        r_bar = float(np.mean(ranges))
        sigma_est = (r_bar / d2) if not params.historical_sigma else float(params.historical_sigma)

        cl = (d2 * sigma_est) if params.historical_sigma else r_bar
        ucl = factors["D4"] * cl if not params.historical_sigma else (d2 + 3.0 * d3) * sigma_est
        lcl = factors["D3"] * cl if not params.historical_sigma else max(0.0, (d2 - 3.0 * d3) * sigma_est)

        fails = evaluate_nelson_rules(ranges, cl, d3 * sigma_est, [1])

        test_rows = []
        for idx, tests in sorted(fails.items()):
            test_rows.append([idx + 1, f"{ranges[idx]:.4f}", "Point > 3 standard deviations from CL (Out of limit)"])

        fig = build_single_spc_plot(
            title=f"R Chart of {params.measurement_col}",
            y_label="Sample Range (R)",
            subgroups=list(range(1, k + 1)),
            values=ranges,
            cl=cl,
            ucl=ucl,
            lcl=lcl,
            failed_points=fails
        )

        return AnalysisResult(
            title="R Chart",
            subtitle=f"{params.measurement_col} (n={n})",
            text_output=f"R Chart for {params.measurement_col}\nUCL = {ucl:.4f}, CL = {cl:.4f}, LCL = {lcl:.4f}\nEstimated Sigma = {sigma_est:.4f}",
            tables=[
                TableResult(title="Control Limits Summary", headers=["Metric", "Value"], rows=[
                    ["Center Line (CL)", f"{cl:.4f}"], ["Upper Control Limit (UCL)", f"{ucl:.4f}"], ["Lower Control Limit (LCL)", f"{lcl:.4f}"], ["Subgroup Size (n)", str(n)]
                ]),
                TableResult(title="Test Results / Violations", headers=["Subgroup", "Value", "Failed Test"], rows=test_rows)
            ],
            statistics={"cl": cl, "ucl": ucl, "lcl": lcl, "sigma_est": sigma_est},
            plotly_figure=fig
        )
