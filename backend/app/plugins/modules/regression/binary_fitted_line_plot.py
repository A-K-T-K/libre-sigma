"""
Binary Fitted Line Plot Plugin for OpenMinitab Regression.
Fits binary logistic, probit, and complementary log-log models with jittered binary event scatter and sigmoid 95% CI probability bands.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class BinaryFittedLinePlotParams(BaseModel):
    binary_response_y: str = Field(
        ...,
        description="Binary Event Variable Y (0 / 1)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    predictor_x: str = Field(
        ...,
        description="Continuous Predictor Variable X",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    link_function: str = Field(
        "logit",
        description="Link Function",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Logit: ln(p / (1-p))", "value": "logit"},
                {"label": "Probit: InvNorm(p)", "value": "probit"},
                {"label": "Complementary Log-Log (Gompit): ln(-ln(1-p))", "value": "cloglog"}
            ]
        }
    )
    unit_change_x: float = Field(1.0, description="Unit change in X for Odds Ratio (Default: 1.0)")


class BinaryFittedLinePlotPlugin(AnalysisPlugin):
    id = "binary_fitted_line_plot"
    name = "Binary Fitted Line Plot"
    menu_path = ["Stat", "Regression", "Binary Fitted Line Plot"]
    description = "Displays the estimated probability of a binary event across a continuous predictor with S-curve confidence bands."
    param_schema = BinaryFittedLinePlotParams

    def execute(self, df: pd.DataFrame, params: BinaryFittedLinePlotParams) -> AnalysisResult:
        y_col, x_col = params.binary_response_y, params.predictor_x
        if y_col not in df.columns or x_col not in df.columns:
            raise ValueError(f"Columns '{y_col}' and/or '{x_col}' not found in active worksheet.")

        sub_df = df[[x_col, y_col]].dropna().copy()
        sub_df[x_col] = pd.to_numeric(sub_df[x_col], errors="coerce")

        # Map binary outcome to 0 and 1
        raw_y = sub_df[y_col].astype(str).str.strip().str.lower()
        if set(raw_y.unique()).issubset({"0", "1", "0.0", "1.0"}):
            y_bin = pd.to_numeric(sub_df[y_col], errors="coerce")
        elif set(raw_y.unique()).issubset({"pass", "fail"}):
            y_bin = raw_y.map({"pass": 0, "fail": 1})
        elif set(raw_y.unique()).issubset({"yes", "no"}):
            y_bin = raw_y.map({"no": 0, "yes": 1})
        else:
            unique_vals = sorted(sub_df[y_col].dropna().unique())
            if len(unique_vals) != 2:
                raise ValueError("Binary Fitted Line Plot requires a binary response with exactly 2 unique levels.")
            y_bin = (sub_df[y_col] == unique_vals[1]).astype(int)

        sub_df["_y_bin"] = y_bin
        sub_df = sub_df.dropna().reset_index(drop=True)

        n = len(sub_df)
        if n < 6:
            raise ValueError("Binary Fitted Line Plot requires at least 6 observations.")

        x = sub_df[x_col].to_numpy(dtype=float)
        y = sub_df["_y_bin"].to_numpy(dtype=float)

        if len(np.unique(y)) < 2:
            raise ValueError("Response variable contains only a single binary outcome (all 0s or all 1s).")

        # Iteratively Reweighted Least Squares (IRLS) for GLM Binomial
        X_mat = np.column_stack([np.ones(n), x])
        beta = np.zeros(2)

        link = params.link_function
        for _ in range(50):
            eta = X_mat @ beta
            if link == "logit":
                p_hat = np.clip(1.0 / (1.0 + np.exp(-eta)), 1e-6, 1.0 - 1e-6)
                d_mu_d_eta = p_hat * (1.0 - p_hat)
            elif link == "probit":
                p_hat = np.clip(stats.norm.cdf(eta), 1e-6, 1.0 - 1e-6)
                d_mu_d_eta = np.clip(stats.norm.pdf(eta), 1e-6, 1.0)
            else: # C-Log-Log
                p_hat = np.clip(1.0 - np.exp(-np.exp(np.clip(eta, -20, 20))), 1e-6, 1.0 - 1e-6)
                d_mu_d_eta = (1.0 - p_hat) * np.exp(np.clip(eta, -20, 20))

            var_mu = np.maximum(1e-6, p_hat * (1.0 - p_hat))
            w = (d_mu_d_eta ** 2) / var_mu
            z = eta + (y - p_hat) / np.maximum(1e-6, d_mu_d_eta)

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

        # Final predictions & covariance
        eta_final = X_mat @ beta
        if link == "logit":
            p_final = np.clip(1.0 / (1.0 + np.exp(-eta_final)), 1e-6, 1.0 - 1e-6)
            d_mu = p_final * (1.0 - p_final)
        elif link == "probit":
            p_final = np.clip(stats.norm.cdf(eta_final), 1e-6, 1.0 - 1e-6)
            d_mu = np.clip(stats.norm.pdf(eta_final), 1e-6, 1.0)
        else:
            p_final = np.clip(1.0 - np.exp(-np.exp(np.clip(eta_final, -20, 20))), 1e-6, 1.0 - 1e-6)
            d_mu = (1.0 - p_final) * np.exp(np.clip(eta_final, -20, 20))

        w_final = (d_mu ** 2) / np.maximum(1e-6, p_final * (1.0 - p_final))
        cov_beta = np.linalg.pinv(X_mat.T @ np.diag(w_final) @ X_mat)
        se_beta = np.sqrt(np.maximum(1e-12, np.diag(cov_beta)))
        z_stats = beta / np.maximum(1e-12, se_beta)
        p_vals = [float(2.0 * (1.0 - stats.norm.cdf(abs(z_val)))) for z_val in z_stats]

        # Goodness-of-Fit (Deviance & Pearson)
        dev_terms = np.zeros(n)
        pos_mask = (y == 1)
        neg_mask = (y == 0)
        dev_terms[pos_mask] = np.log(np.maximum(1e-9, p_final[pos_mask]))
        dev_terms[neg_mask] = np.log(np.maximum(1e-9, 1.0 - p_final[neg_mask]))
        dev_res = float(-2.0 * np.sum(dev_terms))

        pearson_chi2 = float(np.sum(((y - p_final) ** 2) / (p_final * (1.0 - p_final))))
        df_dev = max(1, n - 2)
        p_dev = float(1.0 - stats.chi2.cdf(dev_res, df_dev))

        # Odds Ratio (for Logit link)
        unit_dx = params.unit_change_x
        odds_ratio = math.exp(beta[1] * unit_dx) if link == "logit" else None
        or_ci_low = math.exp((beta[1] - 1.96 * se_beta[1]) * unit_dx) if link == "logit" else None
        or_ci_high = math.exp((beta[1] + 1.96 * se_beta[1]) * unit_dx) if link == "logit" else None

        # Build Session Log Tables
        coef_rows = [
            ["Constant", f"{beta[0]:.4f}", f"{se_beta[0]:.4f}", f"{z_stats[0]:.2f}", f"{p_vals[0]:.4f}" if p_vals[0] >= 0.0001 else "< 0.0001"],
            [x_col, f"{beta[1]:.4f}", f"{se_beta[1]:.4f}", f"{z_stats[1]:.2f}", f"{p_vals[1]:.4f}" if p_vals[1] >= 0.0001 else "< 0.0001"]
        ]

        coef_table = TableResult(
            title=f"Estimated Parameters for Binary {link.capitalize()} Model",
            headers=["Term", "Coef", "SE Coef", "Z-Value", "p-Value"],
            rows=coef_rows
        )

        gof_table = TableResult(
            title="Goodness-of-Fit and Deviance Tests",
            headers=["Test", "DF", "Chi-Square", "p-Value"],
            rows=[
                ["Deviance", str(df_dev), f"{dev_res:.4f}", f"{p_dev:.4f}" if p_dev >= 0.0001 else "< 0.0001"],
                ["Pearson", str(df_dev), f"{pearson_chi2:.4f}", f"{1.0 - stats.chi2.cdf(pearson_chi2, df_dev):.4f}"]
            ]
        )

        # Plotly Sigmoid S-Curve with Confidence Band & Jittered Binary Points
        x_min, x_max = float(np.min(x)), float(np.max(x))
        x_grid = np.linspace(x_min, x_max, 250)
        X_grid = np.column_stack([np.ones(len(x_grid)), x_grid])
        eta_grid = X_grid @ beta
        se_eta_grid = np.sqrt(np.sum((X_grid @ cov_beta) * X_grid, axis=1))

        if link == "logit":
            p_grid_fit = 1.0 / (1.0 + np.exp(-eta_grid))
            p_grid_low = 1.0 / (1.0 + np.exp(-(eta_grid - 1.96 * se_eta_grid)))
            p_grid_high = 1.0 / (1.0 + np.exp(-(eta_grid + 1.96 * se_eta_grid)))
        elif link == "probit":
            p_grid_fit = stats.norm.cdf(eta_grid)
            p_grid_low = stats.norm.cdf(eta_grid - 1.96 * se_eta_grid)
            p_grid_high = stats.norm.cdf(eta_grid + 1.96 * se_eta_grid)
        else:
            p_grid_fit = 1.0 - np.exp(-np.exp(eta_grid))
            p_grid_low = 1.0 - np.exp(-np.exp(eta_grid - 1.96 * se_eta_grid))
            p_grid_high = 1.0 - np.exp(-np.exp(eta_grid + 1.96 * se_eta_grid))

        # Add vertical jitter to 0/1 scatter points for clean visualization
        np.random.seed(42)
        y_jitter = y + np.where(y == 1, -np.random.uniform(0.01, 0.06, n), np.random.uniform(0.01, 0.06, n))

        plotly_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": x.tolist(),
                    "y": y_jitter.tolist(),
                    "name": f"Observations ({y_col})",
                    "marker": {"color": "#0078d4", "size": 6, "opacity": 0.7}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": x_grid.tolist(),
                    "y": p_grid_fit.tolist(),
                    "name": f"Fitted Probability ({link.capitalize()})",
                    "line": {"color": "#d13438", "width": 2.5}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": x_grid.tolist() + x_grid[::-1].tolist(),
                    "y": p_grid_high.tolist() + p_grid_low[::-1].tolist(),
                    "fill": "toself",
                    "name": "95% CI Band",
                    "fillcolor": "rgba(0, 132, 80, 0.15)",
                    "line": {"color": "rgba(0,0,0,0)"}
                }
            ],
            "layout": {
                "title": f"Binary Fitted Line Plot: P({y_col} = 1) vs. {x_col}",
                "xaxis": {"title": x_col, "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": f"Probability P({y_col} = 1)", "range": [-0.08, 1.08], "showgrid": True, "gridcolor": "#ececec"},
                "legend": {"orientation": "h", "y": -0.2},
                "annotations": [
                    {
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.05,
                        "y": 0.95,
                        "text": f"<b>Link:</b> {link.capitalize()}<br><b>Deviance:</b> {dev_res:.3f} (p = {p_dev:.3f})<br>" + (f"<b>Odds Ratio:</b> {odds_ratio:.3f}" if odds_ratio else ""),
                        "showarrow": False,
                        "bgcolor": "rgba(255,255,255,0.85)",
                        "bordercolor": "#d2d0ce",
                        "borderwidth": 1
                    }
                ]
            }
        }

        return AnalysisResult(
            title=f"Binary Fitted Line Plot for {y_col} vs. {x_col}",
            subtitle=f"Link = {link.capitalize()} | Slope p-Value = {p_vals[1]:.4f}" + (f" | Odds Ratio = {odds_ratio:.2f}" if odds_ratio else ""),
            tables=[coef_table, gof_table],
            plotly_figure=plotly_fig,
            statistics={
                "link": link,
                "intercept": beta[0],
                "slope": beta[1],
                "deviance": dev_res,
                "odds_ratio": odds_ratio,
                "p_slope": p_vals[1]
            }
        )
