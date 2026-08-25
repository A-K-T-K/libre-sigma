import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import evaluate_nelson_rules, build_single_spc_plot, NELSON_TEST_DESCRIPTIONS


class CChartParams(BaseModel):
    defects_col: str = Field(..., description="Defects Count Column (per inspection unit)", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    historical_c: Optional[float] = Field(None, description="Historical Mean Defects (c)", json_schema_extra={"ui_type": "number"})
    test_1: bool = Field(True, description="Test 1: 1 point > 3s from center line", json_schema_extra={"ui_type": "checkbox"})
    test_2: bool = Field(True, description="Test 2: 9 points in a row on same side of center line", json_schema_extra={"ui_type": "checkbox"})
    test_3: bool = Field(True, description="Test 3: 6 points in a row, all increasing or decreasing", json_schema_extra={"ui_type": "checkbox"})
    test_4: bool = Field(True, description="Test 4: 14 points in a row, alternating up and down", json_schema_extra={"ui_type": "checkbox"})


class CChartPlugin(AnalysisPlugin):
    id = "c_chart"
    name = "C Chart"
    menu_path = ["Stat", "Control Charts", "Attributes Charts", "C Chart"]
    description = "Monitors total number of defects per constant unit of inspection."
    param_schema = CChartParams

    def execute(self, df: pd.DataFrame, params: CChartParams) -> AnalysisResult:
        if params.defects_col not in df.columns:
            raise ValueError(f"Column '{params.defects_col}' not found in active worksheet.")

        c_vals = pd.to_numeric(df[params.defects_col], errors="coerce").dropna().to_numpy(dtype=float)
        k = len(c_vals)
        if k < 2:
            raise ValueError("C Chart requires at least 2 inspection units.")

        cl = float(np.mean(c_vals)) if params.historical_c is None else float(params.historical_c)
        sigma_c = np.sqrt(cl)
        ucl = cl + 3.0 * sigma_c
        lcl = max(0.0, cl - 3.0 * sigma_c)

        active_tests = []
        for t in range(1, 5):
            if getattr(params, f"test_{t}", False):
                active_tests.append(t)

        fails = evaluate_nelson_rules(c_vals, cl, sigma_c, active_tests)

        test_rows = []
        for idx, tests in sorted(fails.items()):
            for t in tests:
                test_rows.append([idx + 1, int(c_vals[idx]), f"Test {t}: {NELSON_TEST_DESCRIPTIONS.get(t, '')}"])

        fig = build_single_spc_plot(
            title=f"C Chart of {params.defects_col}",
            y_label="Defect Count (C)",
            subgroups=list(range(1, k + 1)),
            values=c_vals,
            cl=cl,
            ucl=ucl,
            lcl=lcl,
            failed_points=fails
        )

        return AnalysisResult(
            title="C Chart",
            subtitle=f"{params.defects_col} (c_bar={cl:.3f})",
            text_output=f"C Chart for {params.defects_col}\nCenter Line = {cl:.3f}, UCL = {ucl:.3f}, LCL = {lcl:.3f}",
            tables=[
                TableResult(title="Control Limits Summary", headers=["Metric", "Value"], rows=[
                    ["Center Line (c_bar)", f"{cl:.3f}"], ["Upper Control Limit (UCL)", f"{ucl:.3f}"], ["Lower Control Limit (LCL)", f"{lcl:.3f}"], ["Total Defects", str(int(np.sum(c_vals)))]
                ]),
                TableResult(title="Test Violations", headers=["Sample", "Defects", "Failed Test"], rows=test_rows)
            ],
            statistics={"cl": cl, "ucl": ucl, "lcl": lcl},
            plotly_figure=fig
        )
