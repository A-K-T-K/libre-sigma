"""
Partial Least Squares (PLS) Regression Plugin for OpenMinitab.
Handles collinear & high-dimensional predictors using NIPALS/SIMPLS decomposition, cross-validated Q2, and Variable Importance in Projection (VIP).
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class PlsParams(BaseModel):
    response_y: str = Field(
        ...,
        description="Response Variable (Continuous Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    predictors_x: List[str] = Field(
        ...,
        description="Predictor Variables (X Matrix)",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )
    num_components: int = Field(2, ge=1, le=20, description="Number of PLS Components (Default: 2)")
    cross_validation: str = Field(
        "leave_one_out",
        description="Cross-Validation Method",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Leave-One-Out Cross Validation (LOOCV)", "value": "leave_one_out"},
                {"label": "5-Fold Cross Validation", "value": "5_fold"},
                {"label": "None", "value": "none"}
            ]
        }
    )


def nipals_pls(X_orig: np.ndarray, y_orig: np.ndarray, n_comp: int):
    """Exact NIPALS algorithm for Partial Least Squares Regression."""
    n, p = X_orig.shape
    X = X_orig.copy()
    y = y_orig.copy().reshape(-1, 1)

    T = np.zeros((n, n_comp))
    P = np.zeros((p, n_comp))
    W = np.zeros((p, n_comp))
    Q = np.zeros(n_comp)

    for a in range(n_comp):
        w = X.T @ y
        w_norm = np.linalg.norm(w)
        if w_norm < 1e-12:
            break
        w = w / w_norm
        t = X @ w
        t_norm_sq = float(np.squeeze(t.T @ t))
        if t_norm_sq < 1e-12:
            break
        p_vec = (X.T @ t) / t_norm_sq
        q_val = float(np.squeeze(y.T @ t) / t_norm_sq)

        T[:, a] = t.flatten()
        P[:, a] = p_vec.flatten()
        W[:, a] = w.flatten()
        Q[a] = q_val

        # Deflation
        X = X - np.outer(t, p_vec)
        y = y - t * q_val

    # Regression coefficients: B = W(P^T W)^{-1} Q
    PW = P.T @ W
    try:
        B = W @ np.linalg.pinv(PW) @ Q
    except Exception:
        B = np.zeros(p)

    return T, P, W, Q, B


class PartialLeastSquaresPlugin(AnalysisPlugin):
    id = "partial_least_squares"
    name = "Partial Least Squares (PLS)"
    menu_path = ["Stat", "Regression", "Partial Least Squares"]
    description = "Extracts latent factors from collinear predictor matrices and computes Variable Importance in Projection (VIP) scores."
    param_schema = PlsParams

    def execute(self, df: pd.DataFrame, params: PlsParams) -> AnalysisResult:
        y_col = params.response_y
        x_cols = [c for c in params.predictors_x if c in df.columns]

        if y_col not in df.columns:
            raise ValueError(f"Response column '{y_col}' not found in active worksheet.")
        if len(x_cols) < 2:
            raise ValueError("Select at least 2 predictor variables for Partial Least Squares.")

        sub_df = df[[y_col] + x_cols].dropna().copy().reset_index(drop=True)
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        for c in x_cols:
            sub_df[c] = pd.to_numeric(sub_df[c], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n = len(sub_df)
        p = len(x_cols)
        if n < 4:
            raise ValueError("Partial Least Squares requires at least 4 observations.")

        n_comp = min(params.num_components, p, n - 1)

        y_raw = sub_df[y_col].to_numpy(dtype=float)
        X_raw = sub_df[x_cols].to_numpy(dtype=float)

        # Standardize (Center and Scale)
        x_mean, x_std = np.mean(X_raw, axis=0), np.std(X_raw, axis=0, ddof=1)
        x_std[x_std < 1e-12] = 1.0
        X_std = (X_raw - x_mean) / x_std

        y_mean, y_std = float(np.mean(y_raw)), float(np.std(y_raw, ddof=1))
        y_std = max(1e-12, y_std)
        y_std_arr = (y_raw - y_mean) / y_std

        # Run NIPALS PLS
        T, P, W, Q, B_std = nipals_pls(X_std, y_std_arr, n_comp)

        # Transform coefficients back to unstandardized scale
        B_unstd = (B_std / x_std) * y_std
        intercept = y_mean - float(np.sum(B_unstd * x_mean))

        # Model Variance Explained
        ss_y_tot = float(np.sum((y_raw - y_mean) ** 2))
        y_pred = X_std @ B_std * y_std + y_mean
        ss_res = float(np.sum((y_raw - y_pred) ** 2))
        r_sq_y = max(0.0, 1.0 - ss_res / ss_y_tot) if ss_y_tot > 1e-12 else 1.0

        # Variance of X explained per component
        ss_x_tot = float(np.sum(X_std ** 2))
        r2_x_comp = []
        r2_y_comp = []
        for a in range(n_comp):
            t_a = T[:, a]
            p_a = P[:, a]
            q_a = Q[a]
            var_x_a = float(np.sum(np.outer(t_a, p_a) ** 2))
            var_y_a = float(np.sum((t_a * q_a) ** 2))
            r2_x_comp.append((var_x_a / max(1e-12, ss_x_tot)) * 100.0)
            r2_y_comp.append((var_y_a / max(1e-12, len(y_raw))) * 100.0)

        # Cross-Validation Q2 and RMSEP
        rmsep_list = []
        q2_list = []
        comp_range = list(range(1, n_comp + 1))

        if params.cross_validation == "leave_one_out":
            for a in comp_range:
                press_a = 0.0
                for i in range(n):
                    X_cv = np.delete(X_std, i, axis=0)
                    y_cv = np.delete(y_std_arr, i)
                    _, _, _, _, B_cv = nipals_pls(X_cv, y_cv, a)
                    pred_i = float(X_std[i] @ B_cv) * y_std + y_mean
                    press_a += (y_raw[i] - pred_i) ** 2
                rmsep_val = math.sqrt(press_a / n)
                q2_val = max(0.0, 1.0 - press_a / ss_y_tot) if ss_y_tot > 1e-12 else 0.0
                rmsep_list.append(rmsep_val)
                q2_list.append(q2_val)
        else:
            rmsep_list = [math.sqrt(ss_res / n)] * n_comp
            q2_list = [r_sq_y] * n_comp

        # Variable Importance in Projection (VIP)
        # VIP_j = sqrt(p * sum_a (Q_a^2 * ||t_a||^2 * (W_ja/||W_a||)^2) / sum_a (Q_a^2 * ||t_a||^2))
        weights_term = np.zeros(p)
        denom_vip = 0.0
        for a in range(n_comp):
            t_norm_sq = float(np.sum(T[:, a] ** 2))
            score_contrib = (Q[a] ** 2) * t_norm_sq
            denom_vip += score_contrib
            w_col = W[:, a]
            w_norm = np.linalg.norm(w_col)
            if w_norm > 1e-12:
                weights_term += score_contrib * ((w_col / w_norm) ** 2)

        if denom_vip > 1e-12:
            vip_scores = np.sqrt(p * weights_term / denom_vip)
        else:
            vip_scores = np.ones(p)

        # Build Session Log Tables
        coef_rows = []
        for i, cname in enumerate(x_cols):
            coef_rows.append([
                cname,
                f"{B_unstd[i]:.4f}",
                f"{B_std[i]:.4f}",
                f"{vip_scores[i]:.3f}",
                "Important (VIP > 1.0)" if vip_scores[i] >= 1.0 else "Minor"
            ])

        coef_table = TableResult(
            title=f"PLS Regression Coefficients & VIP Scores ({n_comp} Components)",
            headers=["Predictor", "Unstandardized Coef", "Standardized Coef", "VIP Score", "Importance"],
            rows=coef_rows
        )

        comp_rows = []
        cum_x, cum_y = 0.0, 0.0
        for a in range(n_comp):
            cum_x += r2_x_comp[a]
            cum_y += r2_y_comp[a]
            comp_rows.append([
                str(a + 1),
                f"{r2_x_comp[a]:.2f}%",
                f"{cum_x:.2f}%",
                f"{r2_y_comp[a]:.2f}%",
                f"{cum_y:.2f}%",
                f"{q2_list[a] * 100.0:.2f}%",
                f"{rmsep_list[a]:.4f}"
            ])

        model_table = TableResult(
            title="Model Selection and Cross-Validation Summary",
            headers=["Component", "X Variance (%)", "Cumulative X (%)", "Y Variance (%)", "Cumulative Y (%)", "Q-sq (%)", "RMSEP"],
            rows=comp_rows
        )

        # Plotly 3-Panel Composite Dashboard
        plotly_fig = {
            "data": [
                # 1. RMSEP vs Components
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": comp_range,
                    "y": rmsep_list,
                    "name": "RMSEP",
                    "line": {"color": "#0078d4", "width": 2},
                    "marker": {"size": 7},
                    "xaxis": "x1",
                    "yaxis": "y1"
                },

                # 2. Scores Plot (t1 vs t2)
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": T[:, 0].tolist(),
                    "y": T[:, 1].tolist() if n_comp > 1 else [0.0] * n,
                    "name": "Latent Scores (t1 vs t2)",
                    "marker": {"color": "#008450", "size": 6},
                    "xaxis": "x2",
                    "yaxis": "y2"
                },

                # 3. VIP Score Bar Chart
                {
                    "type": "bar",
                    "x": x_cols,
                    "y": vip_scores.tolist(),
                    "name": "VIP Scores",
                    "marker": {"color": ["#d13438" if v >= 1.0 else "#0078d4" for v in vip_scores]},
                    "xaxis": "x3",
                    "yaxis": "y3"
                }
            ],
            "layout": {
                "title": f"Partial Least Squares (PLS) Dashboard for {y_col}",
                "grid": {"rows": 1, "columns": 3, "pattern": "independent"},
                "showlegend": False,
                "margin": {"l": 40, "r": 30, "t": 60, "b": 40}
            }
        }

        return AnalysisResult(
            title=f"Partial Least Squares Regression for {y_col}",
            subtitle=f"{n_comp} Components | R-sq(Y) = {r_sq_y * 100:.2f}% | Top VIP: {x_cols[int(np.argmax(vip_scores))]} ({np.max(vip_scores):.2f})",
            tables=[coef_table, model_table],
            plotly_figure=plotly_fig,
            statistics={
                "r_sq_y": r_sq_y,
                "n_components": n_comp,
                "vip_scores": dict(zip(x_cols, vip_scores.tolist())),
                "intercept": intercept,
                "coefficients": dict(zip(x_cols, B_unstd.tolist()))
            }
        )
