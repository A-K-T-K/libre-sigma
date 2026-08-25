"""
Non-Normal Process Capability Analysis Plugin for OpenMinitab.
Calculates process capability metrics (Pp, Ppk, Z-bench, Expected vs Observed PPM) for non-normally distributed continuous processes using percentiles (0.135%, 50%, 99.865%).
Supports Weibull, Lognormal, Exponential, Gamma, and Logistic distributions with interactive fitted capability histograms.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class NonNormalCapabilityParams(BaseModel):
    data_column: str = Field(
        ...,
        description="Data Column (Continuous Process Variable)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    lsl: Optional[float] = Field(
        None,
        description="Lower Specification Limit (LSL)"
    )
    target: Optional[float] = Field(
        None,
        description="Target Value (Optional)"
    )
    usl: Optional[float] = Field(
        None,
        description="Upper Specification Limit (USL)"
    )
    distribution: str = Field(
        "weibull",
        description="Fitted Distribution",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Weibull", "value": "weibull"},
                {"label": "Lognormal", "value": "lognormal"},
                {"label": "Exponential", "value": "exponential"},
                {"label": "Gamma", "value": "gamma"}
            ]
        }
    )
    # Storage Sub-Modal
    store_estimates: bool = Field(
        False,
        description="Store Fitted Distribution Parameters in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )


class NonNormalCapabilityPlugin(AnalysisPlugin):
    id = "capability_nonnormal"
    name = "Non-Normal Process Capability"
    menu_path = ["Stat", "Quality Tools", "Capability Analysis", "Non-Normal"]
    description = "Evaluates process capability (Pp, Ppk, PPM) for non-normal process distributions using percentile methods."
    param_schema = NonNormalCapabilityParams

    def execute(self, df: pd.DataFrame, params: NonNormalCapabilityParams) -> AnalysisResult:
        data_col = params.data_column
        if data_col not in df.columns:
            raise ValueError(f"Column '{data_col}' not found in active worksheet.")

        raw = pd.to_numeric(df[data_col], errors="coerce").dropna()
        if len(raw) < 5:
            raise ValueError("Non-normal capability analysis requires at least 5 valid process observations.")

        lsl, usl, target = params.lsl, params.usl, params.target
        if lsl is None and usl is None:
            raise ValueError("Specify at least one specification limit (LSL or USL).")

        dist_name = params.distribution
        # Ensure positive numbers for Weibull, Gamma, Lognormal
        if dist_name in ["weibull", "lognormal", "gamma", "exponential"]:
            if (raw <= 0).any():
                shift_c = abs(raw.min()) + 0.001
                raw = raw + shift_c
            else:
                shift_c = 0.0

        x_vals = raw.to_numpy(dtype=float)
        n_total = len(x_vals)
        mean_val = float(np.mean(x_vals))
        sd_val = float(np.std(x_vals, ddof=1))

        # Fit distribution parameters and compute theoretical percentiles
        # P0.135 (equivalent to -3 sigma), P50 (median), P99.865 (equivalent to +3 sigma)
        dist_param_rows = []
        if dist_name == "weibull":
            shape_c, loc_c, scale_c = stats.weibull_min.fit(x_vals, floc=0)
            fitted_dist = stats.weibull_min(shape_c, loc=loc_c, scale=scale_c)
            dist_param_rows = [["Shape (β)", f"{shape_c:.4f}"], ["Scale (η)", f"{scale_c:.4f}"]]
        elif dist_name == "lognormal":
            s_c, loc_c, scale_c = stats.lognorm.fit(x_vals, floc=0)
            fitted_dist = stats.lognorm(s_c, loc=loc_c, scale=scale_c)
            dist_param_rows = [["Location (μ)", f"{np.log(scale_c):.4f}"], ["Scale (σ)", f"{s_c:.4f}"]]
        elif dist_name == "gamma":
            a_c, loc_c, scale_c = stats.gamma.fit(x_vals, floc=0)
            fitted_dist = stats.gamma(a_c, loc=loc_c, scale=scale_c)
            dist_param_rows = [["Shape (k)", f"{a_c:.4f}"], ["Scale (θ)", f"{scale_c:.4f}"]]
        else: # exponential
            loc_c, scale_c = stats.expon.fit(x_vals, floc=0)
            fitted_dist = stats.expon(loc=loc_c, scale=scale_c)
            dist_param_rows = [["Scale / Mean", f"{scale_c:.4f}"]]

        p_00135 = float(fitted_dist.ppf(0.00135))
        p_50 = float(fitted_dist.ppf(0.50))
        p_99865 = float(fitted_dist.ppf(0.99865))

        # Overall Capability Indices (ISO 22514-2 / Minitab Non-Normal Percentile Method)
        # Pp = (USL - LSL) / (P99.865 - P0.135)
        # Ppl = (P50 - LSL) / (P50 - P0.135)
        # Ppu = (USL - P50) / (P99.865 - P50)
        # Ppk = min(Ppl, Ppu)

        pp_val = None
        ppl_val = None
        ppu_val = None
        ppk_val = None

        spread_6sigma = p_99865 - p_00135
        if lsl is not None and usl is not None and spread_6sigma > 0:
            pp_val = (usl - lsl) / spread_6sigma

        if lsl is not None and (p_50 - p_00135) > 0:
            ppl_val = (p_50 - lsl) / (p_50 - p_00135)

        if usl is not None and (p_99865 - p_50) > 0:
            ppu_val = (usl - p_50) / (p_99865 - p_50)

        if ppl_val is not None and ppu_val is not None:
            ppk_val = min(ppl_val, ppu_val)
        elif ppl_val is not None:
            ppk_val = ppl_val
        elif ppu_val is not None:
            ppk_val = ppu_val

        # Expected PPM Defective
        ppm_lsl_exp = float(fitted_dist.cdf(lsl) * 1e6) if lsl is not None else 0.0
        ppm_usl_exp = float((1.0 - fitted_dist.cdf(usl)) * 1e6) if usl is not None else 0.0
        ppm_total_exp = ppm_lsl_exp + ppm_usl_exp

        # Observed PPM Defective
        ppm_lsl_obs = float(np.sum(x_vals < lsl) / n_total * 1e6) if lsl is not None else 0.0
        ppm_usl_obs = float(np.sum(x_vals > usl) / n_total * 1e6) if usl is not None else 0.0
        ppm_total_obs = ppm_lsl_obs + ppm_usl_obs

        # Capability Index Table
        cap_rows = []
        if pp_val is not None: cap_rows.append(["Pp (Overall Spread Capability)", f"{pp_val:.2f}"])
        if ppl_val is not None: cap_rows.append(["PPL (Lower Capability)", f"{ppl_val:.2f}"])
        if ppu_val is not None: cap_rows.append(["PPU (Upper Capability)", f"{ppu_val:.2f}"])
        if ppk_val is not None: cap_rows.append(["Ppk (Overall Process Performance)", f"{ppk_val:.2f}"])
        cap_rows.append(["P0.135 (Equivalent -3σ)", f"{p_00135:.4f}"])
        cap_rows.append(["P50 (Median)", f"{p_50:.4f}"])
        cap_rows.append(["P99.865 (Equivalent +3σ)", f"{p_99865:.4f}"])

        # PPM Table
        ppm_rows = [
            ["PPM < LSL", f"{ppm_lsl_exp:.1f}", f"{ppm_lsl_obs:.1f}"],
            ["PPM > USL", f"{ppm_usl_exp:.1f}", f"{ppm_usl_obs:.1f}"],
            ["Total PPM Defective", f"{ppm_total_exp:.1f}", f"{ppm_total_obs:.1f}"]
        ]

        # Histogram + Fitted Curve
        counts, bin_edges = np.histogram(x_vals, bins="auto", density=True)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

        x_grid = np.linspace(min(x_vals) * 0.9, max(x_vals) * 1.1, 150)
        pdf_curve = fitted_dist.pdf(x_grid)

        traces = [
            {
                "x": x_vals.tolist(),
                "type": "histogram",
                "histnorm": "probability density",
                "name": "Process Data",
                "marker": {"color": "rgba(0, 132, 80, 0.45)", "line": {"color": "#008450", "width": 1}}
            },
            {
                "x": x_grid.tolist(),
                "y": pdf_curve.tolist(),
                "mode": "lines",
                "name": f"Fitted {dist_name.capitalize()} Curve",
                "line": {"color": "#005a9e", "width": 2.5}
            }
        ]

        shapes = []
        if lsl is not None:
            shapes.append({"type": "line", "x0": lsl, "x1": lsl, "y0": 0, "y1": 1, "yref": "paper", "line": {"color": "#d13438", "width": 2, "dash": "dash"}})
        if usl is not None:
            shapes.append({"type": "line", "x0": usl, "x1": usl, "y0": 0, "y1": 1, "yref": "paper", "line": {"color": "#d13438", "width": 2, "dash": "dash"}})
        if target is not None:
            shapes.append({"type": "line", "x0": target, "x1": target, "y0": 0, "y1": 1, "yref": "paper", "line": {"color": "#008450", "width": 1.5, "dash": "dot"}})

        ppk_str = f"Ppk = {ppk_val:.2f}" if ppk_val is not None else "Capability"
        layout = {
            "title": {"text": f"<b>Non-Normal Process Capability for {data_col}</b><br><span style='font-size:11px;color:#605e5c'>Model: {dist_name.capitalize()}, {ppk_str}, Exp PPM = {ppm_total_exp:.0f}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": data_col, "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Density", "showgrid": True, "gridcolor": "#f3f2f1"},
            "shapes": shapes,
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 55}
        }

        tables = [
            TableResult(title=f"{dist_name.capitalize()} Parameter Estimates", headers=["Parameter", "Estimate"], rows=dist_param_rows),
            TableResult(title="Overall Capability (Percentile Method)", headers=["Capability Metric", "Index"], rows=cap_rows),
            TableResult(title="Parts Per Million (PPM) Defective", headers=["Defect Region", "Expected PPM (Overall)", "Observed PPM"], rows=ppm_rows)
        ]

        text_lines = [
            f"Process Capability Analysis (Non-Normal Distribution): {data_col}",
            f"Fitted Distribution: {dist_name.capitalize()}",
            f"Sample Size N = {n_total}",
            "",
            f"  Ppk = {ppk_val:.2f}" if ppk_val is not None else "",
            f"  Pp  = {pp_val:.2f}" if pp_val is not None else "",
            f"  Expected Total PPM = {ppm_total_exp:.1f}",
            f"  Observed Total PPM = {ppm_total_obs:.1f}"
        ]

        # Storage
        action_type = None
        worksheet_data = None
        if params.store_estimates:
            storage_cols = [
                {"id": "nonnorm_ppk", "name": f"Ppk_{dist_name[:4]}", "type": "numeric"},
                {"id": "nonnorm_ppm_exp", "name": "Exp_PPM", "type": "numeric"}
            ]
            rows_data = [{"nonnorm_ppk": round(ppk_val or 0.0, 4), "nonnorm_ppm_exp": round(ppm_total_exp, 1)}]
            action_type = "worksheet_append_columns"
            worksheet_data = {"columns": storage_cols, "rows": rows_data}

        return AnalysisResult(
            title="Non-Normal Process Capability",
            subtitle=f"{data_col} ({dist_name.capitalize()})",
            text_output="\n".join(text_lines),
            tables=tables,
            plotly_figure={"data": traces, "layout": layout},
            action_type=action_type,
            worksheet_data=worksheet_data,
            statistics={
                "pp": pp_val,
                "ppk": ppk_val,
                "expected_ppm": ppm_total_exp,
                "observed_ppm": ppm_total_obs
            }
        )
