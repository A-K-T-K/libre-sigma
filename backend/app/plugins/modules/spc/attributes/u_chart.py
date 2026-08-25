import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import evaluate_nelson_rules, NELSON_TEST_DESCRIPTIONS


class UChartParams(BaseModel):
    defects_col: str = Field(..., description="Defects Count Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    size_col: Optional[str] = Field(None, description="Sample Size / Inspection Units Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    constant_size: Optional[float] = Field(None, description="Constant Inspection Units Size", json_schema_extra={"ui_type": "number"})
    historical_u: Optional[float] = Field(None, description="Historical Mean Defects per Unit (u)", json_schema_extra={"ui_type": "number"})
    test_1: bool = Field(True, description="Test 1: 1 point > 3s from center line", json_schema_extra={"ui_type": "checkbox"})
    test_2: bool = Field(True, description="Test 2: 9 points in a row on same side of center line", json_schema_extra={"ui_type": "checkbox"})
    test_3: bool = Field(True, description="Test 3: 6 points in a row, all increasing or decreasing", json_schema_extra={"ui_type": "checkbox"})
    test_4: bool = Field(True, description="Test 4: 14 points in a row, alternating up and down", json_schema_extra={"ui_type": "checkbox"})


class UChartPlugin(AnalysisPlugin):
    id = "u_chart"
    name = "U Chart"
    menu_path = ["Stat", "Control Charts", "Attributes Charts", "U Chart"]
    description = "Monitors number of defects per unit for variable or constant sample sizes."
    param_schema = UChartParams

    def execute(self, df: pd.DataFrame, params: UChartParams) -> AnalysisResult:
        if params.defects_col not in df.columns:
            raise ValueError(f"Column '{params.defects_col}' not found in active worksheet.")

        c_vals = pd.to_numeric(df[params.defects_col], errors="coerce").dropna().to_numpy(dtype=float)
        k = len(c_vals)
        if k < 2:
            raise ValueError("U Chart requires at least 2 sample units.")

        if params.size_col and params.size_col in df.columns:
            n_vals = pd.to_numeric(df[params.size_col], errors="coerce").dropna().to_numpy(dtype=float)[:k]
        elif params.constant_size is not None and params.constant_size > 0:
            n_vals = np.full(k, float(params.constant_size))
        else:
            n_vals = np.full(k, 1.0)

        u_vals = c_vals / n_vals
        u_bar = float(np.sum(c_vals) / np.sum(n_vals)) if params.historical_u is None else float(params.historical_u)

        se_u = np.sqrt(u_bar / n_vals)
        ucl_vals = u_bar + 3.0 * se_u
        lcl_vals = np.maximum(0.0, u_bar - 3.0 * se_u)

        z_scores = np.where(se_u > 0, (u_vals - u_bar) / se_u, 0.0)

        active_tests = []
        for t in range(1, 5):
            if getattr(params, f"test_{t}", False):
                active_tests.append(t)

        fails = evaluate_nelson_rules(z_scores, 0.0, 1.0, active_tests)

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
                "name": "UCL",
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

        layout = {
            "title": {"text": f"<b>U Chart of {params.defects_col}</b>", "x": 0.5},
            "showlegend": True,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 420,
            "xaxis": {"title": {"text": "Subgroup / Sample"}},
            "yaxis": {"title": {"text": "Defects per Unit (U)"}, "showgrid": True, "gridcolor": "#ececec"},
        }

        return AnalysisResult(
            title="U Chart",
            subtitle=f"{params.defects_col} (u_bar={u_bar:.4f})",
            text_output=f"U Chart for {params.defects_col}\nAverage Rate u_bar = {u_bar:.4f}\nTotal Defects = {int(np.sum(c_vals))}, Total Units = {np.sum(n_vals):.2f}",
            tables=[
                TableResult(title="Summary Statistics", headers=["Metric", "Value"], rows=[
                    ["Center Line (u_bar)", f"{u_bar:.4f}"], ["Total Defects", str(int(np.sum(c_vals)))], ["Total Inspection Units", f"{np.sum(n_vals):.2f}"], ["Samples", str(k)]
                ]),
                TableResult(title="Test Results / Violations", headers=["Sample", "Rate (U)", "Failed Test"], rows=test_rows)
            ],
            statistics={"u_bar": u_bar, "failed_count": len(test_rows)},
            plotly_figure={"data": plot_data, "layout": layout}
        )
