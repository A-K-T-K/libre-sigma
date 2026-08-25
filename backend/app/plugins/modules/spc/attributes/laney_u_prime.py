import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import evaluate_nelson_rules, NELSON_TEST_DESCRIPTIONS


class LaneyUPrimeParams(BaseModel):
    defects_col: str = Field(..., description="Defects Count Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    size_col: Optional[str] = Field(None, description="Sample Size Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    constant_size: Optional[float] = Field(None, description="Constant Inspection Size", json_schema_extra={"ui_type": "number"})


class LaneyUPrimePlugin(AnalysisPlugin):
    id = "laney_u_prime"
    name = "Laney U' Chart"
    menu_path = ["Stat", "Control Charts", "Attributes Charts", "Laney U' Chart"]
    description = "Adjusts U chart control limits for overdispersion or underdispersion in defect rates using Laney sigma_z correction."
    param_schema = LaneyUPrimeParams

    def execute(self, df: pd.DataFrame, params: LaneyUPrimeParams) -> AnalysisResult:
        if params.defects_col not in df.columns:
            raise ValueError(f"Column '{params.defects_col}' not found in active worksheet.")

        c_vals = pd.to_numeric(df[params.defects_col], errors="coerce").dropna().to_numpy(dtype=float)
        k = len(c_vals)
        if k < 3:
            raise ValueError("Laney U' Chart requires at least 3 samples.")

        if params.size_col and params.size_col in df.columns:
            n_vals = pd.to_numeric(df[params.size_col], errors="coerce").dropna().to_numpy(dtype=float)[:k]
        elif params.constant_size is not None and params.constant_size > 0:
            n_vals = np.full(k, float(params.constant_size))
        else:
            n_vals = np.full(k, 1.0)

        u_vals = c_vals / n_vals
        u_bar = float(np.sum(c_vals) / np.sum(n_vals))

        se_poisson = np.sqrt(u_bar / n_vals)
        z_vals = np.where(se_poisson > 0, (u_vals - u_bar) / se_poisson, 0.0)

        mr_z = np.abs(np.diff(z_vals))
        sigma_z = float(np.mean(mr_z) / 1.128) if len(mr_z) > 0 else 1.0

        se_laney = sigma_z * se_poisson
        ucl_vals = u_bar + 3.0 * se_laney
        lcl_vals = np.maximum(0.0, u_bar - 3.0 * se_laney)

        z_laney = np.where(se_laney > 0, (u_vals - u_bar) / se_laney, 0.0)
        fails = evaluate_nelson_rules(z_laney, 0.0, 1.0, [1, 2, 3, 4])

        test_rows = []
        for idx, tests in sorted(fails.items()):
            for t in tests:
                test_rows.append([idx + 1, f"{u_vals[idx]:.4f}", f"Test {t}: {NELSON_TEST_DESCRIPTIONS.get(t, '')}"])

        x_axis = [str(i + 1) for i in range(k)]
        colors = ["#dc2626" if i in fails else "#1d4ed8" for i in range(k)]
        hover = [
            f"Sample: {x_axis[i]}<br>Defects: {int(c_vals[i])}<br>Units: {n_vals[i]:.2f}<br><b>Rate (U): {u_vals[i]:.4f}</b>" + (f"<br><b style='color:red;'>FAILED: {', '.join(['Test ' + str(f) for f in fails[i]])}</b>" if i in fails else "")
            for i in range(k)
        ]

        plot_data = [
            {
                "type": "scatter",
                "mode": "lines+markers",
                "x": x_axis,
                "y": u_vals.tolist(),
                "name": "Sample Rate (U)",
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
                "name": f"UCL (σ_z={sigma_z:.2f})",
                "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"},
            },
            {
                "type": "scatter",
                "mode": "lines",
                "x": x_axis,
                "y": [u_bar] * k,
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

        disp_status = "Overdispersion detected (Limits widened)" if sigma_z > 1.1 else "Underdispersion detected (Limits narrowed)" if sigma_z < 0.9 else "Standard dispersion"

        layout = {
            "title": {"text": f"<b>Laney U' Chart of {params.defects_col} (σ_z = {sigma_z:.3f})</b>", "x": 0.5},
            "showlegend": True,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 420,
            "xaxis": {"title": {"text": "Subgroup / Sample"}},
            "yaxis": {"title": {"text": "Defects per Unit"}, "showgrid": True, "gridcolor": "#ececec"},
        }

        return AnalysisResult(
            title="Laney U' Chart",
            subtitle=f"{params.defects_col} (Sigma_Z = {sigma_z:.3f})",
            text_output=f"Laney U' Chart for {params.defects_col}\nCenter Line u_bar = {u_bar:.4f}\nLaney Sigma_Z Correction Factor = {sigma_z:.4f} ({disp_status})",
            tables=[
                TableResult(title="Dispersion & Summary Statistics", headers=["Metric", "Value"], rows=[
                    ["Center Line (u_bar)", f"{u_bar:.4f}"], ["Sigma_Z Correction Factor", f"{sigma_z:.4f}"], ["Dispersion Status", disp_status], ["Total Defects", str(int(np.sum(c_vals)))]
                ]),
                TableResult(title="Test Violations", headers=["Sample", "Rate (U)", "Failed Test"], rows=test_rows)
            ],
            statistics={"u_bar": u_bar, "sigma_z": sigma_z, "failed_count": len(test_rows)},
            plotly_figure={"data": plot_data, "layout": layout}
        )
