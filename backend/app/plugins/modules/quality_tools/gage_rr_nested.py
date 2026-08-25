"""
Gage R&R (Nested Design - Destructive MSA) Plugin for OpenMinitab.
Performs Gage Repeatability & Reproducibility for destructive testing or nested measurement systems where parts cannot be measured more than once.
Computes Nested ANOVA (Part nested within Operator), Variance Components, %Contribution, %Study Variation, %Tolerance, and Number of Distinct Categories (ndc).
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from statsmodels.formula.api import ols
from statsmodels.stats.anova import anova_lm
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class GageRRNestedParams(BaseModel):
    part_column: str = Field(
        ...,
        description="Part / Batch Column (Nested Factor)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    operator_column: str = Field(
        ...,
        description="Operator / Appraiser Column",
        json_schema_extra={"ui_type": "column_picker"}
    )
    measurement_data: str = Field(
        ...,
        description="Measurement Data (Continuous Response)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    process_tolerance: Optional[float] = Field(
        None,
        description="Process Tolerance (USL - LSL, for %Tolerance calculation)"
    )
    alpha: float = Field(
        0.05,
        ge=0.001,
        le=0.25,
        description="Alpha Significance Level",
        json_schema_extra={"sub_modal": "Options..."}
    )


class GageRRNestedPlugin(AnalysisPlugin):
    id = "gage_rr_nested"
    name = "Gage R&R (Nested)"
    menu_path = ["Stat", "Quality Tools", "Gage Study", "Gage R&R (Nested)"]
    description = "Evaluates measurement system capability for destructive testing using a Nested ANOVA design (Parts nested within Operators)."
    param_schema = GageRRNestedParams

    def execute(self, df: pd.DataFrame, params: GageRRNestedParams) -> AnalysisResult:
        part_col = params.part_column
        op_col = params.operator_column
        meas_col = params.measurement_data

        for c in [part_col, op_col, meas_col]:
            if c not in df.columns:
                raise ValueError(f"Column '{c}' not found in active worksheet.")

        sub_df = df[[op_col, part_col, meas_col]].dropna().copy()
        sub_df[meas_col] = pd.to_numeric(sub_df[meas_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n_total = len(sub_df)
        if n_total < 6:
            raise ValueError("Gage R&R (Nested) requires at least 6 measurement observations.")

        operators = sub_df[op_col].unique()
        p = len(operators)
        if p < 2:
            raise ValueError("Gage R&R (Nested) requires at least 2 distinct operators.")

        # Compute Nested ANOVA directly via group sum of squares
        grand_mean = float(np.mean(sub_df[meas_col]))
        ss_tot = float(np.sum((sub_df[meas_col] - grand_mean) ** 2))
        df_tot = n_total - 1

        # Operator SS
        op_means = sub_df.groupby(op_col)[meas_col].mean()
        op_counts = sub_df.groupby(op_col)[meas_col].count()
        ss_op = float(np.sum(op_counts * ((op_means - grand_mean) ** 2)))
        df_op = p - 1
        ms_op = ss_op / df_op if df_op > 0 else 0.0

        # Part(Operator) SS
        part_op_means = sub_df.groupby([op_col, part_col])[meas_col].mean()
        part_op_counts = sub_df.groupby([op_col, part_col])[meas_col].count()

        ss_part_nested = 0.0
        for (op_val, pt_val), pt_mean in part_op_means.items():
            cnt = part_op_counts[(op_val, pt_val)]
            op_m = op_means[op_val]
            ss_part_nested += cnt * ((pt_mean - op_m) ** 2)

        total_parts_nested = len(part_op_counts)
        df_part_nested = max(1, total_parts_nested - p)
        ms_part_nested = ss_part_nested / df_part_nested if df_part_nested > 0 else 0.0

        # Repeatability / Residual SS = SS_Total - SS_Op - SS_Part(Op)
        ss_resid = max(0.0, ss_tot - ss_op - ss_part_nested)
        df_resid = max(1, df_tot - df_op - df_part_nested)
        ms_resid = ss_resid / df_resid if df_resid > 0 else 0.0

        r = float(np.mean(part_op_counts)) # average replicates per part


        # F-test for Operator against Part(Operator)
        f_op = ms_op / ms_part_nested if ms_part_nested > 0 else 0.0
        p_op = float(1.0 - stats.f.cdf(f_op, df_op, df_part_nested))

        # F-test for Part(Operator) against Residual Repeatability
        f_part = ms_part_nested / ms_resid if ms_resid > 0 else 0.0
        p_part = float(1.0 - stats.f.cdf(f_part, df_part_nested, df_resid))

        # Variance Components
        # Var(Repeatability) = MS_Residual
        var_repeat = float(max(0.0, ms_resid))
        # Var(Part-to-Part) = (MS_Part(Op) - MS_Residual) / r
        var_part = float(max(0.0, (ms_part_nested - ms_resid) / r))
        # Var(Reproducibility / Operator) = (MS_Operator - MS_Part(Op)) / (b * r)
        b_parts_per_op = total_parts_nested / p
        var_reprod = float(max(0.0, (ms_op - ms_part_nested) / (b_parts_per_op * r)))

        var_total_gage = var_repeat + var_reprod
        var_total = var_total_gage + var_part

        pct_contrib_gage = (var_total_gage / var_total * 100.0) if var_total > 0 else 0.0
        pct_contrib_repeat = (var_repeat / var_total * 100.0) if var_total > 0 else 0.0
        pct_contrib_reprod = (var_reprod / var_total * 100.0) if var_total > 0 else 0.0
        pct_contrib_part = (var_part / var_total * 100.0) if var_total > 0 else 0.0

        sd_total = np.sqrt(var_total)
        sd_gage = np.sqrt(var_total_gage)
        sd_repeat = np.sqrt(var_repeat)
        sd_reprod = np.sqrt(var_reprod)
        sd_part = np.sqrt(var_part)

        study_var_mult = 6.0
        study_var_total = sd_total * study_var_mult
        pct_study_gage = (sd_gage / sd_total * 100.0) if sd_total > 0 else 0.0
        pct_study_repeat = (sd_repeat / sd_total * 100.0) if sd_total > 0 else 0.0
        pct_study_reprod = (sd_reprod / sd_total * 100.0) if sd_total > 0 else 0.0
        pct_study_part = (sd_part / sd_total * 100.0) if sd_total > 0 else 0.0

        # Number of Distinct Categories (ndc)
        ndc = int(np.floor(1.41 * (sd_part / sd_gage))) if sd_gage > 0 else 1

        anova_rows = [
            [op_col, int(df_op), round(ss_op, 4), round(ms_op, 4), round(f_op, 2), round(p_op, 4)],
            [f"{part_col}({op_col})", int(df_part_nested), round(ss_part_nested, 4), round(ms_part_nested, 4), round(f_part, 2), round(p_part, 4)],
            ["Repeatability", int(df_resid), round(ss_resid, 4), round(ms_resid, 4), "", ""],
            ["Total", int(df_tot), round(ss_tot, 4), "", "", ""]
        ]

        var_rows = [
            ["Total Gage R&R", round(var_total_gage, 5), round(pct_contrib_gage, 2), round(sd_gage, 4), round(sd_gage * study_var_mult, 4), round(pct_study_gage, 2)],
            ["  Repeatability", round(var_repeat, 5), round(pct_contrib_repeat, 2), round(sd_repeat, 4), round(sd_repeat * study_var_mult, 4), round(pct_study_repeat, 2)],
            ["  Reproducibility", round(var_reprod, 5), round(pct_contrib_reprod, 2), round(sd_reprod, 4), round(sd_reprod * study_var_mult, 4), round(pct_study_reprod, 2)],
            ["Part-to-Part", round(var_part, 5), round(pct_contrib_part, 2), round(sd_part, 4), round(sd_part * study_var_mult, 4), round(pct_study_part, 2)],
            ["Total Variation", round(var_total, 5), 100.0, round(sd_total, 4), round(study_var_total, 4), 100.0]
        ]

        # Bar chart of %Contribution vs %Study Var
        components = ["Total Gage R&R", "Repeatability", "Reproducibility", "Part-to-Part"]
        contribs = [pct_contrib_gage, pct_contrib_repeat, pct_contrib_reprod, pct_contrib_part]
        study_vars = [pct_study_gage, pct_study_repeat, pct_study_reprod, pct_study_part]

        traces = [
            {
                "x": components,
                "y": contribs,
                "type": "bar",
                "name": "% Contribution",
                "marker": {"color": "#008450"}
            },
            {
                "x": components,
                "y": study_vars,
                "type": "bar",
                "name": "% Study Var (6*SD)",
                "marker": {"color": "#005a9e"}
            }
        ]

        layout = {
            "title": {"text": f"<b>Gage R&R (Nested) Components of Variation</b><br><span style='font-size:11px;color:#605e5c'>%Gage Study Var = {pct_study_gage:.2f}%, ndc = {ndc}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Source of Variation", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Percent (%)", "showgrid": True, "gridcolor": "#f3f2f1"},
            "barmode": "group",
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 55}
        }

        tables = [
            TableResult(
                title="Gage R&R (Nested) ANOVA Table",
                headers=["Source", "DF", "SS", "MS", "F", "P"],
                rows=anova_rows
            ),
            TableResult(
                title="Gage R&R (Nested) Variance Components",
                headers=["Source", "VarComp", "%Contribution", "StdDev (SD)", "Study Var (6*SD)", "%Study Var (%SV)"],
                rows=var_rows
            )
        ]

        text_lines = [
            "Gage R&R (Nested) Table",
            f"Measurement: {meas_col}   Operator: {op_col}   Part: {part_col}",
            "",
            f"  {'Source':<20} {'DF':>4} {'SS':>12} {'MS':>12} {'F':>8} {'P':>8}",
            f"  {'-'*20} {'-'*4} {'-'*12} {'-'*12} {'-'*8} {'-'*8}",
        ]
        for r in anova_rows:
            text_lines.append(f"  {r[0]:<20} {str(r[1]):>4} {str(r[2]):>12} {str(r[3]):>12} {str(r[4]):>8} {str(r[5]):>8}")
        text_lines += [
            "",
            f"Number of Distinct Categories (ndc) = {ndc}",
            f"% Contribution of Gage R&R = {pct_contrib_gage:.2f}%",
            f"% Study Variation of Gage R&R = {pct_study_gage:.2f}%"
        ]

        return AnalysisResult(
            title="Gage R&R (Nested)",
            subtitle=f"{meas_col} (Destructive MSA)",
            text_output="\n".join(text_lines),
            tables=tables,
            plotly_figure={"data": traces, "layout": layout},
            statistics={
                "ndc": ndc,
                "percent_gage_study_var": pct_study_gage,
                "percent_gage_contribution": pct_contrib_gage
            }
        )
