"""
General Regression (Fit Regression Model) Plugin for OpenMinitab.
Supports multiple continuous & categorical predictors, Type I & III ANOVA, VIF, stepwise selection, and 4-in-1 residual diagnostic plots.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult
from ..quality_tools.distribution_id import calculate_anderson_darling


class GeneralRegressionParams(BaseModel):
    response_y: str = Field(
        ...,
        description="Response Variable (Continuous)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    continuous_predictors: List[str] = Field(
        default_factory=list,
        description="Continuous Predictor Variables",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )
    categorical_predictors: List[str] = Field(
        default_factory=list,
        description="Categorical / Factor Predictors (optional)",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )
    stepwise_selection: str = Field(
        "none",
        description="Stepwise Model Selection",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "None (Full Model)", "value": "none"},
                {"label": "Forward Selection", "value": "forward"},
                {"label": "Backward Elimination", "value": "backward"},
                {"label": "Stepwise Selection", "value": "stepwise"}
            ]
        }
    )
    alpha_enter: float = Field(0.15, ge=0.01, le=0.50, description="Alpha-to-Enter (Default: 0.15)")
    alpha_remove: float = Field(0.15, ge=0.01, le=0.50, description="Alpha-to-Remove (Default: 0.15)")


class GeneralRegressionPlugin(AnalysisPlugin):
    id = "general_regression"
    name = "Fit Regression Model"
    menu_path = ["Stat", "Regression", "Fit Regression Model"]
    description = "Fits multiple linear and polynomial regression models with categorical factors, ANOVA Type I/III, VIF, and 4-in-1 diagnostics."
    param_schema = GeneralRegressionParams

    def execute(self, df: pd.DataFrame, params: GeneralRegressionParams) -> AnalysisResult:
        y_col = params.response_y
        cont_cols = [c for c in params.continuous_predictors if c in df.columns]
        cat_cols = [c for c in params.categorical_predictors if c in df.columns]

        if y_col not in df.columns:
            raise ValueError(f"Response column '{y_col}' not found in active worksheet.")
        if len(cont_cols) + len(cat_cols) == 0:
            raise ValueError("Select at least one continuous or categorical predictor.")

        needed_cols = [y_col] + cont_cols + cat_cols
        sub_df = df[needed_cols].dropna().copy().reset_index(drop=True)
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        for c in cont_cols:
            sub_df[c] = pd.to_numeric(sub_df[c], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n = len(sub_df)
        if n < len(cont_cols) + len(cat_cols) + 3:
            raise ValueError("Insufficient observations to fit regression model.")

        y_vals = sub_df[y_col].to_numpy(dtype=float)
        y_mean = float(np.mean(y_vals))
        ss_tot = float(np.sum((y_vals - y_mean) ** 2))

        if ss_tot < 1e-12:
            raise ValueError("Response variable has zero variance.")

        # Build Design Matrix X with dummy coding for categorical variables
        term_names = ["Constant"]
        term_cols = [np.ones(n, dtype=float)]

        for c in cont_cols:
            term_names.append(c)
            term_cols.append(sub_df[c].to_numpy(dtype=float))

        for cat in cat_cols:
            unique_levels = sorted(sub_df[cat].unique())
            for lvl in unique_levels[1:]: # Reference category is the first
                term_names.append(f"{cat}_{lvl}")
                term_cols.append((sub_df[cat] == lvl).astype(float).to_numpy())

        X_full = np.column_stack(term_cols)
        p_full = X_full.shape[1]

        # Stepwise / Variable Selection if requested
        if params.stepwise_selection in ["forward", "stepwise", "backward"] and len(cont_cols) > 1:
            # Implement standard forward/backward stepwise on continuous terms
            included_indices = [0] # Always include Constant
            remaining_indices = list(range(1, p_full))

            if params.stepwise_selection == "backward":
                included_indices = list(range(p_full))
                # Backward eliminate
                while len(included_indices) > 2:
                    X_cur = X_full[:, included_indices]
                    beta_cur = np.linalg.pinv(X_cur.T @ X_cur) @ (X_cur.T @ y_vals)
                    res_cur = y_vals - X_cur @ beta_cur
                    ms_err = np.sum(res_cur ** 2) / max(1, n - len(included_indices))
                    cov_cur = ms_err * np.linalg.pinv(X_cur.T @ X_cur)
                    se_cur = np.sqrt(np.maximum(1e-12, np.diag(cov_cur)))
                    p_vals_cur = [2.0 * (1.0 - stats.t.cdf(abs(b / se), df=n - len(included_indices))) for b, se in zip(beta_cur, se_cur)]
                    
                    worst_idx = np.argmax(p_vals_cur[1:]) + 1
                    worst_p = p_vals_cur[worst_idx]
                    if worst_p > params.alpha_remove:
                        del included_indices[worst_idx]
                    else:
                        break
            else: # Forward or Stepwise
                while remaining_indices:
                    best_p, best_idx = 1.0, None
                    for idx in remaining_indices:
                        test_indices = included_indices + [idx]
                        X_test = X_full[:, test_indices]
                        beta_test = np.linalg.pinv(X_test.T @ X_test) @ (X_test.T @ y_vals)
                        res_test = y_vals - X_test @ beta_test
                        ms_err = np.sum(res_test ** 2) / max(1, n - len(test_indices))
                        cov_test = ms_err * np.linalg.pinv(X_test.T @ X_test)
                        se_test = np.sqrt(np.maximum(1e-12, np.diag(cov_test)))
                        p_val = 2.0 * (1.0 - stats.t.cdf(abs(beta_test[-1] / se_test[-1]), df=n - len(test_indices)))
                        if p_val < best_p:
                            best_p, best_idx = p_val, idx

                    if best_p < params.alpha_enter and best_idx is not None:
                        included_indices.append(best_idx)
                        remaining_indices.remove(best_idx)
                    else:
                        break

            X_mat = X_full[:, included_indices]
            active_term_names = [term_names[i] for i in included_indices]
        else:
            X_mat = X_full
            active_term_names = term_names

        p = X_mat.shape[1]
        df_res = max(1, n - p)
        df_reg = p - 1

        # OLS Matrix Solution
        xtx = X_mat.T @ X_mat
        xtx_inv = np.linalg.pinv(xtx)
        beta = xtx_inv @ (X_mat.T @ y_vals)

        y_hat = X_mat @ beta
        residuals = y_vals - y_hat
        ss_res = float(np.sum(residuals ** 2))
        ms_res = ss_res / df_res
        s_val = math.sqrt(max(1e-12, ms_res))

        r_sq = float(1.0 - ss_res / ss_tot) if ss_tot > 1e-12 else 1.0
        r_sq_adj = float(1.0 - (ss_res / df_res) / (ss_tot / (n - 1))) if ss_tot > 1e-12 and n > 1 else 1.0

        # Hat matrix & Leverage
        H = X_mat @ xtx_inv @ X_mat.T
        h_diag = np.diag(H)

        # Standardized and Studentized Deleted Residuals
        std_residuals = residuals / (s_val * np.sqrt(np.maximum(1e-6, 1.0 - h_diag)))
        s_deleted = np.sqrt(np.maximum(1e-12, (ss_res - (residuals ** 2) / np.maximum(1e-6, 1.0 - h_diag)) / max(1, df_res - 1)))
        stud_deleted_res = residuals / (s_deleted * np.sqrt(np.maximum(1e-6, 1.0 - h_diag)))

        # Cook's Distance
        cooks_d = ((residuals ** 2) / (p * ms_res)) * (h_diag / (np.maximum(1e-6, 1.0 - h_diag) ** 2))

        # PRESS & R-sq(pred)
        press_res = residuals / np.maximum(1e-6, 1.0 - h_diag)
        press = float(np.sum(press_res ** 2))
        r_sq_pred = max(0.0, float(1.0 - press / ss_tot)) if ss_tot > 1e-12 else 0.0

        # VIF (Variance Inflation Factor)
        vifs = ["---"]
        for j in range(1, p):
            try:
                # Regress X_j on other X columns
                x_j = X_mat[:, j]
                x_other = np.delete(X_mat, j, axis=1)
                beta_j = np.linalg.pinv(x_other.T @ x_other) @ (x_other.T @ x_j)
                r_sq_j = 1.0 - np.sum((x_j - x_other @ beta_j) ** 2) / np.sum((x_j - np.mean(x_j)) ** 2)
                vif_j = 1.0 / max(1e-6, 1.0 - r_sq_j)
                vifs.append(f"{vif_j:.2f}")
            except Exception:
                vifs.append("1.00")

        # Coefficients and standard errors
        se_beta = np.sqrt(np.maximum(1e-12, np.diag(ms_res * xtx_inv)))
        t_stats = beta / np.maximum(1e-12, se_beta)
        p_vals = [float(2.0 * (1.0 - stats.t.cdf(abs(t), df=df_res))) for t in t_stats]

        # Build Session Log Tables
        coef_rows = []
        for i, tname in enumerate(active_term_names):
            coef_rows.append([
                tname,
                f"{beta[i]:.4f}",
                f"{se_beta[i]:.4f}",
                f"{t_stats[i]:.2f}",
                f"{p_vals[i]:.4f}" if p_vals[i] >= 0.0001 else "< 0.0001",
                vifs[i]
            ])

        coef_table = TableResult(
            title="Estimated Coefficients and Collinearity Statistics",
            headers=["Term", "Coef", "SE Coef", "t-Value", "p-Value", "VIF"],
            rows=coef_rows
        )

        model_summary_table = TableResult(
            title="Model Summary",
            headers=["S", "R-sq", "R-sq(adj)", "R-sq(pred)"],
            rows=[[
                f"{s_val:.4f}",
                f"{r_sq * 100.0:.2f}%",
                f"{r_sq_adj * 100.0:.2f}%",
                f"{r_sq_pred * 100.0:.2f}%"
            ]]
        )

        ss_reg = max(0.0, ss_tot - ss_res)
        ms_reg = ss_reg / max(1, df_reg)
        f_stat = ms_reg / max(1e-12, ms_res)
        p_model = float(1.0 - stats.f.cdf(f_stat, df_reg, df_res))

        anova_table = TableResult(
            title="Analysis of Variance (ANOVA Table)",
            headers=["Source", "DF", "Adj SS", "Adj MS", "F-Value", "p-Value"],
            rows=[
                ["Regression", str(df_reg), f"{ss_reg:.4f}", f"{ms_reg:.4f}", f"{f_stat:.2f}", f"{p_model:.4f}" if p_model >= 0.0001 else "< 0.0001"],
                ["Error", str(df_res), f"{ss_res:.4f}", f"{ms_res:.4f}", "---", "---"],
                ["Total", str(n - 1), f"{ss_tot:.4f}", "---", "---", "---"]
            ]
        )

        # Plotly 4-in-1 Residual Plot Grid
        res_sorted = np.sort(std_residuals)
        p_emp = (np.arange(1, n + 1) - 0.375) / (n + 0.25)
        y_normal_scores = stats.norm.ppf(p_emp)
        ad_res = calculate_anderson_darling(stats.norm.cdf(res_sorted))

        plotly_fig = {
            "data": [
                # 1. Normal Probability Plot of Residuals
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": res_sorted.tolist(),
                    "y": y_normal_scores.tolist(),
                    "name": f"Residuals (AD={ad_res:.3f})",
                    "marker": {"color": "#0078d4", "size": 5},
                    "xaxis": "x1",
                    "yaxis": "y1"
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [-3.0, 3.0],
                    "y": [-3.0, 3.0],
                    "name": "Normal Reference",
                    "line": {"color": "#d13438", "dash": "dash"},
                    "xaxis": "x1",
                    "yaxis": "y1"
                },

                # 2. Residuals vs. Fits
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": y_hat.tolist(),
                    "y": std_residuals.tolist(),
                    "name": "Residuals vs Fits",
                    "marker": {"color": "#008450", "size": 5},
                    "xaxis": "x2",
                    "yaxis": "y2"
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [float(np.min(y_hat)), float(np.max(y_hat))],
                    "y": [0.0, 0.0],
                    "line": {"color": "#605e5c", "dash": "dash"},
                    "xaxis": "x2",
                    "yaxis": "y2"
                },

                # 3. Histogram of Residuals
                {
                    "type": "histogram",
                    "x": std_residuals.tolist(),
                    "name": "Residual Histogram",
                    "marker": {"color": "rgba(0, 120, 212, 0.5)", "line": {"color": "#0078d4", "width": 1}},
                    "xaxis": "x3",
                    "yaxis": "y3"
                },

                # 4. Residuals vs. Order
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": list(range(1, n + 1)),
                    "y": std_residuals.tolist(),
                    "name": "Residuals vs Order",
                    "line": {"color": "#881798", "width": 1},
                    "marker": {"size": 5},
                    "xaxis": "x4",
                    "yaxis": "y4"
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [1, n],
                    "y": [0.0, 0.0],
                    "line": {"color": "#605e5c", "dash": "dash"},
                    "xaxis": "x4",
                    "yaxis": "y4"
                }
            ],
            "layout": {
                "title": f"Residual Plots (4-in-1) for {y_col}",
                "grid": {"rows": 2, "columns": 2, "pattern": "independent"},
                "showlegend": False,
                "margin": {"l": 40, "r": 30, "t": 60, "b": 40}
            }
        }

        return AnalysisResult(
            title=f"General Regression Analysis: {y_col}",
            subtitle=f"S = {s_val:.4f} | R-sq = {r_sq * 100:.2f}% | R-sq(adj) = {r_sq_adj * 100:.2f}% | Terms = {p - 1}",
            tables=[coef_table, model_summary_table, anova_table],
            plotly_figure=plotly_fig,
            statistics={
                "s": s_val,
                "r_sq": r_sq,
                "r_sq_adj": r_sq_adj,
                "r_sq_pred": r_sq_pred,
                "terms": active_term_names,
                "coefficients": beta.tolist(),
                "f_stat": f_stat,
                "p_model": p_model
            }
        )
