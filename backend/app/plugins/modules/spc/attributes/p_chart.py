import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import evaluate_nelson_rules, NELSON_TEST_DESCRIPTIONS


class PChartParams(BaseModel):
    defectives_col: str = Field(..., description="Defectives Count Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    size_col: Optional[str] = Field(None, description="Subgroup Size Column (if sample sizes vary)", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    constant_size: Optional[int] = Field(None, description="Constant Subgroup Size", json_schema_extra={"ui_type": "number"})
    historical_p: Optional[float] = Field(None, description="Historical Proportion (p)", json_schema_extra={"ui_type": "number"})
    test_1: bool = Field(True, description="Test 1: 1 point > 3s from center line", json_schema_extra={"ui_type": "checkbox"})
    test_2: bool = Field(True, description="Test 2: 9 points in a row on same side of center line", json_schema_extra={"ui_type": "checkbox"})
    test_3: bool = Field(True, description="Test 3: 6 points in a row, all increasing or decreasing", json_schema_extra={"ui_type": "checkbox"})
    test_4: bool = Field(True, description="Test 4: 14 points in a row, alternating up and down", json_schema_extra={"ui_type": "checkbox"})


class PChartPlugin(AnalysisPlugin):
    id = "p_chart"
    name = "P Chart"
    menu_path = ["Stat", "Control Charts", "Attributes Charts", "P Chart"]
    description = "Monitors the proportion of nonconforming/defective units in variable or constant size samples."
    param_schema = PChartParams

    def execute(self, df: pd.DataFrame, params: PChartParams) -> AnalysisResult:
        if params.defectives_col not in df.columns:
            raise ValueError(f"Column '{params.defectives_col}' not found in active worksheet.")

        x_vals = pd.to_numeric(df[params.defectives_col], errors="coerce").dropna().to_numpy(dtype=float)
        k = len(x_vals)
        if k < 2:
            raise ValueError("P Chart requires at least 2 subgroups.")

        # Determine subgroup sizes
        if params.size_col and params.size_col in df.columns:
            n_vals = pd.to_numeric(df[params.size_col], errors="coerce").dropna().to_numpy(dtype=float)[:k]
        elif params.constant_size is not None and params.constant_size > 0:
            n_vals = np.full(k, float(params.constant_size))
        else:
            n_vals = np.full(k, 100.0)

        p_vals = x_vals / n_vals
        p_bar = float(np.sum(x_vals) / np.sum(n_vals)) if params.historical_p is None else float(params.historical_p)

        # Standard error per subgroup
        se_p = np.sqrt((p_bar * (1.0 - p_bar)) / n_vals)
        ucl_vals = np.minimum(1.0, p_bar + 3.0 * se_p)
        lcl_vals = np.maximum(0.0, p_bar - 3.0 * se_p)

        # Standardized z-scores for Nelson rules
        z_scores = np.where(se_p > 0, (p_vals - p_bar) / se_p, 0.0)

        active_tests = []
        for t in range(1, 5):
            if getattr(params, f"test_{t}", False):
                active_tests.append(t)

        fails = evaluate_nelson_rules(z_scores, 0.0, 1.0, active_tests)

        test_rows = []
        for idx, tests in sorted(fails.items()):
            for t in tests:
                test_rows.append([idx + 1, f"{p_vals[idx]:.4f}", f"Test {t}: {NELSON_TEST_DESCRIPTIONS.get(t, '')}"])

        # Plotly stepped limit chart
        x_axis = [str(i + 1) for i in range(k)]
        colors = ["#dc2626" if i in fails else "#1d4ed8" for i in range(k)]
        hover = [
            f"Subgroup: {x_axis[i]}<br>Defectives: {int(x_vals[i])}/{int(n_vals[i])}<br><b>Proportion: {p_vals[i]:.4f}</b>" + (f"<br><b style='color:red;'>FAILED: {', '.join(['Test ' + str(f) for f in fails[i]])}</b>" if i in fails else "")
            for i in range(k)
        ]

        plot_data = [
            # Main points & line
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
            # UCL Step Line
            {
                "type": "scatter",
                "mode": "lines",
                "x": x_axis,
                "y": ucl_vals.tolist(),
                "name": "UCL",
                "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"},
            },
            # Center Line
            {
                "type": "scatter",
                "mode": "lines",
                "x": x_axis,
                "y": [p_bar] * k,
                "name": "Center Line",
                "line": {"color": "#16a34a", "width": 1.75},
            },
            # LCL Step Line
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
            "title": {"text": f"<b>P Chart of {params.defectives_col}</b>", "x": 0.5},
            "showlegend": True,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 420,
            "xaxis": {"title": {"text": "Subgroup / Sample"}},
            "yaxis": {"title": {"text": "Proportion Defective"}, "showgrid": True, "gridcolor": "#ececec"},
        }

        return AnalysisResult(
            title="P Chart",
            subtitle=f"{params.defectives_col} (p_bar={p_bar:.4f})",
            text_output=f"P Chart for {params.defectives_col}\nAverage Proportion p_bar = {p_bar:.4f}\nTotal Defectives = {int(np.sum(x_vals))}, Total Units Inspected = {int(np.sum(n_vals))}",
            tables=[
                TableResult(title="Summary Statistics", headers=["Metric", "Value"], rows=[
                    ["Center Line (p_bar)", f"{p_bar:.4f}"], ["Total Defectives", str(int(np.sum(x_vals)))], ["Total Units Inspected", str(int(np.sum(n_vals)))], ["Subgroups", str(k)]
                ]),
                TableResult(title="Test Results / Violations", headers=["Subgroup", "Proportion", "Failed Test"], rows=test_rows)
            ],
            statistics={"p_bar": p_bar, "failed_count": len(test_rows)},
            plotly_figure={"data": plot_data, "layout": layout}
        )
