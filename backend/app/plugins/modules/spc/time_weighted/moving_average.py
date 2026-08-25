import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import get_spc_factors


class MovingAverageParams(BaseModel):
    measurement_col: str = Field(..., description="Measurement Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    subgroup_size: int = Field(1, description="Subgroup Size (n >= 1)", json_schema_extra={"ui_type": "number"})
    span: int = Field(3, description="Moving Average Span / Window length (w >= 2)", json_schema_extra={"ui_type": "number"})
    historical_mean: Optional[float] = Field(None, description="Historical Mean (mu)", json_schema_extra={"ui_type": "number"})
    historical_sigma: Optional[float] = Field(None, description="Historical Sigma (sigma)", json_schema_extra={"ui_type": "number"})


class MovingAveragePlugin(AnalysisPlugin):
    id = "moving_average"
    name = "Moving Average Chart"
    menu_path = ["Stat", "Control Charts", "Time-Weighted Charts", "Moving Average"]
    description = "Simple Moving Average chart for smoothing process data over a rolling window span."
    param_schema = MovingAverageParams

    def execute(self, df: pd.DataFrame, params: MovingAverageParams) -> AnalysisResult:
        if params.measurement_col not in df.columns:
            raise ValueError(f"Column '{params.measurement_col}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[params.measurement_col], errors="coerce").dropna().to_numpy(dtype=float)
        n = max(1, int(params.subgroup_size))
        w = max(2, int(params.span))

        if len(raw_series) < n * w:
            raise ValueError(f"Moving Average Chart requires at least {w} subgroups.")

        k = len(raw_series) // n
        trimmed = raw_series[: k * n].reshape(k, n)
        means = np.mean(trimmed, axis=1)

        if params.historical_sigma is not None and params.historical_sigma > 0:
            sigma_est = float(params.historical_sigma)
        elif n > 1:
            ranges = np.ptp(trimmed, axis=1)
            sigma_est = float(np.mean(ranges) / get_spc_factors(n)["d2"])
        else:
            mr = np.abs(np.diff(means))
            sigma_est = float(np.mean(mr) / 1.128) if len(mr) > 0 else float(np.std(means, ddof=1))

        cl = float(np.mean(means)) if params.historical_mean is None else float(params.historical_mean)

        ma_vals = np.zeros(k)
        ucl_vals = np.zeros(k)
        lcl_vals = np.zeros(k)
        fails = []

        for i in range(k):
            window_len = min(i + 1, w)
            ma = np.mean(means[i - window_len + 1 : i + 1])
            ma_vals[i] = ma

            se_ma = (sigma_est / np.sqrt(n)) / np.sqrt(window_len)
            ucl = cl + 3.0 * se_ma
            lcl = cl - 3.0 * se_ma
            ucl_vals[i] = ucl
            lcl_vals[i] = lcl

            if ma > ucl or ma < lcl:
                fails.append(i)

        x_axis = [str(i + 1) for i in range(k)]
        colors = ["#dc2626" if i in fails else "#1d4ed8" for i in range(k)]
        hover = [
            f"Subgroup: {x_axis[i]}<br>Mean: {means[i]:.4f}<br><b>Moving Avg: {ma_vals[i]:.4f}</b>" + ("<br><b style='color:red;'>OUT OF CONTROL</b>" if i in fails else "")
            for i in range(k)
        ]

        plot_data = [
            {
                "type": "scatter",
                "mode": "lines+markers",
                "x": x_axis,
                "y": ma_vals.tolist(),
                "name": f"Moving Average (w={w})",
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
                "y": [cl] * k,
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
            "title": {"text": f"<b>Moving Average Chart of {params.measurement_col} (Span = {w})</b>", "x": 0.5},
            "showlegend": True,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 420,
            "xaxis": {"title": {"text": "Subgroup / Sample"}},
            "yaxis": {"title": {"text": "Moving Average"}, "showgrid": True, "gridcolor": "#ececec"},
        }

        test_rows = [[i + 1, f"{ma_vals[i]:.4f}", f"{ucl_vals[i]:.4f}", f"{lcl_vals[i]:.4f}", "Point beyond control limits"] for i in fails]

        return AnalysisResult(
            title="Moving Average Chart",
            subtitle=f"{params.measurement_col} (w={w})",
            text_output=f"Moving Average Chart for {params.measurement_col}\nSpan w = {w}, Center Line = {cl:.4f}, Sigma = {sigma_est:.4f}",
            tables=[
                TableResult(title="Summary Statistics", headers=["Metric", "Value"], rows=[
                    ["Center Line", f"{cl:.4f}"], ["Estimated Sigma", f"{sigma_est:.4f}"], ["Span (w)", str(w)], ["Subgroup Size (n)", str(n)]
                ]),
                TableResult(title="Test Results / Violations", headers=["Subgroup", "Moving Avg", "UCL", "LCL", "Violation"], rows=test_rows)
            ],
            statistics={"cl": cl, "sigma_est": sigma_est, "span": w, "failed_count": len(fails)},
            plotly_figure={"data": plot_data, "layout": layout}
        )
