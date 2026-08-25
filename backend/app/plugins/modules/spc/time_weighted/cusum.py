import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult
from app.plugins.modules.spc.spc_constants import get_spc_factors


class CUSUMParams(BaseModel):
    measurement_col: str = Field(..., description="Measurement Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    subgroup_size: int = Field(1, description="Subgroup Size (n >= 1)", json_schema_extra={"ui_type": "number"})
    target_mean: Optional[float] = Field(None, description="Target Process Mean (mu0)", json_schema_extra={"ui_type": "number"})
    shift_size: float = Field(1.0, description="Shift size to detect (delta in sigma units, e.g. 1.0)", json_schema_extra={"ui_type": "number"})
    decision_interval: float = Field(4.0, description="Decision interval (h in sigma units, e.g. 4.0 or 5.0)", json_schema_extra={"ui_type": "number"})
    historical_sigma: Optional[float] = Field(None, description="Historical Sigma (sigma)", json_schema_extra={"ui_type": "number"})


class CUSUMPlugin(AnalysisPlugin):
    id = "cusum"
    name = "CUSUM Chart"
    menu_path = ["Stat", "Control Charts", "Time-Weighted Charts", "CUSUM"]
    description = "Tabular Cumulative Sum chart for rapidly detecting small shifts in the process mean."
    param_schema = CUSUMParams

    def execute(self, df: pd.DataFrame, params: CUSUMParams) -> AnalysisResult:
        if params.measurement_col not in df.columns:
            raise ValueError(f"Column '{params.measurement_col}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[params.measurement_col], errors="coerce").dropna().to_numpy(dtype=float)
        n = max(1, int(params.subgroup_size))

        if len(raw_series) < n * 3:
            raise ValueError("CUSUM Chart requires at least 3 subgroups.")

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

        mu0 = float(np.mean(means)) if params.target_mean is None else float(params.target_mean)
        se_mean = sigma_est / np.sqrt(n)

        # Tabular CUSUM: K = delta / 2, H = decision interval
        delta = float(params.shift_size)
        K_val = (delta / 2.0) * se_mean
        H_val = float(params.decision_interval) * se_mean

        c_plus = np.zeros(k)
        c_minus = np.zeros(k)
        fails = []

        prev_cp, prev_cm = 0.0, 0.0
        for i in range(k):
            cp = max(0.0, means[i] - (mu0 + K_val) + prev_cp)
            cm = max(0.0, (mu0 - K_val) - means[i] + prev_cm)
            c_plus[i] = cp
            c_minus[i] = -cm  # plotted negative for lower CUSUM
            prev_cp, prev_cm = cp, cm

            if cp > H_val or cm > H_val:
                fails.append(i)

        x_axis = [str(i + 1) for i in range(k)]
        hover_cp = [f"Subgroup: {x_axis[i]}<br>Mean: {means[i]:.4f}<br><b>C+: {c_plus[i]:.4f}</b>" + ("<br><b style='color:red;'>SIGNAL: C+ > H</b>" if c_plus[i] > H_val else "") for i in range(k)]
        hover_cm = [f"Subgroup: {x_axis[i]}<br>Mean: {means[i]:.4f}<br><b>C-: {-c_minus[i]:.4f}</b>" + ("<br><b style='color:red;'>SIGNAL: C- > H</b>" if -c_minus[i] > H_val else "") for i in range(k)]

        plot_data = [
            # Upper CUSUM C+
            {
                "type": "scatter",
                "mode": "lines+markers",
                "x": x_axis,
                "y": c_plus.tolist(),
                "name": "C+ (Upper CUSUM)",
                "line": {"color": "#2563eb", "width": 1.5},
                "marker": {"color": ["#dc2626" if c_plus[i] > H_val else "#2563eb" for i in range(k)], "size": 6},
                "hovertext": hover_cp,
                "hoverinfo": "text",
            },
            # Lower CUSUM C-
            {
                "type": "scatter",
                "mode": "lines+markers",
                "x": x_axis,
                "y": c_minus.tolist(),
                "name": "C- (Lower CUSUM)",
                "line": {"color": "#0d9488", "width": 1.5},
                "marker": {"color": ["#dc2626" if -c_minus[i] > H_val else "#0d9488" for i in range(k)], "size": 6},
                "hovertext": hover_cm,
                "hoverinfo": "text",
            }
        ]

        layout = {
            "title": {"text": f"<b>Tabular CUSUM Chart of {params.measurement_col} (h={params.decision_interval}σ, k={delta/2:.2f}σ)</b>", "x": 0.5},
            "showlegend": True,
            "margin": {"l": 70, "r": 90, "t": 70, "b": 50},
            "height": 420,
            "xaxis": {"title": {"text": "Subgroup / Sample"}},
            "yaxis": {"title": {"text": "Cumulative Sum (CUSUM)"}, "showgrid": True, "gridcolor": "#ececec"},
            "shapes": [
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": H_val, "y1": H_val, "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"}},
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": 0, "y1": 0, "line": {"color": "#16a34a", "width": 1.5}},
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": -H_val, "y1": -H_val, "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"}},
            ],
            "annotations": [
                {"xref": "paper", "x": 1.01, "y": H_val, "text": f"<b>+H={H_val:.3f}</b>", "showarrow": False, "font": {"color": "#dc2626", "size": 11}, "xanchor": "left"},
                {"xref": "paper", "x": 1.01, "y": 0, "text": "<b>0.000</b>", "showarrow": False, "font": {"color": "#16a34a", "size": 11}, "xanchor": "left"},
                {"xref": "paper", "x": 1.01, "y": -H_val, "text": f"<b>-H={-H_val:.3f}</b>", "showarrow": False, "font": {"color": "#dc2626", "size": 11}, "xanchor": "left"},
            ]
        }

        test_rows = []
        for i in sorted(list(set(fails))):
            sig_type = "Upper Shift (C+ > H)" if c_plus[i] > H_val else "Lower Shift (C- > H)"
            test_rows.append([i + 1, f"{means[i]:.4f}", f"{c_plus[i]:.4f}", f"{-c_minus[i]:.4f}", sig_type])

        return AnalysisResult(
            title="CUSUM Chart",
            subtitle=f"{params.measurement_col} (h={params.decision_interval}s)",
            text_output=f"Tabular CUSUM Chart for {params.measurement_col}\nTarget Mean mu0 = {mu0:.4f}, Sigma = {sigma_est:.4f}\nReference value K = {K_val:.4f}, Decision limit H = {H_val:.4f}",
            tables=[
                TableResult(title="CUSUM Parameters", headers=["Parameter", "Value"], rows=[
                    ["Target Mean (mu0)", f"{mu0:.4f}"], ["Estimated Sigma", f"{sigma_est:.4f}"], ["Reference Value (K)", f"{K_val:.4f}"], ["Decision Limit (H)", f"{H_val:.4f}"]
                ]),
                TableResult(title="CUSUM Out-of-Control Signals", headers=["Subgroup", "Sample Mean", "C+", "C-", "Signal Type"], rows=test_rows)
            ],
            statistics={"mu0": mu0, "sigma_est": sigma_est, "H": H_val, "K": K_val, "signal_count": len(test_rows)},
            plotly_figure={"data": plot_data, "layout": layout}
        )
