import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import evaluate_nelson_rules, build_single_spc_plot, NELSON_TEST_DESCRIPTIONS


class NPChartParams(BaseModel):
    defectives_col: str = Field(..., description="Defectives Count Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    subgroup_size: int = Field(50, description="Constant Subgroup Size (n)", json_schema_extra={"ui_type": "number"})
    historical_p: Optional[float] = Field(None, description="Historical Proportion (p)", json_schema_extra={"ui_type": "number"})
    test_1: bool = Field(True, description="Test 1: 1 point > 3s from center line", json_schema_extra={"ui_type": "checkbox"})
    test_2: bool = Field(True, description="Test 2: 9 points in a row on same side of center line", json_schema_extra={"ui_type": "checkbox"})
    test_3: bool = Field(True, description="Test 3: 6 points in a row, all increasing or decreasing", json_schema_extra={"ui_type": "checkbox"})
    test_4: bool = Field(True, description="Test 4: 14 points in a row, alternating up and down", json_schema_extra={"ui_type": "checkbox"})


class NPChartPlugin(AnalysisPlugin):
    id = "np_chart"
    name = "NP Chart"
    menu_path = ["Stat", "Control Charts", "Attributes Charts", "NP Chart"]
    description = "Monitors the count of nonconforming/defective units in constant sample sizes."
    param_schema = NPChartParams

    def execute(self, df: pd.DataFrame, params: NPChartParams) -> AnalysisResult:
        if params.defectives_col not in df.columns:
            raise ValueError(f"Column '{params.defectives_col}' not found in active worksheet.")

        np_vals = pd.to_numeric(df[params.defectives_col], errors="coerce").dropna().to_numpy(dtype=float)
        k = len(np_vals)
        if k < 2:
            raise ValueError("NP Chart requires at least 2 subgroups.")

        n = max(1, int(params.subgroup_size))
        p_bar = float(np.sum(np_vals) / (k * n)) if params.historical_p is None else float(params.historical_p)

        cl = n * p_bar
        sigma_np = np.sqrt(n * p_bar * (1.0 - p_bar))
        ucl = min(float(n), cl + 3.0 * sigma_np)
        lcl = max(0.0, cl - 3.0 * sigma_np)

        active_tests = []
        for t in range(1, 5):
            if getattr(params, f"test_{t}", False):
                active_tests.append(t)

        fails = evaluate_nelson_rules(np_vals, cl, sigma_np, active_tests)

        test_rows = []
        for idx, tests in sorted(fails.items()):
            for t in tests:
                test_rows.append([idx + 1, int(np_vals[idx]), f"Test {t}: {NELSON_TEST_DESCRIPTIONS.get(t, '')}"])

        fig = build_single_spc_plot(
            title=f"NP Chart of {params.defectives_col}",
            y_label="Defective Count (NP)",
            subgroups=list(range(1, k + 1)),
            values=np_vals,
            cl=cl,
            ucl=ucl,
            lcl=lcl,
            failed_points=fails
        )

        return AnalysisResult(
            title="NP Chart",
            subtitle=f"{params.defectives_col} (n={n})",
            text_output=f"NP Chart for {params.defectives_col}\nCenter Line = {cl:.3f}, UCL = {ucl:.3f}, LCL = {lcl:.3f}\nAverage Proportion p_bar = {p_bar:.4f}",
            tables=[
                TableResult(title="Control Limits Summary", headers=["Metric", "Value"], rows=[
                    ["Center Line (np_bar)", f"{cl:.3f}"], ["Upper Control Limit (UCL)", f"{ucl:.3f}"], ["Lower Control Limit (LCL)", f"{lcl:.3f}"], ["Subgroup Size (n)", str(n)], ["p_bar", f"{p_bar:.4f}"]
                ]),
                TableResult(title="Test Violations", headers=["Subgroup", "Defectives", "Failed Test"], rows=test_rows)
            ],
            statistics={"cl": cl, "ucl": ucl, "lcl": lcl, "p_bar": p_bar},
            plotly_figure=fig
        )
