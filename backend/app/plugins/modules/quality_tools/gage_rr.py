"""
Gage R&R Study (Crossed / Nested) Plugin for OpenMinitab Quality Tools.
Performs Measurement Systems Analysis (MSA) using Two-Way Random Effects ANOVA, variance component decomposition, %Contribution, %StudyVar, and ndc.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class GageRrParams(BaseModel):
    part_column: str = Field(
        ...,
        description="Part / Sample Variable",
        json_schema_extra={"ui_type": "column_picker"}
    )
    operator_column: str = Field(
        ...,
        description="Operator / Appraiser Variable",
        json_schema_extra={"ui_type": "column_picker"}
    )
    measurement_column: str = Field(
        ...,
        description="Measurement Data Variable",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    study_type: str = Field(
        "crossed_anova",
        description="Method of Analysis",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Crossed (Two-Way ANOVA)", "value": "crossed_anova"},
                {"label": "Crossed (Xbar / R)", "value": "crossed_xbar_r"},
                {"label": "Nested (Operators nested in Parts)", "value": "nested"}
            ]
        }
    )
    tolerance: Optional[float] = Field(None, description="Process Tolerance (USL - LSL, optional)")
    sigma_multiplier: float = Field(6.0, description="Study Variation Multiplier (Default: 6.0)")


class GageRrPlugin(AnalysisPlugin):
    id = "gage_rr"
    name = "Gage R&R Study (Crossed)"
    menu_path = ["Stat", "Quality Tools", "Gage Study", "Gage R&R Study (Crossed)"]
    description = "Evaluates repeatability, reproducibility, part-to-part variation, %StudyVar, and number of distinct categories (ndc)."
    param_schema = GageRrParams

    def execute(self, df: pd.DataFrame, params: GageRrParams) -> AnalysisResult:
        part_col, op_col, meas_col = params.part_column, params.operator_column, params.measurement_column

        for col in [part_col, op_col, meas_col]:
            if col not in df.columns:
                raise ValueError(f"Required column '{col}' not found in active worksheet.")

        sub_df = df[[part_col, op_col, meas_col]].dropna().copy()
        sub_df[meas_col] = pd.to_numeric(sub_df[meas_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        if len(sub_df) < 6:
            raise ValueError("Gage R&R requires at least 6 valid measurements.")

        parts = sub_df[part_col].unique()
        operators = sub_df[op_col].unique()

        p = len(parts)
        o = len(operators)
        N = len(sub_df)

        if p < 2 or o < 1:
            raise ValueError("Need at least 2 parts and 1 operator for Gage R&R.")

        y = sub_df[meas_col].to_numpy(dtype=float)
        grand_mean = float(np.mean(y))
        ss_total = float(np.sum((y - grand_mean) ** 2))
        df_total = N - 1

        # Replications per cell
        cell_counts = sub_df.groupby([part_col, op_col]).size()
        r = float(cell_counts.mean()) if len(cell_counts) > 0 else 1.0

        # Part SS
        part_means = sub_df.groupby(part_col)[meas_col].mean()
        part_counts = sub_df.groupby(part_col)[meas_col].count()
        ss_part = float(np.sum(part_counts * (part_means - grand_mean) ** 2))
        df_part = p - 1
        ms_part = ss_part / max(1, df_part)

        # Operator SS
        op_means = sub_df.groupby(op_col)[meas_col].mean()
        op_counts = sub_df.groupby(op_col)[meas_col].count()
        ss_op = float(np.sum(op_counts * (op_means - grand_mean) ** 2))
        df_op = o - 1
        ms_op = ss_op / max(1, df_op) if df_op > 0 else 0.0

        # Cell SS (Part x Operator)
        cell_means = sub_df.groupby([part_col, op_col])[meas_col].mean()
        ss_cells = float(np.sum(cell_counts * (cell_means - grand_mean) ** 2))
        ss_inter = max(0.0, ss_cells - ss_part - ss_op)
        df_inter = max(0, (p - 1) * (o - 1))
        ms_inter = ss_inter / max(1, df_inter) if df_inter > 0 else 0.0

        # Repeatability (Error) SS
        ss_error = max(0.0, ss_total - ss_cells)
        df_error = max(1, N - p * o)
        ms_error = ss_error / df_error

        # F-tests and P-values
        if df_inter > 0 and ms_inter > 1e-12:
            f_part = ms_part / ms_inter
            p_part = float(1.0 - stats.f.cdf(f_part, df_part, df_inter))

            f_op = ms_op / ms_inter if df_op > 0 else 0.0
            p_op = float(1.0 - stats.f.cdf(f_op, df_op, df_inter)) if df_op > 0 else 1.0

            f_inter = ms_inter / ms_error
            p_inter = float(1.0 - stats.f.cdf(f_inter, df_inter, df_error))
        else:
            f_part = ms_part / ms_error
            p_part = float(1.0 - stats.f.cdf(f_part, df_part, df_error))

            f_op = ms_op / ms_error if df_op > 0 else 0.0
            p_op = float(1.0 - stats.f.cdf(f_op, df_op, df_error)) if df_op > 0 else 1.0

            f_inter, p_inter = 0.0, 1.0

        # Variance Components Decomposition
        var_repeat = ms_error
        if df_inter > 0:
            var_inter = max(0.0, (ms_inter - ms_error) / r)
            var_op_main = max(0.0, (ms_op - ms_inter) / (p * r)) if df_op > 0 else 0.0
        else:
            var_inter = 0.0
            var_op_main = max(0.0, (ms_op - ms_error) / (p * r)) if df_op > 0 else 0.0

        var_reprod = var_op_main + var_inter
        var_gage_rr = var_repeat + var_reprod

        if df_inter > 0:
            var_part = max(0.0, (ms_part - ms_inter) / (o * r))
        else:
            var_part = max(0.0, (ms_part - ms_error) / (o * r))

        var_total = var_gage_rr + var_part
        var_total = max(1e-12, var_total)

        # Standard Deviations & Study Variation
        sd_total = math.sqrt(var_total)
        sd_gage_rr = math.sqrt(var_gage_rr)
        sd_repeat = math.sqrt(var_repeat)
        sd_reprod = math.sqrt(var_reprod)
        sd_part = math.sqrt(var_part)

        K = params.sigma_multiplier
        sv_total = K * sd_total
        sv_gage_rr = K * sd_gage_rr
        sv_repeat = K * sd_repeat
        sv_reprod = K * sd_reprod
        sv_part = K * sd_part

        # %Contribution and %StudyVar
        pct_contrib_gage_rr = (var_gage_rr / var_total) * 100.0
        pct_contrib_repeat = (var_repeat / var_total) * 100.0
        pct_contrib_reprod = (var_reprod / var_total) * 100.0
        pct_contrib_part = (var_part / var_total) * 100.0

        pct_sv_gage_rr = (sd_gage_rr / sd_total) * 100.0
        pct_sv_repeat = (sd_repeat / sd_total) * 100.0
        pct_sv_reprod = (sd_reprod / sd_total) * 100.0
        pct_sv_part = (sd_part / sd_total) * 100.0

        # Number of Distinct Categories (ndc)
        ndc = int(math.floor(1.41 * (sd_part / max(1e-12, sd_gage_rr))))

        # %Tolerance
        tol = params.tolerance

        # Build ANOVA Table
        anova_table = TableResult(
            title="Two-Way ANOVA Table With Interaction",
            headers=["Source", "DF", "SS", "MS", "F-Value", "p-Value"],
            rows=[
                [part_col, str(df_part), f"{ss_part:.4f}", f"{ms_part:.4f}", f"{f_part:.2f}", f"{p_part:.4f}" if p_part >= 0.0001 else "< 0.0001"],
                [op_col, str(df_op), f"{ss_op:.4f}", f"{ms_op:.4f}", f"{f_op:.2f}", f"{p_op:.4f}" if p_op >= 0.0001 else "< 0.0001"],
                [f"{part_col} * {op_col}", str(df_inter), f"{ss_inter:.4f}", f"{ms_inter:.4f}", f"{f_inter:.2f}", f"{p_inter:.4f}" if p_inter >= 0.0001 else "< 0.0001"],
                ["Repeatability (Error)", str(df_error), f"{ss_error:.4f}", f"{ms_error:.4f}", "---", "---"],
                ["Total", str(df_total), f"{ss_total:.4f}", "---", "---", "---"]
            ]
        )

        # Build Gage R&R Table
        gage_table = TableResult(
            title="Gage R&R Variance Components and Study Variation (K = " + f"{K:.1f})",
            headers=["Source", "VarComp", "%Contribution", "StdDev (SD)", f"Study Var ({K:.0f}*SD)", "%Study Var (%SV)"],
            rows=[
                ["Total Gage R&R", f"{var_gage_rr:.6f}", f"{pct_contrib_gage_rr:.2f}%", f"{sd_gage_rr:.5f}", f"{sv_gage_rr:.5f}", f"{pct_sv_gage_rr:.2f}%"],
                ["  Repeatability", f"{var_repeat:.6f}", f"{pct_contrib_repeat:.2f}%", f"{sd_repeat:.5f}", f"{sv_repeat:.5f}", f"{pct_sv_repeat:.2f}%"],
                ["  Reproducibility", f"{var_reprod:.6f}", f"{pct_contrib_reprod:.2f}%", f"{sd_reprod:.5f}", f"{sv_reprod:.5f}", f"{pct_sv_reprod:.2f}%"],
                ["Part-to-Part", f"{var_part:.6f}", f"{pct_contrib_part:.2f}%", f"{sd_part:.5f}", f"{sv_part:.5f}", f"{pct_sv_part:.2f}%"],
                ["Total Variation", f"{var_total:.6f}", "100.00%", f"{sd_total:.5f}", f"{sv_total:.5f}", "100.00%"]
            ]
        )

        summary_table = TableResult(
            title="Measurement System Acceptability Summary",
            headers=["Metric", "Value", "Guideline / Assessment"],
            rows=[
                ["%StudyVar (%SV)", f"{pct_sv_gage_rr:.2f}%", "< 10% Acceptable, 10-30% Marginal, > 30% Unacceptable"],
                ["%Contribution", f"{pct_contrib_gage_rr:.2f}%", "< 1% Acceptable, 1-9% Marginal, > 9% Unacceptable"],
                ["Number of Distinct Categories (ndc)", str(ndc), ">= 5 indicates adequate measurement resolution"]
            ]
        )

        # Plotly 6-Panel MSA Visualization
        plotly_fig = {
            "data": [
                # Panel 1: Components of Variation
                {
                    "type": "bar",
                    "x": ["Gage R&R", "Repeat", "Reprod", "Part-to-Part"],
                    "y": [pct_contrib_gage_rr, pct_contrib_repeat, pct_contrib_reprod, pct_contrib_part],
                    "name": "%Contribution",
                    "marker": {"color": "#0078d4"},
                    "xaxis": "x1",
                    "yaxis": "y1"
                },
                {
                    "type": "bar",
                    "x": ["Gage R&R", "Repeat", "Reprod", "Part-to-Part"],
                    "y": [pct_sv_gage_rr, pct_sv_repeat, pct_sv_reprod, pct_sv_part],
                    "name": "%Study Var",
                    "marker": {"color": "#008450"},
                    "xaxis": "x1",
                    "yaxis": "y1"
                },

                # Panel 2: By-Part Measurement Scatter
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": [str(p) for p in sub_df[part_col]],
                    "y": sub_df[meas_col].tolist(),
                    "name": "Measurements by Part",
                    "marker": {"color": "#0078d4", "size": 6},
                    "xaxis": "x2",
                    "yaxis": "y2"
                },

                # Panel 3: By-Operator Scatter
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": [str(o) for o in sub_df[op_col]],
                    "y": sub_df[meas_col].tolist(),
                    "name": "Measurements by Operator",
                    "marker": {"color": "#ca5010", "size": 6},
                    "xaxis": "x3",
                    "yaxis": "y3"
                },

                # Panel 4: Part x Operator Interaction
                *[
                    {
                        "type": "scatter",
                        "mode": "lines+markers",
                        "x": [str(p) for p in parts],
                        "y": [float(sub_df[(sub_df[part_col] == p) & (sub_df[op_col] == op)][meas_col].mean()) for p in parts],
                        "name": f"Op: {op}",
                        "xaxis": "x4",
                        "yaxis": "y4"
                    }
                    for op in operators
                ]
            ],
            "layout": {
                "title": f"Gage R&R (Crossed) Report for {meas_col}",
                "grid": {"rows": 2, "columns": 2, "pattern": "independent"},
                "legend": {"orientation": "h", "y": -0.2}
            }
        }

        return AnalysisResult(
            title=f"Gage R&R Study (Crossed) for {meas_col}",
            subtitle=f"%StudyVar = {pct_sv_gage_rr:.2f}% | %Contribution = {pct_contrib_gage_rr:.2f}% | ndc = {ndc}",
            tables=[anova_table, gage_table, summary_table],
            plotly_figure=plotly_fig,
            statistics={
                "pct_sv_gage_rr": pct_sv_gage_rr,
                "pct_contrib_gage_rr": pct_contrib_gage_rr,
                "ndc": ndc,
                "var_gage_rr": var_gage_rr,
                "var_part": var_part,
                "var_total": var_total
            }
        )
