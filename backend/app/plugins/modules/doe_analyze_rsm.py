"""
Analyze Response Surface Design Plugin for OpenMinitab.
Performs:
  - Full Quadratic Response Surface Regression: y = b0 + sum(bi*xi) + sum(bii*xi^2) + sum(bij*xi*xj)
  - Estimated Coefficients and Standard Errors Table
  - Full Response Surface ANOVA Table (Linear, Square, 2-Way Interactions, Lack of Fit, Pure Error)
  - Canonical Analysis and Stationary Point Optimization (Maximum, Minimum, or Saddle Point)
  - 2D Contour Plot & 3D Surface Plot (Plotly)
"""

from typing import Any, Dict, List, Optional
import itertools
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ..base import AnalysisPlugin, AnalysisResult, TableResult


class AnalyzeRsmParams(BaseModel):
    response_col: str = Field(
        ...,
        description="Response Variable (e.g. Response_1)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    factor_cols: List[str] = Field(
        ...,
        description="Continuous Factors (Select 2 or more)",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )
    alpha: float = Field(0.05, description="Significance Level Alpha (Default: 0.05)")


class AnalyzeRsmDesignPlugin(AnalysisPlugin):
    id = "doe_analyze_rsm"
    name = "Analyze Response Surface Design"
    menu_path = ["Stat", "DOE", "Response Surface", "Analyze Response Surface Design"]
    description = "Fits full quadratic response surface models, performs ANOVA, canonical stationary point analysis, and contour plots."
    param_schema = AnalyzeRsmParams

    def execute(self, df: pd.DataFrame, params: AnalyzeRsmParams) -> AnalysisResult:
        resp_col = params.response_col
        factors = params.factor_cols

        if resp_col not in df.columns:
            raise ValueError(f"Response column '{resp_col}' not found in active worksheet.")

        valid_factors = [f for f in factors if f in df.columns]
        if len(valid_factors) < 2:
            raise ValueError("Select at least 2 valid continuous factors for Response Surface Analysis.")

        # Clean numeric rows
        clean_cols = [resp_col] + valid_factors
        df_clean = df[clean_cols].dropna().copy()

        try:
            df_clean[resp_col] = pd.to_numeric(df_clean[resp_col])
            for f in valid_factors:
                df_clean[f] = pd.to_numeric(df_clean[f])
        except Exception as e:
            raise ValueError(f"Could not convert data to numeric values: {e}")

        n = len(df_clean)
        k = len(valid_factors)
        
        # Need at least 1 + 2k + k*(k-1)/2 parameters
        p_required = 1 + 2 * k + (k * (k - 1) // 2)
        if n < p_required:
            raise ValueError(f"Found {n} complete rows. Full quadratic RSM with {k} factors requires at least {p_required} runs.")

        y = df_clean[resp_col].to_numpy(dtype=float)
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        if ss_tot < 1e-12:
            raise ValueError("Response variable has zero variance (all values are identical).")

        # Coded normalization of factor columns to -1 and +1
        X_coded_dict: Dict[str, np.ndarray] = {}
        factor_mids: Dict[str, float] = {}
        factor_halfs: Dict[str, float] = {}

        for f in valid_factors:
            f_vals = df_clean[f].to_numpy(dtype=float)
            min_v, max_v = np.min(f_vals), np.max(f_vals)
            mid = (max_v + min_v) / 2.0
            half = (max_v - min_v) / 2.0 if abs(max_v - min_v) > 1e-9 else 1.0
            X_coded_dict[f] = (f_vals - mid) / half
            factor_mids[f] = mid
            factor_halfs[f] = half

        # Construct Design Matrix Columns
        # 1. Constant
        term_names = ["Constant"]
        term_cols = [np.ones(n, dtype=float)]

        # 2. Linear terms (A, B, C...)
        for f in valid_factors:
            term_names.append(f)
            term_cols.append(X_coded_dict[f])

        # 3. Square / Quadratic terms (A^2, B^2, C^2...)
        for f in valid_factors:
            term_names.append(f"{f}*{f}")
            term_cols.append(X_coded_dict[f] ** 2)

        # 4. 2-Way Interaction terms (A*B, A*C, B*C...)
        for f1, f2 in itertools.combinations(valid_factors, 2):
            term_names.append(f"{f1}*{f2}")
            term_cols.append(X_coded_dict[f1] * X_coded_dict[f2])

        X_full = np.column_stack(term_cols)
        p_terms = X_full.shape[1]

        rank = np.linalg.matrix_rank(X_full)
        if rank < p_terms:
            beta_hat = np.linalg.pinv(X_full) @ y
        else:
            beta_hat = np.linalg.lstsq(X_full, y, rcond=None)[0]

        y_hat = X_full @ beta_hat
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
            H = X_full @ np.linalg.pinv(X_full)
            h_diag = np.diag(H)
            press_res = residuals / np.maximum(1e-6, 1.0 - h_diag)
            press = float(np.sum(press_res ** 2))
            r_sq_pred = max(0.0, float(1.0 - (press / ss_tot))) if ss_tot > 1e-12 else 0.0
        except Exception:
            r_sq_pred = r_sq_adj

        # Variance-Covariance Matrix for Coefficients
        try:
            xtx_inv = np.linalg.pinv(X_full.T @ X_full)
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
                "1.00" if rank == p_terms and tname != "Constant" else ("---" if tname == "Constant" else "Aliased")
            ])

        coef_table = TableResult(
            title="Estimated Regression Coefficients for Response Surface Fit",
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

        # ANOVA Breakdown: Linear, Square, 2-Way
        # Linear: terms 1 to k
        df_lin = k
        ss_lin = sum(float(beta_hat[i]**2 / xtx_inv[i, i]) for i in range(1, 1 + k))
        ms_lin = ss_lin / df_lin
        f_lin = ms_lin / ms_err if ms_err > 1e-12 else 0.0
        p_lin = float(1.0 - stats.f.cdf(f_lin, df_lin, df_err))

        # Square: terms (1+k) to (2k)
        df_sq = k
        ss_sq = sum(float(beta_hat[i]**2 / xtx_inv[i, i]) for i in range(1 + k, 1 + 2 * k))
        ms_sq = ss_sq / df_sq
        f_sq = ms_sq / ms_err if ms_err > 1e-12 else 0.0
        p_sq = float(1.0 - stats.f.cdf(f_sq, df_sq, df_err))

        # 2-Way: remaining terms
        df_2way = max(0, df_model - df_lin - df_sq)
        ss_2way = max(0.0, ss_model - ss_lin - ss_sq)
        ms_2way = ss_2way / max(1, df_2way) if df_2way > 0 else 0.0
        f_2way = ms_2way / ms_err if ms_err > 1e-12 and df_2way > 0 else None
        p_2way = float(1.0 - stats.f.cdf(f_2way, df_2way, df_err)) if f_2way is not None else None

        # Lack of Fit and Pure Error test via replicate run grouping
        groups = df_clean.groupby(valid_factors)[resp_col].apply(list).to_dict()
        ss_pe = 0.0
        df_pe = 0
        for g_vals in groups.values():
            if len(g_vals) > 1:
                g_arr = np.array(g_vals, dtype=float)
                ss_pe += float(np.sum((g_arr - np.mean(g_arr)) ** 2))
                df_pe += len(g_vals) - 1

        ss_lof = max(0.0, ss_err - ss_pe)
        df_lof = max(0, df_err - df_pe)

        if df_pe > 0 and df_lof > 0:
            ms_lof = ss_lof / df_lof
            ms_pe = ss_pe / df_pe
            f_lof = ms_lof / ms_pe if ms_pe > 1e-12 else 0.0
            p_lof = float(1.0 - stats.f.cdf(f_lof, df_lof, df_pe))
        else:
            f_lof = None
            p_lof = None

        anova_rows = [
            ["Model", df_model, f"{ss_model:.4f}", f"{ms_model:.4f}", f"{f_model:.2f}", f"{p_model:.4f}" if p_model is not None else "---"],
            ["  Linear", df_lin, f"{ss_lin:.4f}", f"{ms_lin:.4f}", f"{f_lin:.2f}", f"{p_lin:.4f}" if p_lin >= 0.0001 else "< 0.0001"],
            ["  Square", df_sq, f"{ss_sq:.4f}", f"{ms_sq:.4f}", f"{f_sq:.2f}", f"{p_sq:.4f}" if p_sq >= 0.0001 else "< 0.0001"],
        ]
        if df_2way > 0:
            anova_rows.append([
                "  2-Way Interactions", df_2way, f"{ss_2way:.4f}", f"{ms_2way:.4f}", f"{f_2way:.2f}" if f_2way else "---", f"{p_2way:.4f}" if p_2way else "---"
            ])

        anova_rows.append(["Error (Residual)", df_err, f"{ss_err:.4f}", f"{ms_err:.4f}", "---", "---"])
        if df_pe > 0 and df_lof > 0:
            anova_rows.append(["  Lack of Fit", df_lof, f"{ss_lof:.4f}", f"{ss_lof/df_lof:.4f}", f"{f_lof:.2f}" if f_lof else "---", f"{p_lof:.4f}" if p_lof else "---"])
            anova_rows.append(["  Pure Error", df_pe, f"{ss_pe:.4f}", f"{ss_pe/df_pe:.4f}", "---", "---"])

        anova_rows.append(["Total", df_tot, f"{ss_tot:.4f}", "---", "---", "---"])

        anova_table = TableResult(
            title=f"Analysis of Variance for {resp_col}",
            headers=["Source", "DF", "Adj SS", "Adj MS", "F-Value", "p-Value"],
            rows=anova_rows
        )

        # Canonical / Stationary Point Analysis
        # b vector (linear coefficients)
        b_vec = beta_hat[1:1 + k]
        # B matrix (quadratic & interaction coefficients)
        B_mat = np.zeros((k, k), dtype=float)
        for i in range(k):
            B_mat[i, i] = beta_hat[1 + k + i] # square term

        inter_idx = 1 + 2 * k
        for i, j in itertools.combinations(range(k), 2):
            if inter_idx < p_terms:
                B_mat[i, j] = beta_hat[inter_idx] / 2.0
                B_mat[j, i] = beta_hat[inter_idx] / 2.0
                inter_idx += 1

        # Solve x0 = -0.5 * inv(B) * b
        try:
            x0_coded = -0.5 * np.linalg.pinv(B_mat) @ b_vec
            y0_pred = float(beta_hat[0] + 0.5 * (x0_coded.T @ b_vec))
            eigenvals, eigenvecs = np.linalg.eigh(B_mat)

            if np.all(eigenvals < -1e-5):
                stationary_type = "Maximum (Peak)"
            elif np.all(eigenvals > 1e-5):
                stationary_type = "Minimum (Trough)"
            else:
                stationary_type = "Saddle Point (Minimax)"

            # Convert x0 to actual un-coded units
            x0_actual = [
                float(factor_mids[valid_factors[i]] + x0_coded[i] * factor_halfs[valid_factors[i]])
                for i in range(k)
            ]
        except Exception:
            x0_coded = np.zeros(k)
            x0_actual = [float(factor_mids[f]) for f in valid_factors]
            y0_pred = float(beta_hat[0])
            stationary_type = "Stationary Point Indeterminate"
            eigenvals = np.zeros(k)

        # Canonical Table
        canonical_rows = [
            ["Stationary Point Nature", stationary_type],
            ["Predicted Response at Stationary Point", f"{y0_pred:.4f}"],
        ]
        for i, fname in enumerate(valid_factors):
            canonical_rows.append([
                f"  {fname} (Coded / Actual)",
                f"{x0_coded[i]:.4f} (Coded)  |  {x0_actual[i]:.4f} (Actual)"
            ])

        canonical_rows.append([
            "Eigenvalues (Canonical Curvatures)",
            ", ".join(f"{ev:.4f}" for ev in eigenvals)
        ])

        canonical_table = TableResult(
            title="Canonical Analysis of Response Surface",
            headers=["Parameter", "Optimal Setting / Value"],
            rows=canonical_rows
        )

        # Plotly Figure: 2D Contour and 3D Response Surface of First 2 Factors
        f1, f2 = valid_factors[0], valid_factors[1]
        grid_res = 30
        grid_f1 = np.linspace(-1.5, 1.5, grid_res)
        grid_f2 = np.linspace(-1.5, 1.5, grid_res)
        G1, G2 = np.meshgrid(grid_f1, grid_f2)

        # Evaluate model over grid with other factors at coded 0
        Z_grid = np.zeros((grid_res, grid_res), dtype=float)
        for r_i in range(grid_res):
            for c_i in range(grid_res):
                val1 = G1[r_i, c_i]
                val2 = G2[r_i, c_i]
                pt_val = beta_hat[0]
                pt_val += beta_hat[1] * val1 + beta_hat[2] * val2
                pt_val += beta_hat[1 + k] * (val1**2) + beta_hat[1 + k + 1] * (val2**2)
                # Interaction f1*f2
                pt_val += beta_hat[1 + 2 * k] * (val1 * val2)
                Z_grid[r_i, c_i] = pt_val

        # Un-code grid axes for visualization
        grid_f1_actual = factor_mids[f1] + grid_f1 * factor_halfs[f1]
        grid_f2_actual = factor_mids[f2] + grid_f2 * factor_halfs[f2]

        contour_fig: PlotlyFigureSpec = {
            "data": [
                {
                    "type": "contour",
                    "x": [round(float(v), 2) for v in grid_f1_actual],
                    "y": [round(float(v), 2) for v in grid_f2_actual],
                    "z": [[round(float(v), 3) for v in row] for row in Z_grid],
                    "colorscale": "Viridis",
                    "contours": {"coloring": "heatmap", "showlabels": True},
                    "colorbar": {"title": resp_col}
                }
            ],
            "layout": {
                "title": f"Contour Plot of {resp_col} vs {f1}, {f2}",
                "xaxis": {"title": f"{f1} (Actual)"},
                "yaxis": {"title": f"{f2} (Actual)"},
                "margin": {"l": 60, "r": 40, "t": 60, "b": 50},
                "height": 420
            }
        }

        # Format Minitab-identical Text Log
        text_lines = [
            f"Response Surface Regression: {resp_col} versus {', '.join(valid_factors)}",
            "",
            "Full Quadratic Regression Equation (in Coded Units):",
            f"  {resp_col} = {beta_hat[0]:.4f}",
        ]
        for i in range(k):
            sign = "+" if beta_hat[1+i] >= 0 else "-"
            text_lines.append(f"    {sign} {abs(beta_hat[1+i]):.4f} * {valid_factors[i]}")
        for i in range(k):
            sign = "+" if beta_hat[1+k+i] >= 0 else "-"
            text_lines.append(f"    {sign} {abs(beta_hat[1+k+i]):.4f} * {valid_factors[i]}^2")
        for i, tname in enumerate(term_names[1+2*k:], start=1+2*k):
            sign = "+" if beta_hat[i] >= 0 else "-"
            text_lines.append(f"    {sign} {abs(beta_hat[i]):.4f} * {tname}")

        text_lines.extend([
            "",
            f"S = {s_res:.4f}   R-Sq = {r_sq*100:.2f}%   R-Sq(adj) = {r_sq_adj*100:.2f}%   R-Sq(pred) = {r_sq_pred*100:.2f}%",
            "",
            f"Canonical Analysis Results: Stationary Point is a {stationary_type}",
            f"Predicted Response at Stationary Point: {y0_pred:.4f}",
        ])

        return AnalysisResult(
            title="Response Surface Regression Analysis",
            subtitle=f"{resp_col} vs. {', '.join(valid_factors)} ({stationary_type}, R² = {r_sq*100:.1f}%)",
            text_output="\n".join(text_lines),
            tables=[coef_table, summary_table, anova_table, canonical_table],
            statistics={
                "r_sq": r_sq,
                "r_sq_adj": r_sq_adj,
                "r_sq_pred": r_sq_pred,
                "s": s_res,
                "f_model": f_model,
                "p_model": p_model,
                "stationary_type": stationary_type,
                "y0_pred": y0_pred,
                "x0_coded": [round(float(v), 4) for v in x0_coded],
                "x0_actual": [round(float(v), 4) for v in x0_actual],
            },
            plotly_figure=contour_fig
        )
