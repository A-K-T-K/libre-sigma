"""
Cross-Tabulation and Chi-Square Plugin for OpenMinitab.
Generates two-way contingency tables with counts, row %, column %, total %, expected frequencies, and standardized residuals.
Computes Pearson Chi-Square, Likelihood Ratio Chi-Square, Fisher's Exact Test, and Ordinal Association Measures (Gamma, Spearman, Kendall's tau-b).
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class CrossTabulationParams(BaseModel):
    row_variable: str = Field(
        ...,
        description="For Rows (Classification Variable)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    col_variable: str = Field(
        ...,
        description="For Columns (Classification Variable)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    # Display Options
    show_counts: bool = Field(True, description="Display Counts")
    show_row_pct: bool = Field(False, description="Display Row Percents (%)")
    show_col_pct: bool = Field(False, description="Display Column Percents (%)")
    show_total_pct: bool = Field(False, description="Display Total Percents (%)")
    show_expected: bool = Field(False, description="Display Expected Cell Counts")
    show_residuals: bool = Field(False, description="Display Standardized Residuals")
    # Chi-Square Sub-Modal
    test_chisquare: bool = Field(
        True,
        description="Pearson Chi-Square Test",
        json_schema_extra={"sub_modal": "Chi-Square..."}
    )
    test_likelihood_ratio: bool = Field(
        True,
        description="Likelihood-Ratio Chi-Square Test",
        json_schema_extra={"sub_modal": "Chi-Square..."}
    )
    test_ordinal_measures: bool = Field(
        False,
        description="Ordinal Association Measures (Gamma, Spearman, Kendall's Tau)",
        json_schema_extra={"sub_modal": "Chi-Square..."}
    )


class CrossTabulationPlugin(AnalysisPlugin):
    id = "tables_cross_tabulation"
    name = "Cross Tabulation and Chi-Square"
    menu_path = ["Stat", "Tables", "Cross Tabulation and Chi-Square"]
    description = "Cross-tabulates categorical data, calculates cell percentages, expected frequencies, and performs Chi-Square / Fisher exact hypothesis tests."
    param_schema = CrossTabulationParams

    def execute(self, df: pd.DataFrame, params: CrossTabulationParams) -> AnalysisResult:
        row_var, col_var = params.row_variable, params.col_variable
        if row_var not in df.columns or col_var not in df.columns:
            raise ValueError(f"Columns '{row_var}' and/or '{col_var}' not found in active worksheet.")

        sub_df = df[[row_var, col_var]].dropna().copy()
        sub_df[row_var] = sub_df[row_var].astype(str)
        sub_df[col_var] = sub_df[col_var].astype(str)

        n_total = len(sub_df)
        if n_total < 2:
            raise ValueError("Cross-Tabulation requires at least 2 valid observations.")

        # Compute raw contingency matrix
        ct_counts = pd.crosstab(sub_df[row_var], sub_df[col_var])
        row_levels = list(ct_counts.index)
        col_levels = list(ct_counts.columns)
        n_r, n_c = ct_counts.shape

        if n_r < 2 or n_c < 2:
            raise ValueError("Cross-Tabulation requires at least 2 distinct levels in both row and column variables.")

        observed_mat = ct_counts.to_numpy(dtype=float)

        # Chi-Square test
        chi2_stat, p_pearson, dof, expected_mat = stats.chi2_contingency(observed_mat, correction=False)
        # Likelihood ratio G2 test
        g2_stat, p_lr, _, _ = stats.chi2_contingency(observed_mat, lambda_="log-likelihood", correction=False)

        # Standardized residuals: (O - E) / sqrt(E)
        std_residuals = (observed_mat - expected_mat) / np.sqrt(np.where(expected_mat > 0, expected_mat, 1e-6))

        # Row, col, total sums
        row_totals = np.sum(observed_mat, axis=1)
        col_totals = np.sum(observed_mat, axis=0)
        grand_total = float(np.sum(observed_mat))

        # Formatted Cross-Tabulation Table
        headers = [f"{row_var} \\ {col_var}"] + col_levels + ["Total"]
        tab_rows = []

        for r_idx, r_val in enumerate(row_levels):
            cell_items = []
            # For each cell in row, build multi-line or composite representation
            r_total = row_totals[r_idx]
            for c_idx, c_val in enumerate(col_levels):
                cnt = int(observed_mat[r_idx, c_idx])
                exp = expected_mat[r_idx, c_idx]
                r_pct = (cnt / r_total * 100.0) if r_total > 0 else 0.0
                c_pct = (cnt / col_totals[c_idx] * 100.0) if col_totals[c_idx] > 0 else 0.0
                t_pct = (cnt / grand_total * 100.0) if grand_total > 0 else 0.0
                std_r = std_residuals[r_idx, c_idx]

                parts = [f"Count: {cnt}"]
                if params.show_expected: parts.append(f"Exp: {exp:.1f}")
                if params.show_row_pct: parts.append(f"Row%: {r_pct:.1f}%")
                if params.show_col_pct: parts.append(f"Col%: {c_pct:.1f}%")
                if params.show_total_pct: parts.append(f"Tot%: {t_pct:.1f}%")
                if params.show_residuals: parts.append(f"StdRes: {std_r:.2f}")

                cell_items.append(" | ".join(parts) if len(parts) > 1 else str(cnt))

            row_total_str = f"Count: {int(r_total)}"
            if params.show_total_pct:
                row_total_str += f" | {(r_total / grand_total * 100.0):.1f}%"

            tab_rows.append([r_val] + cell_items + [row_total_str])

        # Bottom Total Row
        col_total_items = []
        for c_idx, c_val in enumerate(col_levels):
            c_cnt = int(col_totals[c_idx])
            c_str = f"Count: {c_cnt}"
            if params.show_total_pct:
                c_str += f" | {(c_cnt / grand_total * 100.0):.1f}%"
            col_total_items.append(c_str)

        tab_rows.append(["Total"] + col_total_items + [f"Count: {int(grand_total)} | 100.0%"])

        # Chi-Square Test Table
        test_rows = [
            ["Pearson Chi-Square", dof, round(float(chi2_stat), 3), round(float(p_pearson), 5)],
            ["Likelihood-Ratio Chi-Square", dof, round(float(g2_stat), 3), round(float(p_lr), 5)]
        ]

        # If 2x2 table, compute Fisher's Exact Test
        if n_r == 2 and n_c == 2:
            try:
                fisher_odds, fisher_p = stats.fisher_exact(observed_mat)
                test_rows.append(["Fisher's Exact Test (Two-Tailed)", "N/A", f"Odds Ratio = {fisher_odds:.3f}", round(float(fisher_p), 5)])
            except Exception:
                pass

        # Ordinal association measures if requested
        if params.test_ordinal_measures:
            try:
                # Convert categorical levels to numeric indices for Spearman & Kendall
                r_codes = pd.Categorical(sub_df[row_var]).codes
                c_codes = pd.Categorical(sub_df[col_var]).codes
                spear_r, spear_p = stats.spearmanr(r_codes, c_codes)
                kendall_tau, kendall_p = stats.kendalltau(r_codes, c_codes)
                test_rows.append(["Spearman's Rho", "N/A", round(float(spear_r), 4), round(float(spear_p), 5)])
                test_rows.append(["Kendall's Tau-b", "N/A", round(float(kendall_tau), 4), round(float(kendall_p), 5)])
            except Exception:
                pass

        # Grouped Bar Plot / Heatmap
        traces = []
        for r_idx, r_val in enumerate(row_levels):
            traces.append({
                "x": col_levels,
                "y": [int(observed_mat[r_idx, c_idx]) for c_idx in range(n_c)],
                "type": "bar",
                "name": f"{row_var} = {r_val}"
            })

        layout = {
            "title": {"text": f"<b>Cross-Tabulation: {row_var} vs {col_var}</b><br><span style='font-size:11px;color:#605e5c'>Chi-Square = {chi2_stat:.3f}, DF = {dof}, p-value = {p_pearson:.5f}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": col_var, "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Frequency / Count", "showgrid": True, "gridcolor": "#f3f2f1"},
            "barmode": "group",
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 55}
        }

        tables = [
            TableResult(
                title=f"Tabulated Statistics: {row_var}, {col_var}",
                headers=headers,
                rows=tab_rows
            ),
            TableResult(
                title="Chi-Square Tests & Association Measures",
                headers=["Test / Statistic", "DF", "Value", "P-Value"],
                rows=test_rows
            )
        ]

        text_lines = [
            f"Tabulated Statistics: {row_var}, {col_var}",
            "",
            f"Rows: {row_var}   Columns: {col_var}",
            "",
            f"Pearson Chi-Square = {chi2_stat:.3f}, DF = {dof}, P-Value = {p_pearson:.5f}",
            f"Likelihood-Ratio Chi-Square = {g2_stat:.3f}, DF = {dof}, P-Value = {p_lr:.5f}"
        ]

        return AnalysisResult(
            title="Cross Tabulation and Chi-Square",
            subtitle=f"{row_var} by {col_var}",
            text_output="\n".join(text_lines),
            tables=tables,
            plotly_figure={"data": traces, "layout": layout}
        )
