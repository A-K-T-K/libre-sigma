import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import (
    get_spc_factors,
    evaluate_nelson_rules,
    build_dual_spc_plot,
    NELSON_TEST_DESCRIPTIONS
)


class IMRParams(BaseModel):
    measurement_col: str = Field(
        ...,
        description="Measurement Column (Individual values)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    historical_mean: Optional[float] = Field(
        None,
        description="Historical Mean (mu)",
        json_schema_extra={"ui_type": "number"}
    )
    historical_sigma: Optional[float] = Field(
        None,
        description="Historical Standard Deviation (sigma)",
        json_schema_extra={"ui_type": "number"}
    )
    test_1: bool = Field(True, description="Test 1: 1 point > 3s from center line", json_schema_extra={"ui_type": "checkbox"})
    test_2: bool = Field(True, description="Test 2: 9 points in a row on same side of center line", json_schema_extra={"ui_type": "checkbox"})
    test_3: bool = Field(True, description="Test 3: 6 points in a row, all increasing or decreasing", json_schema_extra={"ui_type": "checkbox"})
    test_4: bool = Field(True, description="Test 4: 14 points in a row, alternating up and down", json_schema_extra={"ui_type": "checkbox"})
    test_5: bool = Field(False, description="Test 5: 2 out of 3 points > 2s (same side)", json_schema_extra={"ui_type": "checkbox"})
    test_6: bool = Field(False, description="Test 6: 4 out of 5 points > 1s (same side)", json_schema_extra={"ui_type": "checkbox"})
    test_7: bool = Field(False, description="Test 7: 15 points in a row within 1s", json_schema_extra={"ui_type": "checkbox"})
    test_8: bool = Field(False, description="Test 8: 8 points in a row > 1s with none within 1s", json_schema_extra={"ui_type": "checkbox"})


class IMRPlugin(AnalysisPlugin):
    id = "i_mr"
    name = "I-MR Chart"
    menu_path = ["Stat", "Control Charts", "Variables Charts for Individuals", "I-MR"]
    description = "Individual Value and Moving Range chart for monitoring individual observations when subgrouping is not possible."
    param_schema = IMRParams

    def execute(self, df: pd.DataFrame, params: IMRParams) -> AnalysisResult:
        if params.measurement_col not in df.columns:
            raise ValueError(f"Column '{params.measurement_col}' not found in active worksheet.")

        values = pd.to_numeric(df[params.measurement_col], errors="coerce").dropna().to_numpy(dtype=float)
        n = len(values)
        if n < 3:
            raise ValueError(f"I-MR Chart requires at least 3 individual observations (found {n}).")

        # Moving Range (span = 2)
        mr = np.abs(np.diff(values))
        # Pad first point for MR chart matching length
        mr_padded = np.insert(mr, 0, np.nan)

        d2_2 = 1.128
        d3_2 = 0.8525
        D4_2 = 3.267
        D3_2 = 0.0

        mr_bar = float(np.nanmean(mr))
        sigma_est = (mr_bar / d2_2) if not params.historical_sigma else float(params.historical_sigma)

        # I Chart Limits
        i_cl = float(np.mean(values)) if params.historical_mean is None else float(params.historical_mean)
        i_ucl = i_cl + 3.0 * sigma_est
        i_lcl = i_cl - 3.0 * sigma_est

        # MR Chart Limits
        mr_cl = (d2_2 * sigma_est) if params.historical_sigma else mr_bar
        mr_ucl = D4_2 * mr_cl if not params.historical_sigma else (d2_2 + 3.0 * d3_2) * sigma_est
        mr_lcl = 0.0

        # Nelson Rules
        active_tests = []
        for t in range(1, 9):
            if getattr(params, f"test_{t}", False):
                active_tests.append(t)

        i_fails = evaluate_nelson_rules(values, i_cl, sigma_est, active_tests)
        mr_fails = evaluate_nelson_rules(mr, mr_cl, d3_2 * sigma_est, [1])
        # Shift mr fails by 1 for 1-based index
        mr_fails_adjusted = {k + 1: v for k, v in mr_fails.items()}

        # Tables
        summary_headers = ["Chart", "Center Line (CL)", "Upper Control Limit (UCL)", "Lower Control Limit (LCL)", "Estimated Sigma (σ)"]
        summary_rows = [
            ["Individual Value (I)", f"{i_cl:.4f}", f"{i_ucl:.4f}", f"{i_lcl:.4f}", f"{sigma_est:.4f}"],
            ["Moving Range (MR)", f"{mr_cl:.4f}", f"{mr_ucl:.4f}", f"{mr_lcl:.4f}", f"{sigma_est:.4f}"]
        ]

        test_results_headers = ["Chart", "Observation", "Value", "Failed Test(s)"]
        test_results_rows = []
        for idx, tests in sorted(i_fails.items()):
            for t in tests:
                test_results_rows.append(["Individuals", idx + 1, f"{values[idx]:.4f}", f"Test {t}: {NELSON_TEST_DESCRIPTIONS.get(t, '')}"])
        for idx, tests in sorted(mr_fails_adjusted.items()):
            for t in tests:
                test_results_rows.append(["Moving Range", idx + 1, f"{mr_padded[idx]:.4f}", f"Test {t}: Point > 3 standard deviations from CL"])

        text_lines = [
            f"I-MR Chart of {params.measurement_col}",
            "",
            "Control Limits and Parameters:",
            f"  Number of Observations: N = {n}",
            f"  Estimated Process Sigma: s = {sigma_est:.4f} (MRbar / 1.128)",
            "",
            "Individual Value (I) Chart:",
            f"  UCL = {i_ucl:.4f},  CL = {i_cl:.4f},  LCL = {i_lcl:.4f}",
            "Moving Range (MR) Chart:",
            f"  UCL = {mr_ucl:.4f},  CL = {mr_cl:.4f},  LCL = {mr_lcl:.4f}",
        ]

        # Valid MR values array for plot
        mr_plot_vals = np.array([mr[i-1] if i > 0 else mr[0] for i in range(n)])

        fig = build_dual_spc_plot(
            title=f"I-MR Chart of {params.measurement_col}",
            top_label="Individual Value",
            bot_label="Moving Range",
            subgroups=list(range(1, n + 1)),
            top_values=values,
            top_cl=i_cl,
            top_ucl=i_ucl,
            top_lcl=i_lcl,
            top_fails=i_fails,
            bot_values=mr_plot_vals,
            bot_cl=mr_cl,
            bot_ucl=mr_ucl,
            bot_lcl=mr_lcl,
            bot_fails=mr_fails_adjusted,
        )

        return AnalysisResult(
            title="I-MR Chart",
            subtitle=params.measurement_col,
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title="Control Limits Summary", headers=summary_headers, rows=summary_rows),
                TableResult(title="Test Results / Violations", headers=test_results_headers, rows=test_results_rows)
            ],
            statistics={"sigma_est": sigma_est, "i_cl": i_cl, "mr_cl": mr_cl, "failed_count": len(test_results_rows)},
            plotly_figure=fig
        )
