import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import build_single_spc_plot


class GeneralizedVarianceParams(BaseModel):
    variables: List[str] = Field(..., description="Select 2 or more process variables", json_schema_extra={"ui_type": "column_multi_picker", "data_type": "numeric"})
    subgroup_size: int = Field(5, description="Subgroup Size (n >= p + 1)", json_schema_extra={"ui_type": "number"})


class GeneralizedVariancePlugin(AnalysisPlugin):
    id = "generalized_variance"
    name = "Generalized Variance Chart"
    menu_path = ["Stat", "Control Charts", "Multivariate Control Charts", "Generalized Variance Chart"]
    description = "Monitors multivariate process variability using the determinant of the sample covariance matrix |S|."
    param_schema = GeneralizedVarianceParams

    def execute(self, df: pd.DataFrame, params: GeneralizedVarianceParams) -> AnalysisResult:
        if len(params.variables) < 2:
            raise ValueError("Generalized Variance Chart requires at least 2 numeric variables.")

        valid_vars = [v for v in params.variables if v in df.columns]
        if len(valid_vars) < 2:
            raise ValueError("At least 2 selected variables must exist in the active worksheet.")

        sub_df = df[valid_vars].apply(pd.to_numeric, errors="coerce").dropna()
        n = max(3, int(params.subgroup_size))
        p = len(valid_vars)

        if n <= p:
            raise ValueError(f"Subgroup size n={n} must be strictly greater than number of variables p={p}.")

        total_rows = len(sub_df)
        k_subgroups = total_rows // n
        if k_subgroups < 2:
            raise ValueError(f"Generalized Variance requires at least 2 complete subgroups of size {n}.")

        X = sub_df.to_numpy(dtype=float)[: k_subgroups * n]
        subgroups = X.reshape(k_subgroups, n, p)

        # Compute |S_i| for each subgroup
        det_s = np.zeros(k_subgroups)
        cov_sum = np.zeros((p, p))

        for i in range(k_subgroups):
            s_i = np.cov(subgroups[i], rowvar=False)
            cov_sum += s_i
            det_val = np.linalg.det(s_i)
            det_s[i] = max(0.0, det_val)

        s_bar = cov_sum / k_subgroups
        det_s_bar = float(np.linalg.det(s_bar))

        # Unbiasing factors b1, b2 for Generalized Variance (Montgomery 2009)
        # b1 = prod_{i=1}^p (1 - (i-1)/(n-1))
        b1 = 1.0
        for j in range(1, p + 1):
            b1 *= (1.0 - (j - 1.0) / (n - 1.0))

        # b2 calculation
        prod2 = 1.0
        for j in range(1, p + 1):
            prod2 *= (1.0 - (j - 1.0) / (n - 1.0)) * (1.0 + 2.0 / (n - 1.0 - j + 1.0))
        b2 = max(0.0, prod2 - b1 ** 2)

        cl = b1 * det_s_bar
        se_det = np.sqrt(b2) * det_s_bar
        ucl = cl + 3.0 * se_det
        lcl = max(0.0, cl - 3.0 * se_det)

        fails = {i: [1] for i in range(k_subgroups) if det_s[i] > ucl or det_s[i] < lcl}
        test_rows = [[i + 1, f"{det_s[i]:.6e}", f"{ucl:.6e}", f"{lcl:.6e}", "Point beyond control limits"] for i in sorted(fails.keys())]

        fig = build_single_spc_plot(
            title=f"Generalized Variance |S| Chart ({', '.join(valid_vars)})",
            y_label="|S| Determinant",
            subgroups=list(range(1, k_subgroups + 1)),
            values=det_s,
            cl=cl,
            ucl=ucl,
            lcl=lcl,
            failed_points=fails
        )

        return AnalysisResult(
            title="Generalized Variance Chart",
            subtitle=f"{p} Variables (n={n}, k={k_subgroups})",
            text_output=f"Generalized Variance Chart for {', '.join(valid_vars)}\nCL = {cl:.6e}, UCL = {ucl:.6e}, LCL = {lcl:.6e}\nDeterminant of S_bar = {det_s_bar:.6e}",
            tables=[
                TableResult(title="Generalized Variance Summary", headers=["Metric", "Value"], rows=[
                    ["Center Line (b1 * |S_bar|)", f"{cl:.6e}"], ["Upper Control Limit (UCL)", f"{ucl:.6e}"], ["Lower Control Limit (LCL)", f"{lcl:.6e}"], ["Subgroup Size (n)", str(n)], ["Number of Subgroups (k)", str(k_subgroups)]
                ]),
                TableResult(title="Test Results / Violations", headers=["Subgroup", "|S| Value", "UCL", "LCL", "Violation"], rows=test_rows)
            ],
            statistics={"cl": cl, "ucl": ucl, "lcl": lcl, "failed_count": len(fails)},
            plotly_figure=fig
        )
