"""
Attribute Agreement Analysis Plugin for OpenMinitab Quality Tools.
Assesses repeatability, reproducibility, accuracy, and Cohen's / Fleiss' Kappa statistics for categorical/nominal inspection data.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class AttributeAgreementParams(BaseModel):
    attribute_column: str = Field(
        ...,
        description="Assessment / Rating Variable (Attribute)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    sample_column: str = Field(
        ...,
        description="Sample / Part Variable",
        json_schema_extra={"ui_type": "column_picker"}
    )
    appraiser_column: str = Field(
        ...,
        description="Appraiser / Inspector Variable",
        json_schema_extra={"ui_type": "column_picker"}
    )
    standard_reference_column: Optional[str] = Field(
        None,
        description="Known Standard / Reference Variable (optional)",
        json_schema_extra={"ui_type": "column_picker"}
    )


class AttributeAgreementPlugin(AnalysisPlugin):
    id = "attribute_agreement"
    name = "Attribute Agreement Analysis"
    menu_path = ["Stat", "Quality Tools", "Attribute Agreement Analysis"]
    description = "Evaluates the consistency and accuracy of multiple appraisers performing attribute / pass-fail inspections."
    param_schema = AttributeAgreementParams

    def execute(self, df: pd.DataFrame, params: AttributeAgreementParams) -> AnalysisResult:
        att_col, samp_col, app_col = params.attribute_column, params.sample_column, params.appraiser_column
        std_col = params.standard_reference_column

        needed_cols = [att_col, samp_col, app_col]
        if std_col and std_col in df.columns:
            needed_cols.append(std_col)

        for col in [att_col, samp_col, app_col]:
            if col not in df.columns:
                raise ValueError(f"Required column '{col}' not found in active worksheet.")

        sub_df = df[needed_cols].dropna().copy().reset_index(drop=True)
        if len(sub_df) < 4:
            raise ValueError("Attribute Agreement Analysis requires at least 4 inspection records.")

        appraisers = list(sub_df[app_col].unique())
        samples = list(sub_df[samp_col].unique())
        has_std = bool(std_col and std_col in sub_df.columns)

        # 1. Within-Appraiser Agreement (% Repeatability)
        within_rows = []
        within_pct_list = []
        for app in appraisers:
            app_data = sub_df[sub_df[app_col] == app]
            n_samples_inspected = len(app_data[samp_col].unique())
            agreed_count = 0

            for s in app_data[samp_col].unique():
                ratings = app_data[app_data[samp_col] == s][att_col].tolist()
                if len(ratings) > 1 and len(set(ratings)) == 1:
                    agreed_count += 1
                elif len(ratings) == 1:
                    agreed_count += 1

            pct_agree = (agreed_count / max(1, n_samples_inspected)) * 100.0
            within_pct_list.append(pct_agree)
            
            # Wilson Score 95% CI
            z = 1.96
            n = n_samples_inspected
            p = agreed_count / n
            ci_low = max(0.0, (p + (z**2)/(2*n) - z * math.sqrt((p*(1-p) + (z**2)/(4*n))/n)) / (1 + (z**2)/n)) * 100.0
            ci_high = min(100.0, (p + (z**2)/(2*n) + z * math.sqrt((p*(1-p) + (z**2)/(4*n))/n)) / (1 + (z**2)/n)) * 100.0

            within_rows.append([
                str(app),
                str(n_samples_inspected),
                str(agreed_count),
                f"{pct_agree:.2f}%",
                f"({ci_low:.2f}%, {ci_high:.2f}%)"
            ])

        within_table = TableResult(
            title="Within Appraisers Assessment Agreement (% Repeatability)",
            headers=["Appraiser", "# Inspected", "# Matched", "Percent Agreement", "95% CI"],
            rows=within_rows
        )

        # 2. Each Appraiser vs Standard (Accuracy)
        vs_std_rows = []
        if has_std:
            for app in appraisers:
                app_data = sub_df[sub_df[app_col] == app]
                n_samples_inspected = len(app_data[samp_col].unique())
                correct_count = 0

                for s in app_data[samp_col].unique():
                    ratings = app_data[app_data[samp_col] == s][att_col].tolist()
                    true_vals = app_data[app_data[samp_col] == s][std_col].tolist()
                    if len(ratings) > 0 and len(true_vals) > 0:
                        if all(r == true_vals[0] for r in ratings):
                            correct_count += 1

                pct_correct = (correct_count / max(1, n_samples_inspected)) * 100.0
                vs_std_rows.append([
                    str(app),
                    str(n_samples_inspected),
                    str(correct_count),
                    f"{pct_correct:.2f}%"
                ])

        vs_std_table = TableResult(
            title="Each Appraiser vs Standard Assessment (% Accuracy)",
            headers=["Appraiser", "# Inspected", "# Matched Standard", "Percent Agreement"],
            rows=vs_std_rows if has_std else [["No Standard Reference Column Specified", "---", "---", "---"]]
        )

        # 3. Overall Fleiss' / Cohen's Kappa
        # Compute Fleiss Kappa across all ratings
        categories = list(sub_df[att_col].unique())
        k_cat = len(categories)
        cat_to_idx = {c: i for i, c in enumerate(categories)}

        matrix_n = []
        for s in samples:
            s_data = sub_df[sub_df[samp_col] == s]
            row_counts = [0] * k_cat
            for r in s_data[att_col]:
                if r in cat_to_idx:
                    row_counts[cat_to_idx[r]] += 1
            matrix_n.append(row_counts)

        mat = np.array(matrix_n, dtype=float)
        n_raters_per_item = np.sum(mat, axis=1)
        valid_items = mat[n_raters_per_item > 1]
        
        if len(valid_items) > 0:
            m = np.mean(n_raters_per_item[n_raters_per_item > 1])
            N_items = len(valid_items)
            p_j = np.sum(valid_items, axis=0) / (N_items * m)
            p_e = np.sum(p_j ** 2)
            P_i = (np.sum(valid_items ** 2, axis=1) - m) / (m * (m - 1))
            p_bar = np.mean(P_i)
            kappa = (p_bar - p_e) / (1.0 - p_e) if (1.0 - p_e) > 1e-12 else 1.0
            se_kappa = math.sqrt(2.0 * (1.0 - p_e)) / (math.sqrt(N_items * m * (m - 1)) * (1.0 - p_e)) if (1.0 - p_e) > 1e-12 else 0.05
            z_kappa = kappa / max(1e-12, se_kappa)
            p_val_kappa = float(2.0 * (1.0 - stats.norm.cdf(abs(z_kappa))))
        else:
            kappa, se_kappa, z_kappa, p_val_kappa = 1.0, 0.0, 0.0, 0.0

        kappa_table = TableResult(
            title="Fleiss' Multi-Rater Kappa Statistics",
            headers=["Response Category", "Kappa", "SE Kappa", "Z-Statistic", "p-Value"],
            rows=[
                ["Overall Multi-Rater Agreement", f"{kappa:.4f}", f"{se_kappa:.4f}", f"{z_kappa:.2f}", f"{p_val_kappa:.4f}" if p_val_kappa >= 0.0001 else "< 0.0001"]
            ]
        )

        # Plotly Agreement Dot/Bar Chart
        plotly_fig = {
            "data": [
                {
                    "type": "bar",
                    "x": [str(a) for a in appraisers],
                    "y": within_pct_list,
                    "name": "% Repeatability",
                    "marker": {"color": "#0078d4"}
                }
            ],
            "layout": {
                "title": f"Attribute Agreement Analysis Report for {att_col}",
                "xaxis": {"title": "Appraiser", "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": "Within-Appraiser Agreement (%)", "range": [0, 105], "ticksuffix": "%", "showgrid": True, "gridcolor": "#ececec"},
                "shapes": [
                    {"type": "line", "x0": -0.5, "y0": 90, "x1": len(appraisers) - 0.5, "y1": 90, "line": {"color": "#008450", "width": 2, "dash": "dash"}}
                ],
                "annotations": [
                    {"x": len(appraisers) - 1, "y": 92, "text": "Target: 90% Agreement", "showarrow": False, "font": {"color": "#008450", "size": 10}}
                ]
            }
        }

        return AnalysisResult(
            title=f"Attribute Agreement Analysis for {att_col}",
            subtitle=f"Overall Kappa = {kappa:.4f} | {len(appraisers)} Appraisers on {len(samples)} Samples",
            tables=[within_table, vs_std_table, kappa_table],
            plotly_figure=plotly_fig,
            statistics={
                "kappa": kappa,
                "se_kappa": se_kappa,
                "p_val_kappa": p_val_kappa,
                "num_appraisers": len(appraisers),
                "num_samples": len(samples)
            }
        )
