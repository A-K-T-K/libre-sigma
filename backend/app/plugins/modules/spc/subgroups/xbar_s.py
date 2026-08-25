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


class XbarSParams(BaseModel):
    measurement_col: str = Field(
        ...,
        description="Measurement Data Column",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    subgroup_size: int = Field(
        5,
        description="Subgroup size (n >= 2)",
        json_schema_extra={"ui_type": "number"}
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


class XbarSPlugin(AnalysisPlugin):
    id = "xbar_s"
    name = "Xbar-S Chart"
    menu_path = ["Stat", "Control Charts", "Variables Charts for Subgroups", "Xbar-S"]
    description = "Monitors the process mean and standard deviation across subgroups using unbiasing constant c4."
    param_schema = XbarSParams

    def execute(self, df: pd.DataFrame, params: XbarSParams) -> AnalysisResult:
        if params.measurement_col not in df.columns:
            raise ValueError(f"Column '{params.measurement_col}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[params.measurement_col], errors="coerce").dropna().to_numpy(dtype=float)
        n = max(2, int(params.subgroup_size))

        if len(raw_series) < n * 2:
            raise ValueError(f"Xbar-S Chart requires at least 2 complete subgroups of size {n} (found {len(raw_series)} rows).")

        k_subgroups = len(raw_series) // n
        trimmed_data = raw_series[: k_subgroups * n].reshape(k_subgroups, n)

        subgroup_means = np.mean(trimmed_data, axis=1)
        subgroup_stdevs = np.std(trimmed_data, axis=1, ddof=1)

        factors = get_spc_factors(n)
        c4 = factors["c4"]
        c5 = factors["c5"]

        s_bar = float(np.mean(subgroup_stdevs))
        sigma_est = (s_bar / c4) if not params.historical_sigma else float(params.historical_sigma)
        x_dbar = float(np.mean(subgroup_means)) if params.historical_mean is None else float(params.historical_mean)

        # Xbar limits
        se_xbar = sigma_est / np.sqrt(n)
        xbar_ucl = x_dbar + 3.0 * se_xbar
        xbar_lcl = x_dbar - 3.0 * se_xbar
        xbar_cl = x_dbar

        # S limits
        s_cl = (c4 * sigma_est) if params.historical_sigma else s_bar
        s_ucl = factors["B4"] * s_cl if not params.historical_sigma else (c4 + 3.0 * c5) * sigma_est
        s_lcl = factors["B3"] * s_cl if not params.historical_sigma else max(0.0, (c4 - 3.0 * c5) * sigma_est)

        active_tests = []
        if params.test_1: active_tests.append(1)
        if params.test_2: active_tests.append(2)
        if params.test_3: active_tests.append(3)
        if params.test_4: active_tests.append(4)
        if params.test_5: active_tests.append(5)
        if params.test_6: active_tests.append(6)
        if params.test_7: active_tests.append(7)
        if params.test_8: active_tests.append(8)

        xbar_fails = evaluate_nelson_rules(subgroup_means, xbar_cl, se_xbar, active_tests)
        s_fails = evaluate_nelson_rules(subgroup_stdevs, s_cl, c5 * sigma_est, [1])

        # Tables
        summary_headers = ["Chart", "Center Line (CL)", "Upper Control Limit (UCL)", "Lower Control Limit (LCL)", "Subgroup Size (n)", "Estimated Sigma (σ)"]
        summary_rows = [
            ["Xbar Chart (Mean)", f"{xbar_cl:.4f}", f"{xbar_ucl:.4f}", f"{xbar_lcl:.4f}", str(n), f"{sigma_est:.4f}"],
            ["S Chart (StDev)", f"{s_cl:.4f}", f"{s_ucl:.4f}", f"{s_lcl:.4f}", str(n), f"{sigma_est:.4f}"]
        ]

        test_results_headers = ["Chart", "Subgroup", "Value", "Failed Test(s)"]
        test_results_rows = []
        for idx, tests in sorted(xbar_fails.items()):
            for t in tests:
                test_results_rows.append(["Xbar", idx + 1, f"{subgroup_means[idx]:.4f}", f"Test {t}: {NELSON_TEST_DESCRIPTIONS.get(t, '')}"])
        for idx, tests in sorted(s_fails.items()):
            for t in tests:
                test_results_rows.append(["S", idx + 1, f"{subgroup_stdevs[idx]:.4f}", f"Test {t}: {NELSON_TEST_DESCRIPTIONS.get(t, '')}"])

        text_lines = [
            f"Xbar-S Chart of {params.measurement_col}",
            "",
            "Control Limits and Parameters:",
            f"  Subgroup Size:          n = {n}",
            f"  Number of Subgroups:    k = {k_subgroups}",
            f"  Estimated Process Sigma: s = {sigma_est:.4f} (Sbar / c4)",
            "",
            "Xbar Chart:",
            f"  UCL = {xbar_ucl:.4f},  CL = {xbar_cl:.4f},  LCL = {xbar_lcl:.4f}",
            "S Chart:",
            f"  UCL = {s_ucl:.4f},  CL = {s_cl:.4f},  LCL = {s_lcl:.4f}",
        ]

        fig = build_dual_spc_plot(
            title=f"Xbar-S Chart of {params.measurement_col}",
            top_label="Sample Mean (Xbar)",
            bot_label="Sample StDev (S)",
            subgroups=list(range(1, k_subgroups + 1)),
            top_values=subgroup_means,
            top_cl=xbar_cl,
            top_ucl=xbar_ucl,
            top_lcl=xbar_lcl,
            top_fails=xbar_fails,
            bot_values=subgroup_stdevs,
            bot_cl=s_cl,
            bot_ucl=s_ucl,
            bot_lcl=s_lcl,
            bot_fails=s_fails,
        )

        return AnalysisResult(
            title="Xbar-S Chart",
            subtitle=f"{params.measurement_col} (n={n})",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title="Control Limits Summary", headers=summary_headers, rows=summary_rows),
                TableResult(title="Test Results / Violations", headers=test_results_headers, rows=test_results_rows, notes=["Nelson / Western Electric Run Rules"])
            ],
            statistics={"sigma_est": sigma_est, "xbar_cl": xbar_cl, "s_cl": s_cl, "failed_count": len(test_results_rows)},
            plotly_figure=fig
        )
