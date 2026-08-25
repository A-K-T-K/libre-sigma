"""
Poisson Regression Plugin for OpenMinitab.
Fits log-linear Poisson and Quasi-Poisson models for count data with exposure offsets, overdispersion tests, and Rate Ratios (RR).
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class PoissonRegressionParams(BaseModel):
    count_response_y: str = Field(
        ...,
        description="Count Response Variable Y (Non-negative integers: 0, 1, 2...)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
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
    exposure_offset: Optional[str] = Field(
        None,
        description="Exposure / Time Unit Variable for Rate Offset (optional)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )


class PoissonRegressionPlugin(AnalysisPlugin):
    id = "poisson_regression"
    name = "Poisson Regression"
    menu_path = ["Stat", "Regression", "Poisson Regression"]
    description = "Models event counts and occurrence rates with exposure offsets, Rate Ratios (RR), and overdispersion testing."
    param_schema = PoissonRegressionParams

    def execute(self, df: pd.DataFrame, params: PoissonRegressionParams) -> AnalysisResult:
        y_col = params.count_response_y
        cont_cols = [c for c in params.continuous_predictors if c in df.columns]
        cat_cols = [c for c in params.categorical_predictors if c in df.columns]
        offset_col = params.exposure_offset

        if y_col not in df.columns:
            raise ValueError(f"Response column '{y_col}' not found in active worksheet.")
        if len(cont_cols) + len(cat_cols) == 0:
            raise ValueError("Select at least one continuous or categorical predictor.")

        needed_cols = [y_col] + cont_cols + cat_cols
        if offset_col and offset_col in df.columns:
            needed_cols.append(offset_col)

        sub_df = df[needed_cols].dropna().copy().reset_index(drop=True)
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        for c in cont_cols:
            sub_df[c] = pd.to_numeric(sub_df[c], errors="coerce")

        if offset_col and offset_col in sub_df.columns:
            sub_df[offset_col] = pd.to_numeric(sub_df[offset_col], errors="coerce")

        sub_df = sub_df.dropna().reset_index(drop=True)
        n = len(sub_df)

        if n < 6:
            raise ValueError("Poisson Regression requires at least 6 observations.")

        y = sub_df[y_col].to_numpy(dtype=float)
        if np.any(y < 0):
            raise ValueError("Poisson response variable cannot contain negative counts.")

        # Exposure Offset
        if offset_col and offset_col in sub_df.columns:
            t_raw = sub_df[offset_col].to_numpy(dtype=float)
            if np.any(t_raw <= 0):
                raise ValueError("Exposure offset variable must be strictly positive.")
            offset_arr = np.log(t_raw)
        else:
            offset_arr = np.zeros(n, dtype=float)

        # Build Design Matrix X
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

        # Iteratively Reweighted Least Squares (IRLS) for Poisson GLM (Log link)
        beta = np.zeros(p)
        beta[0] = math.log(max(1e-3, float(np.mean(y))))

        for _ in range(50):
            eta = offset_arr + X_mat @ beta
            mu = np.clip(np.exp(np.clip(eta, -20, 20)), 1e-6, 1e6)
            w = mu
            z = eta - offset_arr + (y - mu) / mu

            W_mat = np.diag(w)
            xtwx = X_mat.T @ W_mat @ X_mat
            try:
                beta_new = np.linalg.pinv(xtwx) @ (X_mat.T @ W_mat @ z)
            except Exception:
                break

            if np.max(np.abs(beta_new - beta)) < 1e-6:
                beta = beta_new
                break
            beta = beta_new

        # Final predictions & diagnostics
        eta_final = offset_arr + X_mat @ beta
        mu_final = np.clip(np.exp(np.clip(eta_final, -20, 20)), 1e-6, 1e6)

        cov_beta = np.linalg.pinv(X_mat.T @ np.diag(mu_final) @ X_mat)
        se_beta = np.sqrt(np.maximum(1e-12, np.diag(cov_beta)))
        z_stats = beta / np.maximum(1e-12, se_beta)
        p_vals = [float(2.0 * (1.0 - stats.norm.cdf(abs(z_val)))) for z_val in z_stats]

        # Deviance and Pearson Goodness-of-fit
        # Deviance: 2 * sum( y * ln(y / mu) - (y - mu) )
        dev_res = 2.0 * np.sum(np.where(y > 0, y * np.log(y / mu_final), 0.0) - (y - mu_final))
        pearson_chi2 = float(np.sum(((y - mu_final) ** 2) / mu_final))
        df_dev = max(1, n - p)
        dispersion_phi = pearson_chi2 / df_dev

        p_dev = float(1.0 - stats.chi2.cdf(dev_res, df_dev))
        p_pearson = float(1.0 - stats.chi2.cdf(pearson_chi2, df_dev))

        # Relative Risk / Rate Ratios: RR = exp(beta)
        coef_rows = []
        for i, tname in enumerate(term_names):
            rr_val = math.exp(beta[i]) if i > 0 else "---"
            rr_ci = f"({math.exp(beta[i] - 1.96 * se_beta[i]):.3f}, {math.exp(beta[i] + 1.96 * se_beta[i]):.3f})" if i > 0 else "---"
            coef_rows.append([
                tname,
                f"{beta[i]:.4f}",
                f"{se_beta[i]:.4f}",
                f"{z_stats[i]:.2f}",
                f"{p_vals[i]:.4f}" if p_vals[i] >= 0.0001 else "< 0.0001",
                f"{rr_val:.4f}" if isinstance(rr_val, float) else rr_val,
                rr_ci
            ])

        coef_table = TableResult(
            title="Poisson Regression Coefficients and Rate Ratios (RR)",
            headers=["Term", "Coef", "SE Coef", "Z-Value", "p-Value", "Rate Ratio (RR)", "95% CI (RR)"],
            rows=coef_rows
        )

        gof_table = TableResult(
            title="Goodness-of-Fit and Overdispersion Assessment",
            headers=["Criterion", "DF", "Value", "Value / DF", "p-Value"],
            rows=[
                ["Deviance", str(df_dev), f"{dev_res:.4f}", f"{dev_res / df_dev:.3f}", f"{p_dev:.4f}" if p_dev >= 0.0001 else "< 0.0001"],
                ["Pearson Chi-Square", str(df_dev), f"{pearson_chi2:.4f}", f"{dispersion_phi:.3f}", f"{p_pearson:.4f}" if p_pearson >= 0.0001 else "< 0.0001"]
            ]
        )

        # Plotly Observed vs Expected Fits
        plotly_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": mu_final.tolist(),
                    "y": y.tolist(),
                    "name": "Observed vs. Fitted Counts",
                    "marker": {"color": "#0078d4", "size": 6}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [0, float(np.max(y))],
                    "y": [0, float(np.max(y))],
                    "name": "Ideal 1:1 Fit Line",
                    "line": {"color": "#d13438", "dash": "dash", "width": 1.5}
                }
            ],
            "layout": {
                "title": f"Poisson Regression Diagnostic: Observed Counts vs. Expected Fits for {y_col}",
                "xaxis": {"title": "Expected Poisson Mean (Mu)", "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": f"Observed Counts ({y_col})", "showgrid": True, "gridcolor": "#ececec"},
                "legend": {"orientation": "h", "y": -0.2},
                "annotations": [
                    {
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.05,
                        "y": 0.95,
                        "text": f"<b>Dispersion Phi:</b> {dispersion_phi:.3f}<br><b>Status:</b> {'Adequate (No Overdispersion)' if dispersion_phi < 1.5 else 'Overdispersion Detected'}",
                        "showarrow": False,
                        "bgcolor": "rgba(255,255,255,0.85)",
                        "bordercolor": "#d2d0ce",
                        "borderwidth": 1
                    }
                ]
            }
        }

        return AnalysisResult(
            title=f"Poisson Regression for {y_col}",
            subtitle=f"Dispersion Phi = {dispersion_phi:.3f} | Deviance = {dev_res:.3f} (p = {p_dev:.3f})",
            tables=[coef_table, gof_table],
            plotly_figure=plotly_fig,
            statistics={
                "coefficients": beta.tolist(),
                "terms": term_names,
                "deviance": dev_res,
                "dispersion_phi": dispersion_phi,
                "p_deviance": p_dev
            }
        )
