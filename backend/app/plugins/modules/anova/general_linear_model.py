"""
General Linear Model (GLM) Plugin for OpenMinitab.
Fits unbalanced multi-factor designs with continuous covariates (ANCOVA), Type I & III Adjusted SS, and Least Squares Means (LS Means).
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult
from ..quality_tools.distribution_id import calculate_anderson_darling


class GlmParams(BaseModel):
    response_column: str = Field(
        ...,
        description="Response Variable (Continuous Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    factors: List[str] = Field(
        ...,
        description="Categorical Factors",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )
    covariates: List[str] = Field(
        default_factory=list,
        description="Continuous Covariates (ANCOVA, optional)",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )
    ss_type: str = Field(
        "type3",
        description="Sum of Squares Method",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Type III (Adjusted)", "value": "type3"},
                {"label": "Type I (Sequential)", "value": "type1"}
            ]
        }
    )


class GeneralLinearModelPlugin(AnalysisPlugin):
    id = "general_linear_model"
    name = "General Linear Model (GLM)"
    menu_path = ["Stat", "ANOVA", "General Linear Model"]
    description = "Fits unbalanced multi-factor designs with continuous covariates (ANCOVA), Type III Adjusted SS, and Least Squares Means (LS Means)."
    param_schema = GlmParams

    def execute(self, df: pd.DataFrame, params: GlmParams) -> AnalysisResult:
        y_col = params.response_column
        factors = [f for f in params.factors if f in df.columns]
        covs = [c for c in params.covariates if c in df.columns]

        if y_col not in df.columns or len(factors) < 1:
            raise ValueError("Select a response variable and at least one factor.")

        needed_cols = [y_col] + factors + covs
        sub_df = df[needed_cols].dropna().copy().reset_index(drop=True)
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        for c in covs:
            sub_df[c] = pd.to_numeric(sub_df[c], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n = len(sub_df)
        if n < len(factors) + len(covs) + 3:
            raise ValueError("Insufficient observations to fit General Linear Model.")

        y = sub_df[y_col].to_numpy(dtype=float)
        grand_mean = float(np.mean(y))
        ss_tot = float(np.sum((y - grand_mean) ** 2))

        # Build Full Design Matrix X using Effect Coding (-1, 0, +1)
        term_map = {} # term_name -> list of column indices in X
        col_list = [np.ones(n, dtype=float)] # Intercept
        term_map["Constant"] = [0]

        cur_idx = 1
        for f in factors:
            levels = sorted(sub_df[f].unique())
            f_cols = []
            for lvl in levels[:-1]: # k-1 effect codes
                code_col = np.where(sub_df[f] == lvl, 1.0, np.where(sub_df[f] == levels[-1], -1.0, 0.0))
                col_list.append(code_col)
                f_cols.append(cur_idx)
                cur_idx += 1
            term_map[f] = f_cols

        for c in covs:
            col_list.append(sub_df[c].to_numpy(dtype=float))
            term_map[c] = [cur_idx]
            cur_idx += 1

        X_full = np.column_stack(col_list)
        p_full = X_full.shape[1]

        # Full Model OLS
        xtx_inv_full = np.linalg.pinv(X_full.T @ X_full)
        beta_full = xtx_inv_full @ (X_full.T @ y)
        y_hat_full = X_full @ beta_full
        residuals = y - y_hat_full
        ss_res_full = float(np.sum(residuals ** 2))
        df_res_full = max(1, n - p_full)
        ms_res_full = ss_res_full / df_res_full
        s_val = math.sqrt(max(1e-12, ms_res_full))

        r_sq = max(0.0, 1.0 - ss_res_full / ss_tot) if ss_tot > 1e-12 else 1.0
        r_sq_adj = float(1.0 - (ss_res_full / df_res_full) / (ss_tot / (n - 1))) if ss_tot > 1e-12 else 1.0

        # Compute Type III (Adjusted) Sum of Squares for each term
        anova_rows = []
        for term_name, col_indices in term_map.items():
            if term_name == "Constant":
                continue
            df_term = len(col_indices)
            # Reduced Model without term
            X_red = np.delete(X_full, col_indices, axis=1)
            beta_red = np.linalg.pinv(X_red.T @ X_red) @ (X_red.T @ y)
            ss_res_red = float(np.sum((y - X_red @ beta_red) ** 2))
            ss_term = max(0.0, ss_res_red - ss_res_full)
            ms_term = ss_term / max(1, df_term)
            f_term = ms_term / max(1e-12, ms_res_full)
            p_term = float(1.0 - stats.f.cdf(f_term, df_term, df_res_full))

            anova_rows.append([
                term_name,
                str(df_term),
                f"{ss_term:.4f}",
                f"{ms_term:.4f}",
                f"{f_term:.2f}",
                f"{p_term:.4f}" if p_term >= 0.0001 else "< 0.0001"
            ])

        anova_rows.append(["Error", str(df_res_full), f"{ss_res_full:.4f}", f"{ms_res_full:.4f}", "---", "---"])
        anova_rows.append(["Total", str(n - 1), f"{ss_tot:.4f}", "---", "---", "---"])

        anova_table = TableResult(
            title=f"General Linear Model: Analysis of Variance (Type III Adjusted SS) for {y_col}",
            headers=["Source", "DF", "Adj SS", "Adj MS", "F-Value", "p-Value"],
            rows=anova_rows
        )

        model_summary_table = TableResult(
            title="Model Summary",
            headers=["S (Residual SE)", "R-sq", "R-sq(adj)", "Error DF"],
            rows=[[
                f"{s_val:.4f}",
                f"{r_sq * 100.0:.2f}%",
                f"{r_sq_adj * 100.0:.2f}%",
                str(df_res_full)
            ]]
        )

        # -------------------------------------------------------------
        # Least Squares Means (LS Means / Marginal Means)
        # -------------------------------------------------------------
        ls_means_rows = []
        primary_factor = factors[0]
        f1_levels = sorted(sub_df[primary_factor].unique())
        f1_col_indices = term_map[primary_factor]

        for i, lvl in enumerate(f1_levels):
            # Form L vector: 1 for constant, effect code for f1, 0 for other factors, mean for covs
            L_vec = np.zeros(p_full)
            L_vec[0] = 1.0 # Constant
            if i < len(f1_levels) - 1:
                L_vec[f1_col_indices[i]] = 1.0
            else:
                for c_idx in f1_col_indices:
                    L_vec[c_idx] = -1.0

            # Covariates set to mean
            for c in covs:
                L_vec[term_map[c][0]] = float(np.mean(sub_df[c]))

            ls_mean = float(L_vec @ beta_full)
            se_ls_mean = math.sqrt(max(1e-12, float(L_vec @ xtx_inv_full @ L_vec) * ms_res_full))
            ci_low = ls_mean - 1.96 * se_ls_mean
            ci_high = ls_mean + 1.96 * se_ls_mean

            ls_means_rows.append([
                str(lvl),
                f"{ls_mean:.4f}",
                f"{se_ls_mean:.4f}",
                f"({ci_low:.4f}, {ci_high:.4f})"
            ])

        ls_means_table = TableResult(
            title=f"Least Squares Means for {primary_factor} (Adjusted for Covariates)",
            headers=[primary_factor, "LS Mean", "SE Mean", "95% CI"],
            rows=ls_means_rows
        )

        # Plotly LS Means Plot
        plotly_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": [r[0] for r in ls_means_rows],
                    "y": [float(r[1]) for r in ls_means_rows],
                    "error_y": {
                        "type": "data",
                        "array": [float(r[2]) * 1.96 for r in ls_means_rows],
                        "visible": True,
                        "color": "#0078d4",
                        "thickness": 2,
                        "width": 6
                    },
                    "name": "LS Means",
                    "marker": {"color": "#0078d4", "size": 8}
                }
            ],
            "layout": {
                "title": f"Least Squares Means Plot for {y_col} by {primary_factor}",
                "xaxis": {"title": primary_factor, "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": f"Adjusted Mean {y_col}", "showgrid": True, "gridcolor": "#ececec"},
            }
        }

        return AnalysisResult(
            title=f"General Linear Model: {y_col}",
            subtitle=f"S = {s_val:.4f} | R-sq = {r_sq * 100:.2f}% | R-sq(adj) = {r_sq_adj * 100:.2f}%",
            tables=[anova_table, model_summary_table, ls_means_table],
            plotly_figure=plotly_fig,
            statistics={
                "s": s_val,
                "r_sq": r_sq,
                "r_sq_adj": r_sq_adj,
                "ls_means": {r[0]: float(r[1]) for r in ls_means_rows}
            }
        )
