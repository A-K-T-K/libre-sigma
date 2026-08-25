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


class XbarRParams(BaseModel):
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
    subgroup_col: Optional[str] = Field(
        None,
        description="Optional Subgroup ID/Label Column",
        json_schema_extra={"ui_type": "column_picker"}
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
    test_1: bool = Field(True, description="Test 1: 1 point > 3 standard deviations from center line", json_schema_extra={"ui_type": "checkbox"})
    test_2: bool = Field(True, description="Test 2: 9 points in a row on same side of center line", json_schema_extra={"ui_type": "checkbox"})
    test_3: bool = Field(True, description="Test 3: 6 points in a row, all increasing or decreasing", json_schema_extra={"ui_type": "checkbox"})
    test_4: bool = Field(True, description="Test 4: 14 points in a row, alternating up and down", json_schema_extra={"ui_type": "checkbox"})
    test_5: bool = Field(False, description="Test 5: 2 out of 3 points > 2 standard deviations (same side)", json_schema_extra={"ui_type": "checkbox"})
    test_6: bool = Field(False, description="Test 6: 4 out of 5 points > 1 standard deviation (same side)", json_schema_extra={"ui_type": "checkbox"})
    test_7: bool = Field(False, description="Test 7: 15 points in a row within 1 standard deviation", json_schema_extra={"ui_type": "checkbox"})
    test_8: bool = Field(False, description="Test 8: 8 points in a row > 1 standard deviation with none within 1s", json_schema_extra={"ui_type": "checkbox"})


class XbarRPlugin(AnalysisPlugin):
    id = "xbar_r"
    name = "Xbar-R Chart"
    menu_path = ["Stat", "Control Charts", "Variables Charts for Subgroups", "Xbar-R"]
    description = "Monitors the process mean and range variation across subgroups using standard unbiasing constants d2, d3, A2, D3, D4."
    param_schema = XbarRParams

    def execute(self, df: pd.DataFrame, params: XbarRParams) -> AnalysisResult:
        if params.measurement_col not in df.columns:
            raise ValueError(f"Column '{params.measurement_col}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[params.measurement_col], errors="coerce").dropna().to_numpy(dtype=float)
        n = max(2, int(params.subgroup_size))

        if len(raw_series) < n * 2:
            raise ValueError(f"Xbar-R Chart requires at least 2 complete subgroups of size {n} (found {len(raw_series)} rows).")

        # Group data into subgroups
        k_subgroups = len(raw_series) // n
        trimmed_data = raw_series[: k_subgroups * n].reshape(k_subgroups, n)

        subgroup_means = np.mean(trimmed_data, axis=1)
        subgroup_ranges = np.ptp(trimmed_data, axis=1)
        subgroup_ids = [f"Subgroup {i+1}" for i in range(k_subgroups)]

        # Unbiasing factors
        factors = get_spc_factors(n)
        d2 = factors["d2"]
        d3 = factors["d3"]

        # Centerlines & Limits
        r_bar = float(np.mean(subgroup_ranges))
        sigma_est = (r_bar / d2) if not params.historical_sigma else float(params.historical_sigma)

        x_dbar = float(np.mean(subgroup_means)) if params.historical_mean is None else float(params.historical_mean)

        # Xbar limits
        se_xbar = sigma_est / np.sqrt(n)
        xbar_ucl = x_dbar + 3.0 * se_xbar
        xbar_lcl = x_dbar - 3.0 * se_xbar
        xbar_cl = x_dbar

        # R limits
        r_cl = (d2 * sigma_est) if params.historical_sigma else r_bar
        r_ucl = factors["D4"] * r_cl if not params.historical_sigma else (d2 + 3.0 * d3) * sigma_est
        r_lcl = factors["D3"] * r_cl if not params.historical_sigma else max(0.0, (d2 - 3.0 * d3) * sigma_est)

        # Active Nelson rules
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
        r_fails = evaluate_nelson_rules(subgroup_ranges, r_cl, d3 * sigma_est, [1])

        # Tables
        summary_headers = ["Chart", "Center Line (CL)", "Upper Control Limit (UCL)", "Lower Control Limit (LCL)", "Subgroup Size (n)", "Estimated Sigma (σ)"]
        summary_rows = [
            ["Xbar Chart (Mean)", f"{xbar_cl:.4f}", f"{xbar_ucl:.4f}", f"{xbar_lcl:.4f}", str(n), f"{sigma_est:.4f}"],
            ["R Chart (Range)", f"{r_cl:.4f}", f"{r_ucl:.4f}", f"{r_lcl:.4f}", str(n), f"{sigma_est:.4f}"]
        ]

        test_results_headers = ["Chart", "Subgroup", "Value", "Failed Test(s)"]
        test_results_rows = []
        for idx, tests in sorted(xbar_fails.items()):
            for t in tests:
                test_results_rows.append(["Xbar", idx + 1, f"{subgroup_means[idx]:.4f}", f"Test {t}: {NELSON_TEST_DESCRIPTIONS.get(t, '')}"])
        for idx, tests in sorted(r_fails.items()):
            for t in tests:
                test_results_rows.append(["R", idx + 1, f"{subgroup_ranges[idx]:.4f}", f"Test {t}: {NELSON_TEST_DESCRIPTIONS.get(t, '')}"])

        text_lines = [
            f"Xbar-R Chart of {params.measurement_col}",
            "",
            "Control Limits and Parameters:",
            f"  Subgroup Size:          n = {n}",
            f"  Number of Subgroups:    k = {k_subgroups}",
            f"  Estimated Process Sigma: s = {sigma_est:.4f} (Rbar / d2)",
            "",
            "Xbar Chart:",
            f"  UCL = {xbar_ucl:.4f},  CL = {xbar_cl:.4f},  LCL = {xbar_lcl:.4f}",
            "R Chart:",
            f"  UCL = {r_ucl:.4f},  CL = {r_cl:.4f},  LCL = {r_lcl:.4f}",
            "",
        ]
        if test_results_rows:
            text_lines.append(f"TEST RESULTS: Found {len(test_results_rows)} test failure(s):")
            for tr in test_results_rows:
                text_lines.append(f"  {tr[0]} Chart: Subgroup {tr[1]} (Val={tr[2]}) -> {tr[3]}")
        else:
            text_lines.append("TEST RESULTS: Process is in statistical control (No test failures).")

        fig = build_dual_spc_plot(
            title=f"Xbar-R Chart of {params.measurement_col}",
            top_label="Sample Mean (Xbar)",
            bot_label="Sample Range (R)",
            subgroups=list(range(1, k_subgroups + 1)),
            top_values=subgroup_means,
            top_cl=xbar_cl,
            top_ucl=xbar_ucl,
            top_lcl=xbar_lcl,
            top_fails=xbar_fails,
            bot_values=subgroup_ranges,
            bot_cl=r_cl,
            bot_ucl=r_ucl,
            bot_lcl=r_lcl,
            bot_fails=r_fails,
        )

        return AnalysisResult(
            title="Xbar-R Chart",
            subtitle=f"{params.measurement_col} (n={n})",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title="Control Limits Summary", headers=summary_headers, rows=summary_rows),
                TableResult(title="Test Results / Violations", headers=test_results_headers, rows=test_results_rows, notes=["Nelson / Western Electric Run Rules"])
            ],
            statistics={"sigma_est": sigma_est, "xbar_cl": xbar_cl, "r_cl": r_cl, "failed_count": len(test_results_rows)},
            plotly_figure=fig
        )
