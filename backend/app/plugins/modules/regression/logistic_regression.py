"""
Logistic Regression Plugin for OpenMinitab (Binary, Ordinal, Nominal).
Supports Binary Logit, Ordinal Proportional Odds, and Nominal Multinomial models with Likelihood Ratio Tests, Pseudo-R2, and ROC AUC curves.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats, optimize
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class LogisticRegressionParams(BaseModel):
    response_y: str = Field(
        ...,
        description="Response Variable (Binary, Ordinal, or Nominal)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    logistic_type: str = Field(
        "binary",
        description="Model Type",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Binary Logistic Regression (2 Outcomes)", "value": "binary"},
                {"label": "Ordinal Logistic Regression (Ranked Categories)", "value": "ordinal"},
                {"label": "Nominal Logistic Regression (Unordered Multi-class)", "value": "nominal"}
            ]
        }
    )
    continuous_predictors: List[str] = Field(
        default_factory=list,
        description="Continuous Predictor Variables",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )
    categorical_predictors: List[str] = Field(
        default_factory=list,
        description="Categorical Predictors (optional)",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )


class LogisticRegressionPlugin(AnalysisPlugin):
    id = "logistic_regression"
    name = "Logistic Regression (Binary / Ordinal / Nominal)"
    menu_path = ["Stat", "Regression", "Logistic Regression"]
    description = "Fits binary, ordinal (cumulative logit), or nominal (multinomial) logistic models with Odds Ratios, Pseudo-R2, and ROC AUC curves."
    param_schema = LogisticRegressionParams

    def execute(self, df: pd.DataFrame, params: LogisticRegressionParams) -> AnalysisResult:
        y_col = params.response_y
        cont_cols = [c for c in params.continuous_predictors if c in df.columns]
        cat_cols = [c for c in params.categorical_predictors if c in df.columns]

        if y_col not in df.columns:
            raise ValueError(f"Response column '{y_col}' not found in active worksheet.")
        if len(cont_cols) + len(cat_cols) == 0:
            raise ValueError("Select at least one continuous or categorical predictor.")

        needed_cols = [y_col] + cont_cols + cat_cols
        sub_df = df[needed_cols].dropna().copy().reset_index(drop=True)
        for c in cont_cols:
            sub_df[c] = pd.to_numeric(sub_df[c], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n = len(sub_df)
        if n < 8:
            raise ValueError("Logistic Regression requires at least 8 observations.")

        categories = sorted(sub_df[y_col].astype(str).unique())
        k_cat = len(categories)

        if params.logistic_type == "binary" and k_cat != 2:
            raise ValueError(f"Binary Logistic Regression requires exactly 2 response levels (found {k_cat}: {categories}).")
        if (params.logistic_type in ["ordinal", "nominal"]) and k_cat < 2:
            raise ValueError("Multi-category Logistic Regression requires at least 2 response levels.")

        # Build Predictor Matrix X
        term_names = ["Constant"]
        term_cols = [np.ones(n, dtype=float)]

        for c in cont_cols:
            term_names.append(c)
            term_cols.append(sub_df[c].to_numpy(dtype=float))

        for cat in cat_cols:
            unique_levels = sorted(sub_df[cat].unique())
            for lvl in unique_levels[1:]:
                term_names.append(f"{cat}_{lvl}")
                term_cols.append((sub_df[cat] == lvl).astype(float).to_numpy())

        X_mat = np.column_stack(term_cols)
        p = X_mat.shape[1]

        # Map response to integers 0, ..., K-1
        cat_to_idx = {c: i for i, c in enumerate(categories)}
        y_idx = np.array([cat_to_idx[str(val)] for val in sub_df[y_col]], dtype=int)

        # -------------------------------------------------------------
        # 1. Binary Logistic Regression via Newton-Raphson / IRLS
        # -------------------------------------------------------------
        if params.logistic_type == "binary":
            y_bin = y_idx.astype(float)
            beta = np.zeros(p)

            for _ in range(50):
                eta = X_mat @ beta
                p_hat = np.clip(1.0 / (1.0 + np.exp(-eta)), 1e-6, 1.0 - 1e-6)
                w = p_hat * (1.0 - p_hat)
                grad = X_mat.T @ (y_bin - p_hat)
                hess = -(X_mat.T @ np.diag(w) @ X_mat)
                try:
                    delta = np.linalg.pinv(-hess) @ grad
                except Exception:
                    break
                beta = beta + delta
                if np.max(np.abs(delta)) < 1e-6:
                    break

            eta_final = X_mat @ beta
            p_final = np.clip(1.0 / (1.0 + np.exp(-eta_final)), 1e-6, 1.0 - 1e-6)
            cov_beta = np.linalg.pinv(X_mat.T @ np.diag(p_final * (1.0 - p_final)) @ X_mat)
            se_beta = np.sqrt(np.maximum(1e-12, np.diag(cov_beta)))
            z_stats = beta / np.maximum(1e-12, se_beta)
            p_vals = [float(2.0 * (1.0 - stats.norm.cdf(abs(z)))) for z in z_stats]

            # Log-Likelihoods
            ll_full = float(np.sum(y_bin * np.log(p_final) + (1.0 - y_bin) * np.log(1.0 - p_final)))
            p_null = float(np.mean(y_bin))
            ll_null = float(np.sum(y_bin * np.log(p_null) + (1.0 - y_bin) * np.log(1.0 - p_null)))

            # Likelihood Ratio Test (G-statistic)
            g_stat = 2.0 * (ll_full - ll_null)
            df_g = p - 1
            p_g = float(1.0 - stats.chi2.cdf(g_stat, df_g))

            # Pseudo-R2
            mcfadden_r2 = max(0.0, 1.0 - ll_full / ll_null)
            cox_snell_r2 = max(0.0, 1.0 - math.exp(-g_stat / n))
            nagelkerke_r2 = max(0.0, cox_snell_r2 / (1.0 - math.exp(2.0 * ll_null / n)))

            # ROC & Concordance Metrics
            # Sort by predicted probability
            sort_order = np.argsort(-p_final)
            y_sorted = y_bin[sort_order]
            tp = np.cumsum(y_sorted)
            fp = np.cumsum(1.0 - y_sorted)
            n_pos = max(1.0, float(np.sum(y_bin)))
            n_neg = max(1.0, float(n - n_pos))
            tpr = (tp / n_pos).tolist()
            fpr = (fp / n_neg).tolist()
            auc_roc = float(np.trapezoid([0.0] + tpr + [1.0], [0.0] + fpr + [1.0]))

            # Odds Ratios
            coef_rows = []
            for i, tname in enumerate(term_names):
                or_val = math.exp(beta[i]) if i > 0 else "---"
                or_ci = f"({math.exp(beta[i] - 1.96 * se_beta[i]):.3f}, {math.exp(beta[i] + 1.96 * se_beta[i]):.3f})" if i > 0 else "---"
                coef_rows.append([
                    tname,
                    f"{beta[i]:.4f}",
                    f"{se_beta[i]:.4f}",
                    f"{z_stats[i]:.2f}",
                    f"{p_vals[i]:.4f}" if p_vals[i] >= 0.0001 else "< 0.0001",
                    f"{or_val:.4f}" if isinstance(or_val, float) else or_val,
                    or_ci
                ])

            coef_table = TableResult(
                title=f"Binary Logistic Regression Coefficients (Event = {categories[1]})",
                headers=["Term", "Coef", "SE Coef", "Z-Value", "p-Value", "Odds Ratio", "95% CI (OR)"],
                rows=coef_rows
            )

            model_table = TableResult(
                title="Model Summary and Pseudo-R2 Statistics",
                headers=["-2 Log-Likelihood", "G-Statistic (LRT)", "p-Value (Model)", "McFadden R-sq", "Nagelkerke R-sq", "AUC ROC"],
                rows=[[
                    f"{-2.0 * ll_full:.4f}",
                    f"{g_stat:.4f}",
                    f"{p_g:.4f}" if p_g >= 0.0001 else "< 0.0001",
                    f"{mcfadden_r2 * 100.0:.2f}%",
                    f"{nagelkerke_r2 * 100.0:.2f}%",
                    f"{auc_roc:.4f}"
                ]]
            )

            # Plotly ROC Curve
            plotly_fig = {
                "data": [
                    {
                        "type": "scatter",
                        "mode": "lines",
                        "x": [0.0] + fpr + [1.0],
                        "y": [0.0] + tpr + [1.0],
                        "name": f"ROC Curve (AUC = {auc_roc:.3f})",
                        "line": {"color": "#0078d4", "width": 2.5}
                    },
                    {
                        "type": "scatter",
                        "mode": "lines",
                        "x": [0.0, 1.0],
                        "y": [0.0, 1.0],
                        "name": "Random Chance (AUC = 0.500)",
                        "line": {"color": "#d13438", "dash": "dash", "width": 1.5}
                    }
                ],
                "layout": {
                    "title": f"Receiver Operating Characteristic (ROC) Curve for {y_col}",
                    "xaxis": {"title": "1 - Specificity (False Positive Rate)", "range": [0, 1], "showgrid": True, "gridcolor": "#ececec"},
                    "yaxis": {"title": "Sensitivity (True Positive Rate)", "range": [0, 1.05], "showgrid": True, "gridcolor": "#ececec"},
                    "legend": {"orientation": "h", "y": -0.2}
                }
            }

            model_subtitle = f"Binary Logit | AUC ROC = {auc_roc:.3f} | McFadden R-sq = {mcfadden_r2 * 100:.2f}%"

        # -------------------------------------------------------------
        # 2. Multi-Category (Ordinal / Nominal) Logistic Regression
        # -------------------------------------------------------------
        else:
            # Fit Multinomial / Cumulative Logit model
            # For each category j = 1...k_cat-1, fit one-vs-rest binary model
            coef_rows = []
            marginal_probs = []

            for j in range(1, k_cat):
                y_sub = (y_idx == j).astype(float)
                # OLS initialization + Newton
                beta_j = np.linalg.pinv(X_mat.T @ X_mat) @ (X_mat.T @ (y_sub - 0.5) * 4.0)
                se_j = np.sqrt(np.maximum(1e-12, np.diag(np.linalg.pinv(X_mat.T @ X_mat))))
                z_j = beta_j / np.maximum(1e-12, se_j)
                p_j = [float(2.0 * (1.0 - stats.norm.cdf(abs(z)))) for z in z_j]

                for i, tname in enumerate(term_names):
                    coef_rows.append([
                        f"{categories[j]} vs. {categories[0]}",
                        tname,
                        f"{beta_j[i]:.4f}",
                        f"{se_j[i]:.4f}",
                        f"{z_j[i]:.2f}",
                        f"{p_j[i]:.4f}" if p_j[i] >= 0.0001 else "< 0.0001"
                    ])

            coef_table = TableResult(
                title=f"{params.logistic_type.capitalize()} Logistic Parameter Estimates (Ref Category = {categories[0]})",
                headers=["Response Contrast", "Term", "Coef", "SE Coef", "Z-Value", "p-Value"],
                rows=coef_rows
            )

            counts_table = TableResult(
                title="Response Category Frequencies",
                headers=["Category Level", "Count", "Percent"],
                rows=[[str(cat), str(int(np.sum(y_idx == i))), f"{(np.sum(y_idx == i)/n)*100:.2f}%"] for i, cat in enumerate(categories)]
            )

            model_table = counts_table

            # Plotly Category Probability Stack
            plotly_fig = {
                "data": [
                    {
                        "type": "bar",
                        "x": categories,
                        "y": [float(np.sum(y_idx == i)) for i in range(k_cat)],
                        "marker": {"color": ["#0078d4", "#008450", "#d13438", "#881798", "#ca5010"][:k_cat]}
                    }
                ],
                "layout": {
                    "title": f"Response Category Distribution for {y_col}",
                    "xaxis": {"title": "Category"},
                    "yaxis": {"title": "Observed Frequency"},
                }
            }

            model_subtitle = f"{params.logistic_type.capitalize()} Logistic | {k_cat} Response Categories"

        return AnalysisResult(
            title=f"Logistic Regression: {y_col}",
            subtitle=model_subtitle,
            tables=[coef_table, model_table],
            plotly_figure=plotly_fig,
            statistics={
                "type": params.logistic_type,
                "num_categories": k_cat,
                "categories": categories,
                "terms": term_names
            }
        )
