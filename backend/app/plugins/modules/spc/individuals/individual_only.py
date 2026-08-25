import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import (
    evaluate_nelson_rules,
    build_single_spc_plot,
    NELSON_TEST_DESCRIPTIONS
)


class IndividualOnlyParams(BaseModel):
    measurement_col: str = Field(..., description="Measurement Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    historical_mean: Optional[float] = Field(None, description="Historical Mean (mu)", json_schema_extra={"ui_type": "number"})
    historical_sigma: Optional[float] = Field(None, description="Historical Standard Deviation (sigma)", json_schema_extra={"ui_type": "number"})
    test_1: bool = Field(True, description="Test 1: 1 point > 3s from center line", json_schema_extra={"ui_type": "checkbox"})
    test_2: bool = Field(True, description="Test 2: 9 points in a row on same side of center line", json_schema_extra={"ui_type": "checkbox"})
    test_3: bool = Field(True, description="Test 3: 6 points in a row, all increasing or decreasing", json_schema_extra={"ui_type": "checkbox"})
    test_4: bool = Field(True, description="Test 4: 14 points in a row, alternating up and down", json_schema_extra={"ui_type": "checkbox"})


class IndividualOnlyPlugin(AnalysisPlugin):
    id = "individual_only"
    name = "Individual Chart"
    menu_path = ["Stat", "Control Charts", "Variables Charts for Individuals", "Individuals Chart"]
    description = "Displays the Individual values (I) chart alone."
    param_schema = IndividualOnlyParams

    def execute(self, df: pd.DataFrame, params: IndividualOnlyParams) -> AnalysisResult:
        if params.measurement_col not in df.columns:
            raise ValueError(f"Column '{params.measurement_col}' not found in active worksheet.")

        values = pd.to_numeric(df[params.measurement_col], errors="coerce").dropna().to_numpy(dtype=float)
        n = len(values)
        if n < 3:
            raise ValueError("Individuals chart requires at least 3 data values.")

        mr = np.abs(np.diff(values))
        sigma_est = float(np.mean(mr) / 1.128) if not params.historical_sigma else float(params.historical_sigma)

        cl = float(np.mean(values)) if params.historical_mean is None else float(params.historical_mean)
        ucl = cl + 3.0 * sigma_est
        lcl = cl - 3.0 * sigma_est

        active_tests = []
        for t in range(1, 5):
            if getattr(params, f"test_{t}", False):
                active_tests.append(t)

        fails = evaluate_nelson_rules(values, cl, sigma_est, active_tests)

        test_rows = []
        for idx, tests in sorted(fails.items()):
            for t in tests:
                test_rows.append([idx + 1, f"{values[idx]:.4f}", f"Test {t}: {NELSON_TEST_DESCRIPTIONS.get(t, '')}"])

        fig = build_single_spc_plot(
            title=f"Individual Value Chart of {params.measurement_col}",
            y_label="Individual Value",
            subgroups=list(range(1, n + 1)),
            values=values,
            cl=cl,
            ucl=ucl,
            lcl=lcl,
            failed_points=fails
        )

        return AnalysisResult(
            title="Individual Chart",
            subtitle=params.measurement_col,
            text_output=f"Individual Chart for {params.measurement_col}\nUCL = {ucl:.4f}, CL = {cl:.4f}, LCL = {lcl:.4f}\nEstimated Sigma = {sigma_est:.4f}",
            tables=[
                TableResult(title="Control Limits Summary", headers=["Metric", "Value"], rows=[
                    ["Center Line (CL)", f"{cl:.4f}"], ["Upper Control Limit (UCL)", f"{ucl:.4f}"], ["Lower Control Limit (LCL)", f"{lcl:.4f}"], ["Estimated Sigma", f"{sigma_est:.4f}"]
                ]),
                TableResult(title="Test Results / Violations", headers=["Observation", "Value", "Failed Test"], rows=test_rows)
            ],
            statistics={"cl": cl, "ucl": ucl, "lcl": lcl, "sigma_est": sigma_est},
            plotly_figure=fig
        )
