"""
Gage Linearity and Bias Study Plugin for OpenMinitab.
Assesses whether a measurement system has consistent bias across its expected operating range (Linearity) and tests the statistical significance of bias at each reference standard.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class GageLinearityBiasParams(BaseModel):
    reference_values: str = Field(
        ...,
        description="Part Reference Values (Standard / Master Column)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    measurement_data: str = Field(
        ...,
        description="Measurement Data Column",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    process_variation: Optional[float] = Field(
        None,
        description="Process Variation (e.g. 6*SD or Tolerance, for %Linearity & %Bias)"
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%)",
        json_schema_extra={"sub_modal": "Options..."}
    )


class GageLinearityBiasPlugin(AnalysisPlugin):
    id = "gage_linearity_bias"
    name = "Gage Linearity and Bias Study"
    menu_path = ["Stat", "Quality Tools", "Gage Study", "Gage Linearity and Bias Study"]
    description = "Evaluates whether measurement bias is constant across part sizes (Linearity) and calculates bias per reference part."
    param_schema = GageLinearityBiasParams

    def execute(self, df: pd.DataFrame, params: GageLinearityBiasParams) -> AnalysisResult:
        ref_col = params.reference_values
        meas_col = params.measurement_data

        if ref_col not in df.columns or meas_col not in df.columns:
            raise ValueError(f"Columns '{ref_col}' and/or '{meas_col}' not found in active worksheet.")

        sub_df = df[[ref_col, meas_col]].dropna().copy()
        sub_df[ref_col] = pd.to_numeric(sub_df[ref_col], errors="coerce")
        sub_df[meas_col] = pd.to_numeric(sub_df[meas_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n_total = len(sub_df)
        if n_total < 4:
            raise ValueError("Gage Linearity and Bias study requires at least 4 measurements.")

        # Compute Bias = Measured - Reference
        sub_df["Bias"] = sub_df[meas_col] - sub_df[ref_col]

        # Group by Reference Value
        ref_groups = sub_df.groupby(ref_col)
        unique_refs = sorted(sub_df[ref_col].unique())
        if len(unique_refs) < 2:
            raise ValueError("Gage Linearity study requires at least 2 distinct reference standard parts.")

        # Fit OLS: Bias = a + b * Reference
        X = sm.add_constant(sub_df[ref_col].to_numpy(dtype=float))
        y_bias = sub_df["Bias"].to_numpy(dtype=float)
        reg_model = sm.OLS(y_bias, X).fit()

        intercept = float(reg_model.params[0])
        slope = float(reg_model.params[1])
        r2 = float(reg_model.rsquared)
        p_slope = float(reg_model.pvalues[1])

        # Overall average bias
        overall_bias = float(np.mean(y_bias))
        overall_se = float(np.std(y_bias, ddof=1) / np.sqrt(n_total))
        overall_t = overall_bias / overall_se if overall_se > 0 else 0.0
        overall_p = float(2.0 * (1.0 - stats.t.cdf(abs(overall_t), df=n_total - 1)))

        # Process Variation
        proc_var = params.process_variation if (params.process_variation and params.process_variation > 0) else float(6.0 * np.std(sub_df[meas_col], ddof=1))
        # Linearity = |slope| * Process_Variation
        linearity_val = abs(slope) * proc_var
        pct_linearity = (linearity_val / proc_var * 100.0) if proc_var > 0 else 0.0
        pct_bias = (abs(overall_bias) / proc_var * 100.0) if proc_var > 0 else 0.0

        # Part Bias table
        part_bias_rows = []
        for ref_val in unique_refs:
            grp_data = sub_df[sub_df[ref_col] == ref_val]
            grp_bias = grp_data["Bias"].to_numpy(dtype=float)
            n_part = len(grp_bias)
            mean_bias = float(np.mean(grp_bias))
            sd_bias = float(np.std(grp_bias, ddof=1)) if n_part > 1 else 0.0
            se_part = sd_bias / np.sqrt(n_part) if n_part > 0 else 0.0
            t_part = mean_bias / se_part if se_part > 0 else 0.0
            p_part = float(2.0 * (1.0 - stats.t.cdf(abs(t_part), df=max(1, n_part - 1))))
            pct_part_bias = (abs(mean_bias) / proc_var * 100.0) if proc_var > 0 else 0.0

            part_bias_rows.append([
                round(float(ref_val), 4),
                n_part,
                round(float(np.mean(grp_data[meas_col])), 4),
                round(mean_bias, 4),
                round(pct_part_bias, 2),
                round(t_part, 2),
                round(p_part, 4)
            ])

        # Plot: Reference Value vs Bias with Fitted Line and 95% CI bands
        x_pts = sub_df[ref_col].to_numpy()
        x_line = np.linspace(min(x_pts), max(x_pts), 100)
        y_fit = intercept + slope * x_line

        # Confidence intervals for regression line
        t_crit = stats.t.ppf(1.0 - (1.0 - params.confidence_level / 100.0) / 2.0, df=n_total - 2)
        s_err = np.sqrt(reg_model.mse_resid)
        x_mean = np.mean(x_pts)
        ss_x = np.sum((x_pts - x_mean) ** 2)
        se_line = s_err * np.sqrt(1.0 / n_total + ((x_line - x_mean) ** 2) / max(1e-6, ss_x))
        ci_upper = y_fit + t_crit * se_line
        ci_lower = y_fit - t_crit * se_line

        traces = [
            {
                "x": x_pts.tolist(),
                "y": y_bias.tolist(),
                "mode": "markers",
                "name": "Observed Bias",
                "marker": {"color": "#005a9e", "size": 6}
            },
            {
                "x": x_line.tolist(),
                "y": y_fit.tolist(),
                "mode": "lines",
                "name": f"Linearity Fit: Bias = {intercept:.4f} + {slope:.4f}*Ref",
                "line": {"color": "#008450", "width": 2}
            },
            {
                "x": x_line.tolist() + x_line.tolist()[::-1],
                "y": ci_upper.tolist() + ci_lower.tolist()[::-1],
                "fill": "toself",
                "fillcolor": "rgba(0, 132, 80, 0.12)",
                "line": {"color": "transparent"},
                "name": f"{params.confidence_level:.0f}% CI Band"
            }
        ]

        # Zero Bias reference line
        shapes = [{
            "type": "line",
            "xref": "paper",
            "x0": 0,
            "x1": 1,
            "y0": 0,
            "y1": 0,
            "line": {"color": "#d13438", "width": 1.5, "dash": "dash"}
        }]

        layout = {
            "title": {"text": f"<b>Gage Linearity and Bias Plot ({meas_col} vs {ref_col})</b><br><span style='font-size:11px;color:#605e5c'>Linearity = {linearity_val:.4f} ({pct_linearity:.2f}%), R-Sq = {r2*100:.1f}%</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": f"Reference Standard ({ref_col})", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Measurement Bias", "showgrid": True, "gridcolor": "#f3f2f1"},
            "shapes": shapes,
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 55}
        }

        linearity_table = TableResult(
            title="Gage Linearity and Overall Bias",
            headers=["Metric", "Value", "% Process Variation", "P-Value"],
            rows=[
                ["Linearity (|Slope| * PV)", f"{linearity_val:.4f}", f"{pct_linearity:.2f}%", f"{p_slope:.4f}"],
                ["Overall Bias", f"{overall_bias:.4f}", f"{pct_bias:.2f}%", f"{overall_p:.4f}"],
                ["Slope (b)", f"{slope:.6f}", "", f"{p_slope:.4f}"],
                ["Intercept (a)", f"{intercept:.6f}", "", f"{float(reg_model.pvalues[0]):.4f}"],
                ["R-Squared", f"{r2 * 100:.2f}%", "", ""]
            ]
        )

        part_bias_table = TableResult(
            title="Gage Bias by Reference Standard",
            headers=["Reference Value", "N", "Average Measured", "Bias", "% Bias", "T-Statistic", "P-Value"],
            rows=part_bias_rows
        )

        text_lines = [
            f"Gage Linearity and Bias Study: {meas_col}",
            f"Reference Standard: {ref_col}",
            "",
            f"Linearity Equation: Bias = {intercept:.4f} + ({slope:.4f}) * Reference",
            f"Linearity = {linearity_val:.4f}   %Linearity = {pct_linearity:.2f}% (P = {p_slope:.4f})",
            f"Overall Bias = {overall_bias:.4f}   %Bias = {pct_bias:.2f}% (P = {overall_p:.4f})",
            "",
            f"  {'Ref Value':<12} {'N':>4} {'Average':>12} {'Bias':>10} {'%Bias':>8} {'T':>8} {'P-Value':>10}",
            f"  {'-'*12} {'-'*4} {'-'*12} {'-'*10} {'-'*8} {'-'*8} {'-'*10}",
        ]
        for r in part_bias_rows:
            text_lines.append(f"  {r[0]:<12.4f} {str(r[1]):>4} {r[2]:>12.4f} {r[3]:>10.4f} {r[4]:>8.2f} {r[5]:>8.2f} {r[6]:>10.4f}")

        return AnalysisResult(
            title="Gage Linearity and Bias Study",
            subtitle=f"{meas_col} by {ref_col}",
            text_output="\n".join(text_lines),
            tables=[linearity_table, part_bias_table],
            plotly_figure={"data": traces, "layout": layout},
            statistics={
                "linearity": linearity_val,
                "percent_linearity": pct_linearity,
                "overall_bias": overall_bias,
                "r_squared": r2
            }
        )
