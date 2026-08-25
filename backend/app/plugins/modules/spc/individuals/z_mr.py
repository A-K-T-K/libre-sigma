import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import (
    evaluate_nelson_rules,
    build_dual_spc_plot,
    NELSON_TEST_DESCRIPTIONS
)


class ZMRParams(BaseModel):
    measurement_col: str = Field(..., description="Measurement Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    target_col: Optional[str] = Field(None, description="Target/Mean Column (for varying short runs)", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    sigma_col: Optional[str] = Field(None, description="Sigma/StdDev Column (for varying short runs)", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    constant_target: Optional[float] = Field(None, description="Constant Target Mean", json_schema_extra={"ui_type": "number"})
    constant_sigma: Optional[float] = Field(None, description="Constant Standard Deviation", json_schema_extra={"ui_type": "number"})


class ZMRPlugin(AnalysisPlugin):
    id = "z_mr"
    name = "Z-MR Chart"
    menu_path = ["Stat", "Control Charts", "Variables Charts for Individuals", "Z-MR"]
    description = "Standardized I-MR chart for short production runs with varying nominal part targets and standard deviations."
    param_schema = ZMRParams

    def execute(self, df: pd.DataFrame, params: ZMRParams) -> AnalysisResult:
        if params.measurement_col not in df.columns:
            raise ValueError(f"Column '{params.measurement_col}' not found in active worksheet.")

        raw_x = pd.to_numeric(df[params.measurement_col], errors="coerce").dropna().to_numpy(dtype=float)
        n = len(raw_x)
        if n < 3:
            raise ValueError("Z-MR Chart requires at least 3 observations.")

        # Determine target means mu_i
        if params.target_col and params.target_col in df.columns:
            mu_vals = pd.to_numeric(df[params.target_col], errors="coerce").fillna(np.mean(raw_x)).to_numpy(dtype=float)[:n]
        elif params.constant_target is not None:
            mu_vals = np.full(n, float(params.constant_target))
        else:
            mu_vals = np.full(n, float(np.mean(raw_x)))

        # Determine sigmas sigma_i
        if params.sigma_col and params.sigma_col in df.columns:
            sig_vals = pd.to_numeric(df[params.sigma_col], errors="coerce").fillna(np.std(raw_x, ddof=1)).to_numpy(dtype=float)[:n]
        elif params.constant_sigma is not None and params.constant_sigma > 0:
            sig_vals = np.full(n, float(params.constant_sigma))
        else:
            mr_temp = np.abs(np.diff(raw_x))
            sig_temp = float(np.mean(mr_temp) / 1.128) if len(mr_temp) > 0 else float(np.std(raw_x, ddof=1))
            sig_vals = np.full(n, sig_temp)

        # Standardized Z values: Z_i = (X_i - mu_i) / sigma_i
        z_vals = np.where(sig_vals > 0, (raw_x - mu_vals) / sig_vals, 0.0)
        mr_z = np.abs(np.diff(z_vals))
        mr_z_plot = np.insert(mr_z, 0, mr_z[0] if len(mr_z) > 0 else 1.128)

        # Theoretical Standardized Limits:
        # Z Chart: CL = 0, UCL = +3.0, LCL = -3.0
        z_cl, z_ucl, z_lcl = 0.0, 3.0, -3.0
        # MR(Z) Chart: CL = d2(2) = 1.128, UCL = D4 * 1.128 = 3.686, LCL = 0.0
        mrz_cl, mrz_ucl, mrz_lcl = 1.128, 3.686, 0.0

        z_fails = evaluate_nelson_rules(z_vals, z_cl, 1.0, [1, 2, 3, 4])
        mrz_fails = evaluate_nelson_rules(mr_z, mrz_cl, 0.8525, [1])
        mrz_fails_adj = {k + 1: v for k, v in mrz_fails.items()}

        test_rows = []
        for idx, tests in sorted(z_fails.items()):
            for t in tests:
                test_rows.append(["Z Chart", idx + 1, f"{z_vals[idx]:.4f}", f"Test {t}: {NELSON_TEST_DESCRIPTIONS.get(t, '')}"])
        for idx, tests in sorted(mrz_fails_adj.items()):
            for t in tests:
                test_rows.append(["MR(Z) Chart", idx + 1, f"{mr_z_plot[idx]:.4f}", "Test 1: Standardized MR > 3.686"])

        fig = build_dual_spc_plot(
            title=f"Z-MR Chart of {params.measurement_col}",
            top_label="Standardized Value (Z)",
            bot_label="Standardized Moving Range (MR)",
            subgroups=list(range(1, n + 1)),
            top_values=z_vals,
            top_cl=z_cl,
            top_ucl=z_ucl,
            top_lcl=z_lcl,
            top_fails=z_fails,
            bot_values=mr_z_plot,
            bot_cl=mrz_cl,
            bot_ucl=mrz_ucl,
            bot_lcl=mrz_lcl,
            bot_fails=mrz_fails_adj,
        )

        return AnalysisResult(
            title="Z-MR Chart",
            subtitle=f"{params.measurement_col} (Standardized)",
            text_output=f"Z-MR Chart for {params.measurement_col}\nZ Limits: UCL = 3.00, CL = 0.00, LCL = -3.00\nMR(Z) Limits: UCL = 3.686, CL = 1.128, LCL = 0.00",
            tables=[
                TableResult(title="Control Limits Summary", headers=["Chart", "CL", "UCL", "LCL"], rows=[
                    ["Z Chart", "0.000", "3.000", "-3.000"],
                    ["MR(Z) Chart", "1.128", "3.686", "0.000"]
                ]),
                TableResult(title="Test Violations", headers=["Chart", "Observation", "Standardized Value", "Violation"], rows=test_rows)
            ],
            statistics={"n": n, "failed_count": len(test_rows)},
            plotly_figure=fig
        )
