import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import (
    get_spc_factors,
    evaluate_nelson_rules,
    build_single_spc_plot,
    NELSON_TEST_DESCRIPTIONS
)


class XbarOnlyParams(BaseModel):
    measurement_col: str = Field(..., description="Measurement Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    subgroup_size: int = Field(5, description="Subgroup size (n >= 2)", json_schema_extra={"ui_type": "number"})
    historical_mean: Optional[float] = Field(None, description="Historical Mean (mu)", json_schema_extra={"ui_type": "number"})
    historical_sigma: Optional[float] = Field(None, description="Historical Sigma (sigma)", json_schema_extra={"ui_type": "number"})
    test_1: bool = Field(True, description="Test 1: 1 point > 3s from center line", json_schema_extra={"ui_type": "checkbox"})
    test_2: bool = Field(True, description="Test 2: 9 points in a row on same side of center line", json_schema_extra={"ui_type": "checkbox"})
    test_3: bool = Field(True, description="Test 3: 6 points in a row, all increasing or decreasing", json_schema_extra={"ui_type": "checkbox"})
    test_4: bool = Field(True, description="Test 4: 14 points in a row, alternating up and down", json_schema_extra={"ui_type": "checkbox"})
    test_5: bool = Field(False, description="Test 5: 2 out of 3 points > 2s (same side)", json_schema_extra={"ui_type": "checkbox"})
    test_6: bool = Field(False, description="Test 6: 4 out of 5 points > 1s (same side)", json_schema_extra={"ui_type": "checkbox"})
    test_7: bool = Field(False, description="Test 7: 15 points in a row within 1s", json_schema_extra={"ui_type": "checkbox"})
    test_8: bool = Field(False, description="Test 8: 8 points in a row > 1s with none within 1s", json_schema_extra={"ui_type": "checkbox"})


class XbarOnlyPlugin(AnalysisPlugin):
    id = "xbar_only"
    name = "Xbar Chart"
    menu_path = ["Stat", "Control Charts", "Variables Charts for Subgroups", "Xbar Chart"]
    description = "Displays the Xbar chart for subgroup means alone."
    param_schema = XbarOnlyParams

    def execute(self, df: pd.DataFrame, params: XbarOnlyParams) -> AnalysisResult:
        if params.measurement_col not in df.columns:
            raise ValueError(f"Column '{params.measurement_col}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[params.measurement_col], errors="coerce").dropna().to_numpy(dtype=float)
        n = max(2, int(params.subgroup_size))

        if len(raw_series) < n * 2:
            raise ValueError(f"Xbar Chart requires at least 2 complete subgroups of size {n}.")

        k = len(raw_series) // n
        trimmed = raw_series[: k * n].reshape(k, n)
        means = np.mean(trimmed, axis=1)
        ranges = np.ptp(trimmed, axis=1)

        factors = get_spc_factors(n)
        r_bar = float(np.mean(ranges))
        sigma_est = (r_bar / factors["d2"]) if not params.historical_sigma else float(params.historical_sigma)
        cl = float(np.mean(means)) if params.historical_mean is None else float(params.historical_mean)

        se_xbar = sigma_est / np.sqrt(n)
        ucl = cl + 3.0 * se_xbar
        lcl = cl - 3.0 * se_xbar

        active_tests = []
        for i in range(1, 9):
            if getattr(params, f"test_{i}", False):
                active_tests.append(i)

        fails = evaluate_nelson_rules(means, cl, se_xbar, active_tests)

        test_rows = []
        for idx, tests in sorted(fails.items()):
            for t in tests:
                test_rows.append([idx + 1, f"{means[idx]:.4f}", f"Test {t}: {NELSON_TEST_DESCRIPTIONS.get(t, '')}"])

        fig = build_single_spc_plot(
            title=f"Xbar Chart of {params.measurement_col}",
            y_label="Sample Mean (Xbar)",
            subgroups=list(range(1, k + 1)),
            values=means,
            cl=cl,
            ucl=ucl,
            lcl=lcl,
            failed_points=fails
        )

        return AnalysisResult(
            title="Xbar Chart",
            subtitle=f"{params.measurement_col} (n={n})",
            text_output=f"Xbar Chart for {params.measurement_col}\nUCL = {ucl:.4f}, CL = {cl:.4f}, LCL = {lcl:.4f}\nEstimated Sigma = {sigma_est:.4f}",
            tables=[
                TableResult(title="Control Limits Summary", headers=["Metric", "Value"], rows=[
                    ["Center Line (CL)", f"{cl:.4f}"], ["Upper Control Limit (UCL)", f"{ucl:.4f}"], ["Lower Control Limit (LCL)", f"{lcl:.4f}"], ["Subgroup Size (n)", str(n)]
                ]),
                TableResult(title="Test Results / Violations", headers=["Subgroup", "Value", "Failed Test"], rows=test_rows)
            ],
            statistics={"cl": cl, "ucl": ucl, "lcl": lcl, "sigma_est": sigma_est},
            plotly_figure=fig
        )
