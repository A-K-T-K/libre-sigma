"""
Process Capability Analysis Plugin for OpenMinitab Quality Tools.
Computes potential (Cp, Cpk, Cpm) and overall (Pp, Ppk) capability indices, within-subgroup variation, and PPM statistics.
"""

from typing import Any, Dict, List, Optional, Tuple
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult
from ..spc.spc_constants import get_c4, get_d2


class ProcessCapabilityParams(BaseModel):
    data_column: str = Field(
        ...,
        description="Measurement Variable",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    subgroup_method: str = Field(
        "single",
        description="Subgroup Option",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Subgroup size (Constant)", "value": "single"},
                {"label": "Subgroup column", "value": "column"}
            ]
        }
    )
    subgroup_size: int = Field(1, ge=1, le=1000, description="Subgroup Size")
    subgroup_column: Optional[str] = Field(
        None,
        description="Subgroup Variable (optional)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    lsl: Optional[float] = Field(None, description="Lower Specification Limit (LSL)")
    usl: Optional[float] = Field(None, description="Upper Specification Limit (USL)")
    target: Optional[float] = Field(None, description="Target Specification (T, optional)")
    within_estimate_method: str = Field(
        "pooled",
        description="Within-subgroup Variation Estimate",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Pooled Standard Deviation (s_p / c4)", "value": "pooled"},
                {"label": "Average Range (Rbar / d2)", "value": "r_bar"},
                {"label": "Average StdDev (Sbar / c4)", "value": "s_bar"}
            ]
        }
    )
    historical_mean: Optional[float] = Field(None, description="Historical Mean (optional)")
    historical_stdev: Optional[float] = Field(None, description="Historical StdDev (optional)")


class ProcessCapabilityPlugin(AnalysisPlugin):
    id = "process_capability"
    name = "Process Capability Analysis"
    menu_path = ["Stat", "Quality Tools", "Capability Analysis", "Normal"]
    description = "Evaluates process performance against customer specifications using Cp, Cpk, Pp, Ppk, and PPM metrics."
    param_schema = ProcessCapabilityParams

    def execute(self, df: pd.DataFrame, params: ProcessCapabilityParams) -> AnalysisResult:
        data_col = params.data_column
        if data_col not in df.columns:
            raise ValueError(f"Column '{data_col}' not found in active worksheet.")

        lsl, usl, target = params.lsl, params.usl, params.target
        if lsl is None and usl is None:
            raise ValueError("Specify at least one specification limit (LSL or USL).")
        if lsl is not None and usl is not None and lsl >= usl:
            raise ValueError("LSL must be strictly less than USL.")

        raw_series = pd.to_numeric(df[data_col], errors="coerce").dropna()
        if len(raw_series) < 5:
            raise ValueError("Process Capability Analysis requires at least 5 numeric observations.")

        # Subgroup decomposition
        subgroups: List[np.ndarray] = []
        if params.subgroup_method == "column" and params.subgroup_column and params.subgroup_column in df.columns:
            sub_col = df.loc[raw_series.index, params.subgroup_column]
            grouped = df.loc[raw_series.index].groupby(sub_col, sort=False)[data_col]
            for _, grp in grouped:
                arr = pd.to_numeric(grp, errors="coerce").dropna().to_numpy(dtype=float)
                if len(arr) > 0:
                    subgroups.append(arr)
        elif params.subgroup_size > 1:
            k = params.subgroup_size
            vals = raw_series.to_numpy(dtype=float)
            n_chunks = len(vals) // k
            for i in range(n_chunks):
                subgroups.append(vals[i * k:(i + 1) * k])
            rem = vals[n_chunks * k:]
            if len(rem) > 1:
                subgroups.append(rem)
        else:
            # Individual observations (k = 1): compute MR / d2(2) for within stdev
            vals = raw_series.to_numpy(dtype=float)
            subgroups = [vals]

        all_vals = np.concatenate(subgroups) if len(subgroups) > 0 else raw_series.to_numpy(dtype=float)
        n_total = len(all_vals)
        mean_val = float(params.historical_mean) if params.historical_mean is not None else float(np.mean(all_vals))
        overall_stdev = float(params.historical_stdev) if params.historical_stdev is not None else float(np.std(all_vals, ddof=1))

        if overall_stdev < 1e-12:
            raise ValueError("Data has zero variance; capability cannot be computed.")

        # Compute Within Standard Deviation
        if len(subgroups) == 1 and params.subgroup_size == 1:
            # Moving Range of length 2
            mr = np.abs(np.diff(all_vals))
            mean_mr = float(np.mean(mr)) if len(mr) > 0 else overall_stdev
            within_stdev = mean_mr / get_d2(2)
        else:
            # Multi-subgroup unbiasing
            k_sizes = [len(sg) for sg in subgroups]
            avg_k = int(round(np.mean(k_sizes)))
            avg_k = max(2, avg_k)

            if params.within_estimate_method == "r_bar":
                ranges = [np.ptp(sg) for sg in subgroups if len(sg) >= 2]
                r_bar = float(np.mean(ranges)) if len(ranges) > 0 else overall_stdev
                within_stdev = r_bar / get_d2(avg_k)
            elif params.within_estimate_method == "s_bar":
                stdevs = [np.std(sg, ddof=1) for sg in subgroups if len(sg) >= 2]
                s_bar = float(np.mean(stdevs)) if len(stdevs) > 0 else overall_stdev
                within_stdev = s_bar / get_c4(avg_k)
            else: # Pooled
                sum_sq = sum(np.sum((sg - np.mean(sg)) ** 2) for sg in subgroups if len(sg) >= 2)
                df_pool = sum(len(sg) - 1 for sg in subgroups if len(sg) >= 2)
                if df_pool > 0:
                    s_pool = math.sqrt(sum_sq / df_pool)
                    within_stdev = s_pool / get_c4(df_pool + 1)
                else:
                    within_stdev = overall_stdev

        within_stdev = max(1e-12, within_stdev)

        # Potential Capability (Within)
        cp, cpl, cpu, cpk, cpm = None, None, None, None, None
        if lsl is not None and usl is not None:
            cp = (usl - lsl) / (6.0 * within_stdev)
        if lsl is not None:
            cpl = (mean_val - lsl) / (3.0 * within_stdev)
        if usl is not None:
            cpu = (usl - mean_val) / (3.0 * within_stdev)
        if cpl is not None and cpu is not None:
            cpk = min(cpl, cpu)
        elif cpl is not None:
            cpk = cpl
        elif cpu is not None:
            cpk = cpu

        if target is not None and lsl is not None and usl is not None:
            cpm = (usl - lsl) / (6.0 * math.sqrt(within_stdev ** 2 + (mean_val - target) ** 2))

        # Overall Capability (Overall)
        pp, ppl, ppu, ppk = None, None, None, None
        if lsl is not None and usl is not None:
            pp = (usl - lsl) / (6.0 * overall_stdev)
        if lsl is not None:
            ppl = (mean_val - lsl) / (3.0 * overall_stdev)
        if usl is not None:
            ppu = (usl - mean_val) / (3.0 * overall_stdev)
        if ppl is not None and ppu is not None:
            ppk = min(ppl, ppu)
        elif ppl is not None:
            ppk = ppl
        elif ppu is not None:
            ppk = ppu

        # PPM Calculations (Observed vs Expected Within vs Expected Overall)
        obs_below = int(np.sum(all_vals < lsl)) if lsl is not None else 0
        obs_above = int(np.sum(all_vals > usl)) if usl is not None else 0
        ppm_obs_below = (obs_below / n_total) * 1e6
        ppm_obs_above = (obs_above / n_total) * 1e6
        ppm_obs_total = ppm_obs_below + ppm_obs_above

        # Expected Within
        p_within_below = stats.norm.cdf((lsl - mean_val) / within_stdev) if lsl is not None else 0.0
        p_within_above = 1.0 - stats.norm.cdf((usl - mean_val) / within_stdev) if usl is not None else 0.0
        ppm_within_below = float(p_within_below * 1e6)
        ppm_within_above = float(p_within_above * 1e6)
        ppm_within_total = ppm_within_below + ppm_within_above

        # Expected Overall
        p_overall_below = stats.norm.cdf((lsl - mean_val) / overall_stdev) if lsl is not None else 0.0
        p_overall_above = 1.0 - stats.norm.cdf((usl - mean_val) / overall_stdev) if usl is not None else 0.0
        ppm_overall_below = float(p_overall_below * 1e6)
        ppm_overall_above = float(p_overall_above * 1e6)
        ppm_overall_total = ppm_overall_below + ppm_overall_above

        # Construct Tables
        indices_table = TableResult(
            title="Process Capability Indices",
            headers=["Potential (Within) Capability", "Estimate", "Overall Capability", "Estimate"],
            rows=[
                ["Cp", f"{cp:.2f}" if cp is not None else "---", "Pp", f"{pp:.2f}" if pp is not None else "---"],
                ["CPL", f"{cpl:.2f}" if cpl is not None else "---", "PPL", f"{ppl:.2f}" if ppl is not None else "---"],
                ["CPU", f"{cpu:.2f}" if cpu is not None else "---", "PPU", f"{ppu:.2f}" if ppu is not None else "---"],
                ["Cpk", f"{cpk:.2f}" if cpk is not None else "---", "Ppk", f"{ppk:.2f}" if ppk is not None else "---"],
                ["Cpm", f"{cpm:.2f}" if cpm is not None else "---", "Cpm (Target)", f"{target:.3f}" if target is not None else "---"]
            ]
        )

        ppm_table = TableResult(
            title="Parts Per Million (PPM) Defect Performance",
            headers=["Performance Condition", "PPM < LSL", "PPM > USL", "PPM Total"],
            rows=[
                ["Observed Performance", f"{ppm_obs_below:.1f}", f"{ppm_obs_above:.1f}", f"{ppm_obs_total:.1f}"],
                ["Expected " + params.within_estimate_method.capitalize() + " (Within)", f"{ppm_within_below:.1f}", f"{ppm_within_above:.1f}", f"{ppm_within_total:.1f}"],
                ["Expected Overall Performance", f"{ppm_overall_below:.1f}", f"{ppm_overall_above:.1f}", f"{ppm_overall_total:.1f}"]
            ]
        )

        process_summary_table = TableResult(
            title="Process Parameters",
            headers=["Parameter", "Value"],
            rows=[
                ["LSL", f"{lsl:.4f}" if lsl is not None else "---"],
                ["Target", f"{target:.4f}" if target is not None else "---"],
                ["USL", f"{usl:.4f}" if usl is not None else "---"],
                ["Sample Mean", f"{mean_val:.4f}"],
                ["Sample Size (N)", str(n_total)],
                ["Standard Deviation (Within)", f"{within_stdev:.4f}"],
                ["Standard Deviation (Overall)", f"{overall_stdev:.4f}"]
            ]
        )

        # Plotly Histogram + Specs + Fitted Curves
        x_grid_min = min(lsl - 0.5 * overall_stdev if lsl is not None else np.min(all_vals), np.min(all_vals) - 0.5 * overall_stdev)
        x_grid_max = max(usl + 0.5 * overall_stdev if usl is not None else np.max(all_vals), np.max(all_vals) + 0.5 * overall_stdev)
        x_grid = np.linspace(x_grid_min, x_grid_max, 250)

        pdf_within = stats.norm.pdf(x_grid, loc=mean_val, scale=within_stdev)
        pdf_overall = stats.norm.pdf(x_grid, loc=mean_val, scale=overall_stdev)

        plotly_fig = {
            "data": [
                {
                    "type": "histogram",
                    "x": all_vals.tolist(),
                    "histnorm": "probability density",
                    "name": "Process Data",
                    "marker": {"color": "rgba(0, 120, 212, 0.4)", "line": {"color": "#0078d4", "width": 1}}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": x_grid.tolist(),
                    "y": pdf_within.tolist(),
                    "name": f"Within Fit (StDev={within_stdev:.3f})",
                    "line": {"color": "#d13438", "width": 2, "dash": "dash"}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": x_grid.tolist(),
                    "y": pdf_overall.tolist(),
                    "name": f"Overall Fit (StDev={overall_stdev:.3f})",
                    "line": {"color": "#004d2c", "width": 2}
                }
            ],
            "layout": {
                "title": f"Process Capability Report for {data_col}",
                "xaxis": {"title": data_col, "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": "Density", "showgrid": True, "gridcolor": "#ececec"},
                "shapes": [
                    *([{"type": "line", "x0": lsl, "y0": 0, "x1": lsl, "y1": max(np.max(pdf_within), np.max(pdf_overall)) * 1.1, "line": {"color": "#d13438", "width": 2, "dash": "dot"}}] if lsl is not None else []),
                    *([{"type": "line", "x0": usl, "y0": 0, "x1": usl, "y1": max(np.max(pdf_within), np.max(pdf_overall)) * 1.1, "line": {"color": "#d13438", "width": 2, "dash": "dot"}}] if usl is not None else []),
                    *([{"type": "line", "x0": target, "y0": 0, "x1": target, "y1": max(np.max(pdf_within), np.max(pdf_overall)) * 1.1, "line": {"color": "#008450", "width": 2, "dash": "solid"}}] if target is not None else [])
                ],
                "annotations": [
                    *([{"x": lsl, "y": max(np.max(pdf_within), np.max(pdf_overall)) * 1.12, "text": f"LSL = {lsl}", "showarrow": False, "font": {"color": "#d13438", "size": 10}}] if lsl is not None else []),
                    *([{"x": usl, "y": max(np.max(pdf_within), np.max(pdf_overall)) * 1.12, "text": f"USL = {usl}", "showarrow": False, "font": {"color": "#d13438", "size": 10}}] if usl is not None else [])
                ],
                "legend": {"orientation": "h", "y": -0.2}
            }
        }

        cpk_str = f"{cpk:.2f}" if cpk is not None else "---"
        ppk_str = f"{ppk:.2f}" if ppk is not None else "---"

        return AnalysisResult(
            title=f"Process Capability Report for {data_col}",
            subtitle=f"Cpk = {cpk_str} | Ppk = {ppk_str} | Mean = {mean_val:.4f}",
            tables=[indices_table, ppm_table, process_summary_table],
            plotly_figure=plotly_fig,
            statistics={
                "mean": mean_val,
                "stdev_within": within_stdev,
                "stdev_overall": overall_stdev,
                "cp": cp,
                "cpk": cpk,
                "pp": pp,
                "ppk": ppk,
                "ppm_within_total": ppm_within_total,
                "ppm_overall_total": ppm_overall_total
            }
        )
