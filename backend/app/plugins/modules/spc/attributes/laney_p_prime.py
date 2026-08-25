import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import evaluate_nelson_rules, NELSON_TEST_DESCRIPTIONS


class LaneyPPrimeParams(BaseModel):
    defectives_col: str = Field(..., description="Defectives Count Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    size_col: Optional[str] = Field(None, description="Subgroup Size Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    constant_size: Optional[int] = Field(None, description="Constant Subgroup Size (n)", json_schema_extra={"ui_type": "number"})


class LaneyPPrimePlugin(AnalysisPlugin):
    id = "laney_p_prime"
    name = "Laney P' Chart"
    menu_path = ["Stat", "Control Charts", "Attributes Charts", "Laney P' Chart"]
    description = "Adjusts P chart control limits for overdispersion or underdispersion using Laney sigma_z correction factor."
    param_schema = LaneyPPrimeParams

    def execute(self, df: pd.DataFrame, params: LaneyPPrimeParams) -> AnalysisResult:
        if params.defectives_col not in df.columns:
            raise ValueError(f"Column '{params.defectives_col}' not found in active worksheet.")

        x_vals = pd.to_numeric(df[params.defectives_col], errors="coerce").dropna().to_numpy(dtype=float)
        k = len(x_vals)
        if k < 3:
            raise ValueError("Laney P' Chart requires at least 3 subgroups.")

        if params.size_col and params.size_col in df.columns:
            n_vals = pd.to_numeric(df[params.size_col], errors="coerce").dropna().to_numpy(dtype=float)[:k]
        elif params.constant_size is not None and params.constant_size > 0:
            n_vals = np.full(k, float(params.constant_size))
        else:
            n_vals = np.full(k, 100.0)

        p_vals = x_vals / n_vals
        p_bar = float(np.sum(x_vals) / np.sum(n_vals))

        # Standard Binomial SE
        se_binom = np.sqrt((p_bar * (1.0 - p_bar)) / n_vals)
        # Standardized Z-values
        z_vals = np.where(se_binom > 0, (p_vals - p_bar) / se_binom, 0.0)

        # Moving Range of Z values and Sigma_z
        mr_z = np.abs(np.diff(z_vals))
        sigma_z = float(np.mean(mr_z) / 1.128) if len(mr_z) > 0 else 1.0

        # Corrected Limits
        se_laney = sigma_z * se_binom
        ucl_vals = np.minimum(1.0, p_bar + 3.0 * se_laney)
        lcl_vals = np.maximum(0.0, p_bar - 3.0 * se_laney)

        # Evaluate rules on adjusted Z
        z_laney = np.where(se_laney > 0, (p_vals - p_bar) / se_laney, 0.0)
        fails = evaluate_nelson_rules(z_laney, 0.0, 1.0, [1, 2, 3, 4])

        test_rows = []
        for idx, tests in sorted(fails.items()):
            for t in tests:
                test_rows.append([idx + 1, f"{p_vals[idx]:.4f}", f"Test {t}: {NELSON_TEST_DESCRIPTIONS.get(t, '')}"])

        x_axis = [str(i + 1) for i in range(k)]
        colors = ["#dc2626" if i in fails else "#1d4ed8" for i in range(k)]
        hover = [
            f"Subgroup: {x_axis[i]}<br>Defectives: {int(x_vals[i])}/{int(n_vals[i])}<br><b>Proportion: {p_vals[i]:.4f}</b>" + (f"<br><b style='color:red;'>FAILED: {', '.join(['Test ' + str(f) for f in fails[i]])}</b>" if i in fails else "")
            for i in range(k)
        ]

        plot_data = [
            {
                "type": "scatter",
                "mode": "lines+markers",
                "x": x_axis,
                "y": p_vals.tolist(),
                "name": "Sample Proportion",
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
                "y": [p_bar] * k,
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
            "title": {"text": f"<b>Laney P' Chart of {params.defectives_col} (σ_z = {sigma_z:.3f})</b>", "x": 0.5},
            "showlegend": True,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 420,
            "xaxis": {"title": {"text": "Subgroup / Sample"}},
            "yaxis": {"title": {"text": "Proportion Defective"}, "showgrid": True, "gridcolor": "#ececec"},
        }

        return AnalysisResult(
            title="Laney P' Chart",
            subtitle=f"{params.defectives_col} (Sigma_Z = {sigma_z:.3f})",
            text_output=f"Laney P' Chart for {params.defectives_col}\nCenter Line p_bar = {p_bar:.4f}\nLaney Sigma_Z Correction Factor = {sigma_z:.4f} ({disp_status})",
            tables=[
                TableResult(title="Dispersion & Summary Statistics", headers=["Metric", "Value"], rows=[
                    ["Center Line (p_bar)", f"{p_bar:.4f}"], ["Sigma_Z Correction Factor", f"{sigma_z:.4f}"], ["Dispersion Status", disp_status], ["Total Inspected", str(int(np.sum(n_vals)))]
                ]),
                TableResult(title="Test Violations", headers=["Subgroup", "Proportion", "Failed Test"], rows=test_rows)
            ],
            statistics={"p_bar": p_bar, "sigma_z": sigma_z, "failed_count": len(test_rows)},
            plotly_figure={"data": plot_data, "layout": layout}
        )
