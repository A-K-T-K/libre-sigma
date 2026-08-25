import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import get_spc_factors


class EWMAParams(BaseModel):
    measurement_col: str = Field(..., description="Measurement Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    subgroup_size: int = Field(1, description="Subgroup Size (n >= 1)", json_schema_extra={"ui_type": "number"})
    weight: float = Field(0.20, description="Weight parameter lambda (0.05 to 0.50)", json_schema_extra={"ui_type": "number"})
    num_sigmas: float = Field(3.0, description="Number of standard deviations (L, typically 3.0)", json_schema_extra={"ui_type": "number"})
    historical_mean: Optional[float] = Field(None, description="Historical Mean (mu)", json_schema_extra={"ui_type": "number"})
    historical_sigma: Optional[float] = Field(None, description="Historical Sigma (sigma)", json_schema_extra={"ui_type": "number"})


class EWMAPlugin(AnalysisPlugin):
    id = "ewma"
    name = "EWMA Chart"
    menu_path = ["Stat", "Control Charts", "Time-Weighted Charts", "EWMA"]
    description = "Exponentially Weighted Moving Average chart for detecting small process shifts (0.5 to 2.0 sigma)."
    param_schema = EWMAParams

    def execute(self, df: pd.DataFrame, params: EWMAParams) -> AnalysisResult:
        if params.measurement_col not in df.columns:
            raise ValueError(f"Column '{params.measurement_col}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[params.measurement_col], errors="coerce").dropna().to_numpy(dtype=float)
        n = max(1, int(params.subgroup_size))

        if len(raw_series) < n * 3:
            raise ValueError("EWMA Chart requires at least 3 subgroups of data.")

        k = len(raw_series) // n
        trimmed = raw_series[: k * n].reshape(k, n)
        means = np.mean(trimmed, axis=1)

        # Estimate process sigma
        if params.historical_sigma is not None and params.historical_sigma > 0:
            sigma_est = float(params.historical_sigma)
        elif n > 1:
            ranges = np.ptp(trimmed, axis=1)
            sigma_est = float(np.mean(ranges) / get_spc_factors(n)["d2"])
        else:
            mr = np.abs(np.diff(means))
            sigma_est = float(np.mean(mr) / 1.128) if len(mr) > 0 else float(np.std(means, ddof=1))

        mu0 = float(np.mean(means)) if params.historical_mean is None else float(params.historical_mean)
        lam = float(params.weight)
        if not (0 < lam <= 1.0):
            raise ValueError("Weight parameter lambda must be in the range (0, 1].")
        l_mult = float(params.num_sigmas)

        # Compute EWMA series
        ewma_vals = np.zeros(k)
        ucl_vals = np.zeros(k)
        lcl_vals = np.zeros(k)
        fails = []

        prev_z = mu0
        for i in range(k):
            z_i = lam * means[i] + (1.0 - lam) * prev_z
            ewma_vals[i] = z_i
            prev_z = z_i

            # Exact dynamic standard error
            i_step = i + 1
            se_i = (sigma_est / np.sqrt(n)) * np.sqrt((lam / (2.0 - lam)) * (1.0 - (1.0 - lam) ** (2 * i_step)))
            ucl_vals[i] = mu0 + l_mult * se_i
            lcl_vals[i] = mu0 - l_mult * se_i

            if z_i > ucl_vals[i] or z_i < lcl_vals[i]:
                fails.append(i)

        x_axis = [str(i + 1) for i in range(k)]
        colors = ["#dc2626" if i in fails else "#1d4ed8" for i in range(k)]
        hover = [
            f"Subgroup: {x_axis[i]}<br>Sample Mean: {means[i]:.4f}<br><b>EWMA (Z): {ewma_vals[i]:.4f}</b>" + ("<br><b style='color:red;'>OUT OF CONTROL</b>" if i in fails else "")
            for i in range(k)
        ]

        plot_data = [
            {
                "type": "scatter",
                "mode": "lines+markers",
                "x": x_axis,
                "y": ewma_vals.tolist(),
                "name": "EWMA",
                "line": {"color": "#64748b", "width": 1.5},
                "marker": {"color": colors, "size": 7},
                "hovertext": hover,
                "hoverinfo": "text",
            },
            {
                "type": "scatter",
                "mode": "lines",
                "x": x_axis,
                "y": ucl_vals.tolist(),
                "name": "UCL",
                "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"},
            },
            {
                "type": "scatter",
                "mode": "lines",
                "x": x_axis,
                "y": [mu0] * k,
                "name": "Center Line",
                "line": {"color": "#16a34a", "width": 1.75},
            },
            {
                "type": "scatter",
                "mode": "lines",
                "x": x_axis,
                "y": lcl_vals.tolist(),
                "name": "LCL",
                "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"},
            }
        ]

        layout = {
            "title": {"text": f"<b>EWMA Chart of {params.measurement_col} (λ = {lam:.2f}, L = {l_mult:.1f})</b>", "x": 0.5},
            "showlegend": True,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 420,
            "xaxis": {"title": {"text": "Subgroup / Sample"}},
            "yaxis": {"title": {"text": "EWMA"}, "showgrid": True, "gridcolor": "#ececec"},
        }

        test_rows = [[i + 1, f"{ewma_vals[i]:.4f}", f"{ucl_vals[i]:.4f}", f"{lcl_vals[i]:.4f}", "Point beyond control limits"] for i in fails]

        return AnalysisResult(
            title="EWMA Chart",
            subtitle=f"{params.measurement_col} (λ={lam})",
            text_output=f"EWMA Chart for {params.measurement_col}\nCenter Line = {mu0:.4f}, Estimated Sigma = {sigma_est:.4f}\nWeight (Lambda) = {lam:.2f}, Control Limit Multiplier (L) = {l_mult:.1f}",
            tables=[
                TableResult(title="EWMA Parameters Summary", headers=["Parameter", "Value"], rows=[
                    ["Center Line (mu0)", f"{mu0:.4f}"], ["Estimated Sigma", f"{sigma_est:.4f}"], ["Weight (Lambda)", f"{lam:.2f}"], ["Multiplier (L)", f"{l_mult:.1f}"], ["Subgroup Size (n)", str(n)]
                ]),
                TableResult(title="Test Results / Violations", headers=["Subgroup", "EWMA Value", "UCL", "LCL", "Violation"], rows=test_rows)
            ],
            statistics={"cl": mu0, "sigma_est": sigma_est, "lambda": lam, "failed_count": len(fails)},
            plotly_figure={"data": plot_data, "layout": layout}
        )
