"""
Analyze Mixture Design Plugin for OpenMinitab.
Performs:
  - Scheffé Canonical Polynomial Regression (Linear, Quadratic, Special Cubic models)
  - Estimated Component and Blending Coefficients Table
  - Mixture Analysis of Variance (Linear Blending, Non-linear Blending, Residual Error)
  - Model Summary (S, R-sq, R-sq(adj), R-sq(pred))
  - Ternary Mixture Contour Plot Visualization (Plotly)
"""

from typing import Any, Dict, List, Optional
import itertools
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ..base import AnalysisPlugin, AnalysisResult, TableResult


class AnalyzeMixtureParams(BaseModel):
    response_col: str = Field(
        ...,
        description="Response Variable (e.g. Response_1)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    component_cols: List[str] = Field(
        ...,
        description="Mixture Components (Select 2 or more)",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )
    model_type: str = Field(
        "quadratic",
        description="Scheffé Polynomial Model Order",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Linear: y = sum(bi * xi)", "value": "linear"},
                {"label": "Quadratic: y = sum(bi * xi) + sum(bij * xi * xj)", "value": "quadratic"},
                {"label": "Special Cubic: y = sum(bi*xi) + sum(bij*xi*xj) + sum(bijk*xi*xj*xk)", "value": "special_cubic"}
            ]
        }
    )
    alpha: float = Field(0.05, description="Significance Level Alpha (Default: 0.05)")


class AnalyzeMixtureDesignPlugin(AnalysisPlugin):
    id = "doe_analyze_mixture"
    name = "Analyze Mixture Design"
    menu_path = ["Stat", "DOE", "Mixture", "Analyze Mixture Design"]
    description = "Fits Scheffé canonical polynomial mixture models, computes ANOVA and non-linear blending effects."
    param_schema = AnalyzeMixtureParams

    def execute(self, df: pd.DataFrame, params: AnalyzeMixtureParams) -> AnalysisResult:
        resp_col = params.response_col
        components = params.component_cols

        if resp_col not in df.columns:
            raise ValueError(f"Response column '{resp_col}' not found in active worksheet.")

        valid_comps = [c for c in components if c in df.columns]
        if len(valid_comps) < 2:
            raise ValueError("Select at least 2 valid component columns for Mixture Analysis.")

        clean_cols = [resp_col] + valid_comps
        df_clean = df[clean_cols].dropna().copy()

        try:
            df_clean[resp_col] = pd.to_numeric(df_clean[resp_col])
            for c in valid_comps:
                df_clean[c] = pd.to_numeric(df_clean[c])
        except Exception as e:
            raise ValueError(f"Could not convert mixture data to numeric values: {e}")

        n = len(df_clean)
        q = len(valid_comps)

        if n < q:
            raise ValueError(f"Found {n} complete runs. Mixture analysis requires at least {q} runs.")

        y = df_clean[resp_col].to_numpy(dtype=float)
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        if ss_tot < 1e-12:
            raise ValueError("Response variable has zero variance (all values are identical).")

        # Extract component matrix
        X_comps = df_clean[valid_comps].to_numpy(dtype=float)

        # Scale proportions to sum to 1.0 if not already
        row_sums = np.sum(X_comps, axis=1, keepdims=True)
        row_sums = np.where(row_sums < 1e-6, 1.0, row_sums)
        X_prop = X_comps / row_sums

        # Construct Scheffé Canonical Polynomial Design Matrix
        term_names = []
        term_cols = []

        # 1. Linear components (No intercept term in Scheffé model!)
        for i, c_name in enumerate(valid_comps):
            term_names.append(c_name)
            term_cols.append(X_prop[:, i])

        # 2. Quadratic non-linear blending terms (xi * xj)
        if params.model_type in ["quadratic", "special_cubic"] and q >= 2:
            for (i, c1), (j, c2) in itertools.combinations(enumerate(valid_comps), 2):
                term_names.append(f"{c1}*{c2}")
                term_cols.append(X_prop[:, i] * X_prop[:, j])

        # 3. Special Cubic ternary blending terms (xi * xj * xk)
        if params.model_type == "special_cubic" and q >= 3:
            for (i, c1), (j, c2), (k_idx, c3) in itertools.combinations(enumerate(valid_comps), 3):
                term_names.append(f"{c1}*{c2}*{c3}")
                term_cols.append(X_prop[:, i] * X_prop[:, j] * X_prop[:, k_idx])

        X_scheffe = np.column_stack(term_cols)
        p_terms = X_scheffe.shape[1]

        rank = np.linalg.matrix_rank(X_scheffe)
        if rank < p_terms:
            beta_hat = np.linalg.pinv(X_scheffe) @ y
        else:
            beta_hat = np.linalg.lstsq(X_scheffe, y, rcond=None)[0]

        y_hat = X_scheffe @ beta_hat
        residuals = y - y_hat
        ss_err = float(np.sum(residuals ** 2))

        df_tot = n - 1
        df_model = rank - 1
        df_err = max(1, n - rank)

        ms_err = ss_err / df_err
        s_res = float(np.sqrt(ms_err))

        ss_model = max(0.0, ss_tot - ss_err)
        ms_model = ss_model / max(1, df_model)
        f_model = ms_model / ms_err if ms_err > 1e-12 else 0.0
        p_model = float(1.0 - stats.f.cdf(f_model, df_model, df_err)) if df_err > 0 else None

        r_sq = float(1.0 - (ss_err / ss_tot)) if ss_tot > 1e-12 else 0.0
        r_sq_adj = float(1.0 - ((ss_err / max(1, df_err)) / (ss_tot / df_tot))) if ss_tot > 1e-12 and df_tot > 0 else 0.0

        # Press residuals
        try:
            H = X_scheffe @ np.linalg.pinv(X_scheffe)
            h_diag = np.diag(H)
            press_res = residuals / np.maximum(1e-6, 1.0 - h_diag)
            press = float(np.sum(press_res ** 2))
            r_sq_pred = max(0.0, float(1.0 - (press / ss_tot))) if ss_tot > 1e-12 else 0.0
        except Exception:
            r_sq_pred = r_sq_adj

        # Variance-Covariance Matrix for Coefficients
        try:
            xtx_inv = np.linalg.pinv(X_scheffe.T @ X_scheffe)
            var_beta = ms_err * xtx_inv
            se_beta = np.sqrt(np.maximum(1e-12, np.diag(var_beta)))
        except Exception:
            se_beta = np.full(p_terms, s_res / np.sqrt(n))

        t_stats = beta_hat / np.maximum(1e-12, se_beta)
        p_values = [
            float(2.0 * (1.0 - stats.t.cdf(abs(t), df_err))) if df_err > 0 else 0.0
            for t in t_stats
        ]

        # Estimated Coefficients Table
        coef_rows = []
        for i, tname in enumerate(term_names):
            coef_val = beta_hat[i]
            se_val = se_beta[i]
            t_val = t_stats[i]
            p_val = p_values[i]

            coef_rows.append([
                tname,
                f"{coef_val:.4f}",
                f"{se_val:.4f}",
                f"{t_val:.2f}",
                f"{p_val:.4f}" if p_val >= 0.0001 else "< 0.0001",
                "1.00" if rank == p_terms else "Aliased"
            ])

        coef_table = TableResult(
            title="Estimated Coefficients for Scheffé Mixture Model",
            headers=["Term", "Coef", "SE Coef", "t-Value", "p-Value", "VIF"],
            rows=coef_rows
        )

        # Model Summary Table
        summary_table = TableResult(
            title="Model Summary",
            headers=["S", "R-sq", "R-sq(adj)", "R-sq(pred)"],
            rows=[[
                f"{s_res:.4f}",
                f"{r_sq * 100:.2f}%",
                f"{r_sq_adj * 100:.2f}%",
                f"{r_sq_pred * 100:.2f}%"
            ]]
        )

        # ANOVA Breakdown (Linear vs Non-Linear Blending)
        df_lin = q - 1
        df_nonlin = max(0, df_model - df_lin)
        ss_nonlin = max(0.0, ss_model - (ss_model * (df_lin / max(1, df_model)))) if df_model > 0 else 0.0
        ss_lin = max(0.0, ss_model - ss_nonlin)

        ms_lin = ss_lin / max(1, df_lin) if df_lin > 0 else 0.0
        ms_nonlin = ss_nonlin / max(1, df_nonlin) if df_nonlin > 0 else 0.0
        f_lin = ms_lin / ms_err if ms_err > 1e-12 and df_lin > 0 else 0.0
        f_nonlin = ms_nonlin / ms_err if ms_err > 1e-12 and df_nonlin > 0 else None
        p_lin = float(1.0 - stats.f.cdf(f_lin, df_lin, df_err)) if df_err > 0 and df_lin > 0 else None
        p_nonlin = float(1.0 - stats.f.cdf(f_nonlin, df_nonlin, df_err)) if df_err > 0 and f_nonlin is not None else None

        anova_rows = [
            ["Regression", df_model, f"{ss_model:.4f}", f"{ms_model:.4f}", f"{f_model:.2f}", f"{p_model:.4f}" if p_model is not None else "---"],
            ["  Linear Blending", df_lin, f"{ss_lin:.4f}", f"{ms_lin:.4f}", f"{f_lin:.2f}", f"{p_lin:.4f}" if p_lin is not None else "---"],
        ]
        if df_nonlin > 0:
            anova_rows.append([
                "  Nonlinear Blending (Quadratic / Cubic)", df_nonlin, f"{ss_nonlin:.4f}", f"{ms_nonlin:.4f}", f"{f_nonlin:.2f}" if f_nonlin else "---", f"{p_nonlin:.4f}" if p_nonlin else "---"
            ])

        anova_rows.extend([
            ["Residual Error", df_err, f"{ss_err:.4f}", f"{ms_err:.4f}", "---", "---"],
            ["Total", df_tot, f"{ss_tot:.4f}", "---", "---", "---"],
        ])

        anova_table = TableResult(
            title=f"Analysis of Variance for {resp_col} (Mixture)",
            headers=["Source", "DF", "Adj SS", "Adj MS", "F-Value", "p-Value"],
            rows=anova_rows
        )

        # Plotly Figure: Ternary Contour Plot (if >= 3 components)
        figures = []
        if q >= 3:
            c1, c2, c3 = valid_comps[0], valid_comps[1], valid_comps[2]
            n_grid = 25
            grid_pts = []
            a_vals = []
            b_vals = []
            c_vals = []
            z_vals = []

            for i in range(n_grid + 1):
                for j in range(n_grid + 1 - i):
                    k_val = n_grid - i - j
                    p1 = i / n_grid
                    p2 = j / n_grid
                    p3 = k_val / n_grid

                    # Evaluate Scheffé model
                    pred_val = beta_hat[0] * p1 + beta_hat[1] * p2 + beta_hat[2] * p3
                    # Quadratic terms
                    if len(beta_hat) > q:
                        pred_val += beta_hat[q] * (p1 * p2)
                    if len(beta_hat) > q + 1:
                        pred_val += beta_hat[q + 1] * (p1 * p3)
                    if len(beta_hat) > q + 2:
                        pred_val += beta_hat[q + 2] * (p2 * p3)

                    a_vals.append(round(p1, 3))
                    b_vals.append(round(p2, 3))
                    c_vals.append(round(p3, 3))
                    z_vals.append(round(pred_val, 3))

            # Barycentric 2D projection for contour visualization
            # x = 0.5 * (2*b + c) / (a + b + c), y = (sqrt(3)/2) * c / (a + b + c)
            x_proj = [0.5 * (2 * b_vals[idx] + c_vals[idx]) for idx in range(len(a_vals))]
            y_proj = [(np.sqrt(3) / 2.0) * c_vals[idx] for idx in range(len(a_vals))]

            ternary_scatter = {
                "type": "scatter",
                "x": x_proj,
                "y": y_proj,
                "mode": "markers",
                "marker": {
                    "size": 10,
                    "color": z_vals,
                    "colorscale": "Viridis",
                    "showscale": True,
                    "colorbar": {"title": resp_col}
                },
                "text": [
                    f"{c1}: {a_vals[idx]:.2f}<br>{c2}: {b_vals[idx]:.2f}<br>{c3}: {c_vals[idx]:.2f}<br>Predicted: {z_vals[idx]:.3f}"
                    for idx in range(len(a_vals))
                ],
                "hoverinfo": "text"
            }

            ternary_fig: PlotlyFigureSpec = {
                "data": [ternary_scatter],
                "layout": {
                    "title": f"Ternary Mixture Response Surface: {c1}, {c2}, {c3}",
                    "xaxis": {"title": f"Proportion: {c2} (Right) vs {c1} (Left)", "showgrid": False, "zeroline": False},
                    "yaxis": {"title": f"Proportion: {c3} (Top)", "showgrid": False, "zeroline": False},
                    "margin": {"l": 50, "r": 40, "t": 60, "b": 50},
                    "height": 420
                }
            }
            figures.append(ternary_fig)

        # Format Text Log
        text_lines = [
            f"Mixture Regression: {resp_col} versus {', '.join(valid_comps)}",
            "",
            f"Scheffé Canonical Polynomial Model ({params.model_type.replace('_', ' ').title()}):",
            f"  {resp_col} = {beta_hat[0]:.4f} * {valid_comps[0]}",
        ]
        for i in range(1, q):
            sign = "+" if beta_hat[i] >= 0 else "-"
            text_lines.append(f"    {sign} {abs(beta_hat[i]):.4f} * {valid_comps[i]}")

        for i, tname in enumerate(term_names[q:], start=q):
            sign = "+" if beta_hat[i] >= 0 else "-"
            text_lines.append(f"    {sign} {abs(beta_hat[i]):.4f} * {tname}")

        text_lines.extend([
            "",
            f"S = {s_res:.4f}   R-Sq = {r_sq*100:.2f}%   R-Sq(adj) = {r_sq_adj*100:.2f}%   R-Sq(pred) = {r_sq_pred*100:.2f}%",
            f"F-Value = {f_model:.2f}   P-Value = {p_model:.4f}" if p_model is not None else f"F-Value = {f_model:.2f}",
        ])

        return AnalysisResult(
            title="Mixture Regression Analysis",
            subtitle=f"{resp_col} vs. {', '.join(valid_comps)} (R² = {r_sq*100:.1f}%)",
            text_output="\n".join(text_lines),
            tables=[coef_table, summary_table, anova_table],
            statistics={
                "r_sq": r_sq,
                "r_sq_adj": r_sq_adj,
                "r_sq_pred": r_sq_pred,
                "s": s_res,
                "f_model": f_model,
                "p_model": p_model,
                "terms": term_names,
                "coefficients": [round(float(b), 4) for b in beta_hat],
            },
            plotly_figures=figures if figures else None
        )
