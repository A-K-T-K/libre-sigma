"""
Capability Sixpack Plugin for OpenMinitab Quality Tools.
Combines 6 core quality tools: Xbar Chart, R/S Chart, Run Chart, Capability Histogram, Normal Probability Plot, and Capability Plot.
"""

from typing import Any, Dict, List, Optional, Tuple
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult
from ..spc.spc_constants import get_c4, get_d2, get_spc_factors
from .distribution_id import calculate_anderson_darling


class CapabilitySixpackParams(BaseModel):
    data_column: str = Field(
        ...,
        description="Measurement Variable",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    subgroup_size: int = Field(1, ge=1, le=1000, description="Subgroup Size (e.g. 5)")
    lsl: Optional[float] = Field(None, description="Lower Specification Limit (LSL)")
    usl: Optional[float] = Field(None, description="Upper Specification Limit (USL)")
    target: Optional[float] = Field(None, description="Target Specification (optional)")


class CapabilitySixpackPlugin(AnalysisPlugin):
    id = "capability_sixpack"
    name = "Capability Sixpack"
    menu_path = ["Stat", "Quality Tools", "Capability Sixpack", "Normal"]
    description = "Displays a 6-panel summary dashboard: Xbar Chart, R Chart, Run Chart, Capability Histogram, Normal Plot, and Capability Indices."
    param_schema = CapabilitySixpackParams

    def execute(self, df: pd.DataFrame, params: CapabilitySixpackParams) -> AnalysisResult:
        data_col = params.data_column
        if data_col not in df.columns:
            raise ValueError(f"Column '{data_col}' not found in active worksheet.")

        lsl, usl, target = params.lsl, params.usl, params.target
        if lsl is None and usl is None:
            raise ValueError("Specify at least one specification limit (LSL or USL).")

        raw_series = pd.to_numeric(df[data_col], errors="coerce").dropna()
        if len(raw_series) < 6:
            raise ValueError("Capability Sixpack requires at least 6 observations.")

        vals = raw_series.to_numpy(dtype=float)
        k = max(1, params.subgroup_size)

        # Chunk into subgroups
        subgroups = []
        if k > 1:
            n_chunks = len(vals) // k
            for i in range(n_chunks):
                subgroups.append(vals[i * k:(i + 1) * k])
            rem = vals[n_chunks * k:]
            if len(rem) > 1:
                subgroups.append(rem)
        else:
            subgroups = [np.array([v]) for v in vals]

        means = np.array([np.mean(sg) for sg in subgroups], dtype=float)
        ranges = np.array([np.ptp(sg) if len(sg) > 1 else 0.0 for sg in subgroups], dtype=float)
        stdevs = np.array([np.std(sg, ddof=1) if len(sg) > 1 else 0.0 for sg in subgroups], dtype=float)

        grand_mean = float(np.mean(vals))
        overall_stdev = float(np.std(vals, ddof=1))
        
        if overall_stdev < 1e-12:
            raise ValueError("Data has zero variance; Capability Sixpack cannot be generated.")

        # Compute Within Standard Deviation
        if k == 1:
            mr = np.abs(np.diff(vals))
            mean_mr = float(np.mean(mr)) if len(mr) > 0 else overall_stdev
            within_stdev = mean_mr / get_d2(2)
            chart2_y = mr.tolist()
            chart2_title = "Moving Range Chart"
            chart2_cl = mean_mr
            chart2_ucl = 3.267 * mean_mr
            chart2_lcl = 0.0
        else:
            factors = get_spc_factors(k)
            r_bar = float(np.mean(ranges))
            within_stdev = r_bar / factors["d2"]
            chart2_y = ranges.tolist()
            chart2_title = "R Chart"
            chart2_cl = r_bar
            chart2_ucl = factors["D4"] * r_bar
            chart2_lcl = factors["D3"] * r_bar

        within_stdev = max(1e-12, within_stdev)

        # Xbar control limits
        xbar_sigma = within_stdev / math.sqrt(k)
        xbar_ucl = grand_mean + 3.0 * xbar_sigma
        xbar_lcl = grand_mean - 3.0 * xbar_sigma

        # Capability Indices
        cp = (usl - lsl) / (6.0 * within_stdev) if (lsl is not None and usl is not None) else None
        cpl = (grand_mean - lsl) / (3.0 * within_stdev) if lsl is not None else None
        cpu = (usl - grand_mean) / (3.0 * within_stdev) if usl is not None else None
        cpk = min(cpl if cpl is not None else 1e6, cpu if cpu is not None else 1e6) if (cpl is not None or cpu is not None) else None

        pp = (usl - lsl) / (6.0 * overall_stdev) if (lsl is not None and usl is not None) else None
        ppl = (grand_mean - lsl) / (3.0 * overall_stdev) if lsl is not None else None
        ppu = (usl - grand_mean) / (3.0 * overall_stdev) if usl is not None else None
        ppk = min(ppl if ppl is not None else 1e6, ppu if ppu is not None else 1e6) if (ppl is not None or ppu is not None) else None

        # Normality AD test
        z_scores = stats.norm.cdf((np.sort(vals) - grand_mean) / overall_stdev)
        ad_stat = calculate_anderson_darling(z_scores)
        ad_p = float(np.clip(math.exp(1.2937 - 5.709 * ad_stat), 0.0, 1.0)) if ad_stat > 0.6 else 0.5

        # Build Session Log Tables
        sixpack_table = TableResult(
            title="Capability Sixpack Metrics for " + data_col,
            headers=["Index", "Within Estimate", "Overall Estimate"],
            rows=[
                ["Cp / Pp", f"{cp:.2f}" if cp is not None else "---", f"{pp:.2f}" if pp is not None else "---"],
                ["Cpk / Ppk", f"{cpk:.2f}" if cpk is not None else "---", f"{ppk:.2f}" if ppk is not None else "---"],
                ["CPL / PPL", f"{cpl:.2f}" if cpl is not None else "---", f"{ppl:.2f}" if ppl is not None else "---"],
                ["CPU / PPU", f"{cpu:.2f}" if cpu is not None else "---", f"{ppu:.2f}" if ppu is not None else "---"],
                ["Mean", f"{grand_mean:.4f}", f"{grand_mean:.4f}"],
                ["StDev", f"{within_stdev:.4f}", f"{overall_stdev:.4f}"],
                ["Normality AD", f"{ad_stat:.3f}", f"p = {ad_p:.4f}"]
            ]
        )

        # Plotly Composite 6-Panel Layout
        # Trace 1: Xbar chart
        n_sg = len(means)
        x_sg = list(range(1, n_sg + 1))

        plotly_fig = {
            "data": [
                # Panel 1: Xbar Chart
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": x_sg,
                    "y": means.tolist(),
                    "name": "Xbar Means",
                    "line": {"color": "#0078d4"},
                    "xaxis": "x1",
                    "yaxis": "y1"
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [1, n_sg],
                    "y": [xbar_ucl, xbar_ucl],
                    "name": "UCL",
                    "line": {"color": "#d13438", "dash": "dash"},
                    "xaxis": "x1",
                    "yaxis": "y1"
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [1, n_sg],
                    "y": [grand_mean, grand_mean],
                    "name": "Mean",
                    "line": {"color": "#008450"},
                    "xaxis": "x1",
                    "yaxis": "y1"
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [1, n_sg],
                    "y": [xbar_lcl, xbar_lcl],
                    "name": "LCL",
                    "line": {"color": "#d13438", "dash": "dash"},
                    "xaxis": "x1",
                    "yaxis": "y1"
                },

                # Panel 2: R/MR Chart
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": list(range(1, len(chart2_y) + 1)),
                    "y": chart2_y,
                    "name": chart2_title,
                    "line": {"color": "#ca5010"},
                    "xaxis": "x2",
                    "yaxis": "y2"
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [1, len(chart2_y)],
                    "y": [chart2_ucl, chart2_ucl],
                    "name": "UCL",
                    "line": {"color": "#d13438", "dash": "dash"},
                    "xaxis": "x2",
                    "yaxis": "y2"
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [1, len(chart2_y)],
                    "y": [chart2_cl, chart2_cl],
                    "name": "Center",
                    "line": {"color": "#008450"},
                    "xaxis": "x2",
                    "yaxis": "y2"
                },

                # Panel 3: Last 25 Subgroups / Values
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": list(range(max(1, len(vals) - 24), len(vals) + 1)),
                    "y": vals[-25:].tolist(),
                    "name": "Last 25 Values",
                    "line": {"color": "#881798"},
                    "xaxis": "x3",
                    "yaxis": "y3"
                },

                # Panel 4: Capability Histogram
                {
                    "type": "histogram",
                    "x": vals.tolist(),
                    "name": "Histogram",
                    "marker": {"color": "rgba(0, 120, 212, 0.5)"},
                    "xaxis": "x4",
                    "yaxis": "y4"
                },

                # Panel 5: Normal Probability Plot
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": np.sort(vals).tolist(),
                    "y": stats.norm.ppf((np.arange(1, len(vals) + 1) - 0.375) / (len(vals) + 0.25)).tolist(),
                    "name": f"AD = {ad_stat:.3f}",
                    "marker": {"color": "#0078d4", "size": 4},
                    "xaxis": "x5",
                    "yaxis": "y5"
                },

                # Panel 6: Capability Plot (Cp, Cpk, Pp, Ppk)
                {
                    "type": "bar",
                    "x": ["Cp", "Cpk", "Pp", "Ppk"],
                    "y": [cp or 0, cpk or 0, pp or 0, ppk or 0],
                    "name": "Capability Indices",
                    "marker": {"color": ["#0078d4", "#008450", "#0078d4", "#008450"]},
                    "xaxis": "x6",
                    "yaxis": "y6"
                }
            ],
            "layout": {
                "title": f"Capability Sixpack Report for {data_col}",
                "grid": {"rows": 2, "columns": 3, "pattern": "independent"},
                "showlegend": False,
                "margin": {"l": 40, "r": 30, "t": 60, "b": 40}
            }
        }

        cpk_str = f"{cpk:.2f}" if cpk is not None else "---"
        ppk_str = f"{ppk:.2f}" if ppk is not None else "---"

        return AnalysisResult(
            title=f"Capability Sixpack for {data_col}",
            subtitle=f"Cpk = {cpk_str} | Ppk = {ppk_str} | AD = {ad_stat:.3f}",
            tables=[sixpack_table],
            plotly_figure=plotly_fig,
            statistics={
                "cp": cp,
                "cpk": cpk,
                "pp": pp,
                "ppk": ppk,
                "ad_stat": ad_stat,
                "ad_p": ad_p
            }
        )
