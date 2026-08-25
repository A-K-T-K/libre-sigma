import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import build_single_spc_plot


class T2MultivariateParams(BaseModel):
    variables: List[str] = Field(..., description="Select 2 or more process variables", json_schema_extra={"ui_type": "column_multi_picker", "data_type": "numeric"})
    alpha: float = Field(0.05, description="False alarm rate alpha (e.g. 0.05 or 0.01)", json_schema_extra={"ui_type": "number"})


class T2MultivariatePlugin(AnalysisPlugin):
    id = "t2_multivariate"
    name = "T2 Multivariate Chart"
    menu_path = ["Stat", "Control Charts", "Multivariate Control Charts", "T2 Multivariate Chart"]
    description = "Hotelling's T-squared chart for simultaneously monitoring multiple correlated process characteristics."
    param_schema = T2MultivariateParams

    def execute(self, df: pd.DataFrame, params: T2MultivariateParams) -> AnalysisResult:
        if len(params.variables) < 2:
            raise ValueError("Hotelling's T2 Chart requires at least 2 numeric variables.")

        valid_vars = [v for v in params.variables if v in df.columns]
        if len(valid_vars) < 2:
            raise ValueError("At least 2 selected variables must exist in the active worksheet.")

        sub_df = df[valid_vars].apply(pd.to_numeric, errors="coerce").dropna()
        m = len(sub_df)
        p = len(valid_vars)

        if m <= p + 1:
            raise ValueError(f"Hotelling's T2 requires at least {p + 2} observations (found {m}).")

        X = sub_df.to_numpy(dtype=float)
        mean_vec = np.mean(X, axis=0)
        cov_mat = np.cov(X, rowvar=False)

        # Invert covariance matrix with pseudoinverse fallback
        try:
            inv_cov = np.linalg.inv(cov_mat)
        except np.linalg.LinAlgError:
            inv_cov = np.linalg.pinv(cov_mat)

        # Compute T2 for each row
        diff = X - mean_vec
        t2_vals = np.sum((diff @ inv_cov) * diff, axis=1)

        # UCL based on F-distribution:
        # UCL = [p * (m + 1) * (m - 1) / (m * (m - p))] * F(alpha, p, m - p)
        alpha = float(params.alpha)
        f_crit = stats.f.ppf(1.0 - alpha, p, m - p)
        ucl = (p * (m + 1) * (m - 1) / (m * (m - p))) * f_crit
        cl = p
        lcl = 0.0

        fails = {i: [1] for i in range(m) if t2_vals[i] > ucl}

        test_rows = [[i + 1, f"{t2_vals[i]:.4f}", f"{ucl:.4f}", f"T² > UCL (α={alpha})"] for i in sorted(fails.keys())]

        fig = build_single_spc_plot(
            title=f"Hotelling's T² Chart ({', '.join(valid_vars)})",
            y_label="Hotelling's T²",
            subgroups=list(range(1, m + 1)),
            values=t2_vals,
            cl=cl,
            ucl=ucl,
            lcl=lcl,
            failed_points=fails
        )

        return AnalysisResult(
            title="T² Multivariate Chart",
            subtitle=f"{p} Variables (m={m}, α={alpha})",
            text_output=f"Hotelling's T² Chart for {', '.join(valid_vars)}\nObservations m = {m}, Variables p = {p}\nUCL = {ucl:.4f}, CL = {cl:.2f}, LCL = 0.00\nFound {len(fails)} out-of-control point(s).",
            tables=[
                TableResult(title="Multivariate Parameters Summary", headers=["Parameter", "Value"], rows=[
                    ["Number of Variables (p)", str(p)], ["Observations (m)", str(m)], ["Significance (alpha)", f"{alpha:.4f}"], ["Upper Control Limit (UCL)", f"{ucl:.4f}"], ["Center Line (p)", f"{cl:.2f}"]
                ]),
                TableResult(title="Test Results / Violations", headers=["Observation", "T² Value", "UCL", "Violation"], rows=test_rows)
            ],
            statistics={"ucl": ucl, "cl": cl, "p": p, "m": m, "failed_count": len(fails)},
            plotly_figure=fig
        )
