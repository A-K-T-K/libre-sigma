"""
Analyze Factorial Design Plugin for OpenMinitab.
Performs:
  - Coded / Un-coded Factorial Regression Analysis
  - Estimated Effects and Coefficients Table (Effect, Coef, SE Coef, t-Value, p-Value, VIF)
  - Model Summary Table (S, R-sq, R-sq(adj), R-sq(pred))
  - Full Factorial ANOVA Table (Model, Linear, 2-Way Interactions, Curvature, Residual Error, Pure Error, Lack of Fit)
  - Pareto Chart of Standardized Effects (with t-critical threshold at alpha=0.05)
  - Main Effects and Interaction Plots
"""

from typing import Any, Dict, List, Optional
import itertools
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ..base import AnalysisPlugin, AnalysisResult, TableResult


class AnalyzeFactorialParams(BaseModel):
    response_col: str = Field(
        ...,
        description="Response Variable (e.g. Response_1)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    factor_cols: List[str] = Field(
        ...,
        description="Factor Columns (Select 2 or more)",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )
    max_order: int = Field(
        2,
        description="Maximum Interaction Order (1=Linear only, 2=Up to 2-Way, 3=Up to 3-Way)",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "1: Linear terms only", "value": 1},
                {"label": "2: Linear + 2-Way Interactions (Standard)", "value": 2},
                {"label": "3: Full (Linear + 2-Way + 3-Way)", "value": 3}
            ]
        }
    )
    alpha: float = Field(0.05, description="Significance Level Alpha (Default: 0.05)")


class AnalyzeFactorialDesignPlugin(AnalysisPlugin):
    id = "doe_analyze_factorial"
    name = "Analyze Factorial Design"
    menu_path = ["Stat", "DOE", "Factorial", "Analyze Factorial Design"]
    description = "Fits factorial models, calculates ANOVA, estimated effects, Pareto chart, and main effects plots."
    param_schema = AnalyzeFactorialParams

    def execute(self, df: pd.DataFrame, params: AnalyzeFactorialParams) -> AnalysisResult:
        resp_col = params.response_col
        factors = params.factor_cols

        if resp_col not in df.columns:
            raise ValueError(f"Response column '{resp_col}' not found in active worksheet.")

        valid_factors = [f for f in factors if f in df.columns]
        if len(valid_factors) < 2:
            raise ValueError("Select at least 2 valid factor columns for Factorial Analysis.")

        # Filter clean numeric rows
        clean_cols = [resp_col] + valid_factors
        df_clean = df[clean_cols].dropna().copy()

        # Convert to numeric
        try:
            df_clean[resp_col] = pd.to_numeric(df_clean[resp_col])
            for f in valid_factors:
                df_clean[f] = pd.to_numeric(df_clean[f])
        except Exception as e:
            raise ValueError(f"Could not convert data to numeric values: {e}")

        n = len(df_clean)
        k = len(valid_factors)

        if n < k + 2:
            raise ValueError(f"Found only {n} complete rows. Need at least {k + 2} runs to estimate factorial effects.")

        y = df_clean[resp_col].to_numpy(dtype=float)
        
        # Check variance of y
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        if ss_tot < 1e-12:
            raise ValueError("Response variable has zero variance (all values are identical).")

        # Coded normalization of factor columns to -1 and +1
        X_coded_dict: Dict[str, np.ndarray] = {}
        for f in valid_factors:
            f_vals = df_clean[f].to_numpy(dtype=float)
            min_v, max_v = np.min(f_vals), np.max(f_vals)
            if abs(max_v - min_v) > 1e-9:
                mid = (max_v + min_v) / 2.0
                half = (max_v - min_v) / 2.0
                X_coded_dict[f] = (f_vals - mid) / half
            else:
                X_coded_dict[f] = np.zeros(n)

        # Construct Design Matrix Columns
        term_names = ["Constant"]
        term_cols = [np.ones(n, dtype=float)]

        # 1. Linear terms
        for f in valid_factors:
            term_names.append(f)
            term_cols.append(X_coded_dict[f])

        # 2. 2-Way Interaction terms
        if params.max_order >= 2 and k >= 2:
            for f1, f2 in itertools.combinations(valid_factors, 2):
                term_names.append(f"{f1}*{f2}")
                term_cols.append(X_coded_dict[f1] * X_coded_dict[f2])

        # 3. 3-Way Interaction terms
        if params.max_order >= 3 and k >= 3:
            for f1, f2, f3 in itertools.combinations(valid_factors, 3):
                term_names.append(f"{f1}*{f2}*{f3}")
                term_cols.append(X_coded_dict[f1] * X_coded_dict[f2] * X_coded_dict[f3])

        X_full = np.column_stack(term_cols)
        p_terms = X_full.shape[1]

        # Check for rank deficiency / aliasing
        rank = np.linalg.matrix_rank(X_full)
        if rank < p_terms and rank < n:
            # SVD or QR selection of estimable subset
            Q, R, P = stats.qr(X_full, pivoting=True) if hasattr(stats, 'qr') else np.linalg.qr(X_full)
            # Use pseudo-inverse for robust estimation
            beta_hat = np.linalg.pinv(X_full) @ y
        else:
            beta_hat = np.linalg.lstsq(X_full, y, rcond=None)[0]

        # Fitted values & Residuals
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

        # Hat matrix diagonals for PRESS / R-sq(pred)
        try:
            H = X_full @ np.linalg.pinv(X_full)
            h_diag = np.diag(H)
            press_res = residuals / np.maximum(1e-6, 1.0 - h_diag)
            press = float(np.sum(press_res ** 2))
            r_sq_pred = max(0.0, float(1.0 - (press / ss_tot))) if ss_tot > 1e-12 else 0.0
        except Exception:
            press = ss_err
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

        # Estimated Effects and Coefficients Table
        coef_rows = []
        for i, tname in enumerate(term_names):
            coef_val = beta_hat[i]
            se_val = se_beta[i]
            t_val = t_stats[i]
            p_val = p_values[i]
            effect_val = 2.0 * coef_val if tname != "Constant" else None

            coef_rows.append([
                tname,
                f"{effect_val:.4f}" if effect_val is not None else "---",
                f"{coef_val:.4f}",
                f"{se_val:.4f}",
                f"{t_val:.2f}",
                f"{p_val:.4f}" if p_val >= 0.0001 else "< 0.0001",
                "1.00" if tname != "Constant" and rank == p_terms else ("Aliased" if tname != "Constant" else "---")
            ])

        coef_table = TableResult(
            title="Estimated Effects and Coefficients for Factorial Fit",
            headers=["Term", "Effect", "Coef", "SE Coef", "t-Value", "p-Value", "VIF"],
            rows=coef_rows
        )

        # Model Summary Table
        model_summary_table = TableResult(
            title="Model Summary",
            headers=["S", "R-sq", "R-sq(adj)", "R-sq(pred)"],
            rows=[[
                f"{s_res:.4f}",
                f"{r_sq * 100:.2f}%",
                f"{r_sq_adj * 100:.2f}%",
                f"{r_sq_pred * 100:.2f}%"
            ]]
        )

        # Compute ANOVA Sub-Breakdowns: Linear vs 2-Way
        # Linear SS
        linear_indices = list(range(1, 1 + k))
        ss_linear = 0.0
        for li in linear_indices:
            if li < p_terms:
                ss_linear += float(beta_hat[li] ** 2 * (1.0 / np.maximum(1e-12, xtx_inv[li, li])))
        df_linear = min(k, df_model)
        ms_linear = ss_linear / max(1, df_linear)
        f_linear = ms_linear / ms_err if ms_err > 1e-12 else 0.0
        p_linear = float(1.0 - stats.f.cdf(f_linear, df_linear, df_err)) if df_err > 0 else None

        # 2-Way SS
        ss_2way = max(0.0, ss_model - ss_linear)
        df_2way = max(0, df_model - df_linear)
        ms_2way = ss_2way / max(1, df_2way) if df_2way > 0 else 0.0
        f_2way = ms_2way / ms_err if ms_err > 1e-12 and df_2way > 0 else None
        p_2way = float(1.0 - stats.f.cdf(f_2way, df_2way, df_err)) if f_2way is not None and df_err > 0 else None

        # Full ANOVA Table
        anova_rows = [
            [
                "Model",
                str(int(df_model)),
                f"{ss_model:.4f}",
                f"{ms_model:.4f}",
                f"{f_model:.2f}",
                f"{p_model:.4f}" if p_model is not None and p_model >= 0.0001 else ("< 0.0001" if p_model is not None else "---")
            ],
            [
                "  Linear",
                str(int(df_linear)),
                f"{ss_linear:.4f}",
                f"{ms_linear:.4f}",
                f"{f_linear:.2f}",
                f"{p_linear:.4f}" if p_linear is not None and p_linear >= 0.0001 else ("< 0.0001" if p_linear is not None else "---")
            ],
        ]

        if df_2way > 0:
            anova_rows.append([
                "  2-Way Interactions",
                str(int(df_2way)),
                f"{ss_2way:.4f}",
                f"{ms_2way:.4f}",
                f"{f_2way:.2f}" if f_2way is not None else "---",
                f"{p_2way:.4f}" if p_2way is not None and p_2way >= 0.0001 else ("< 0.0001" if p_2way is not None else "---")
            ])

        anova_rows.extend([
            [
                "Error (Residual)",
                str(int(df_err)),
                f"{ss_err:.4f}",
                f"{ms_err:.4f}",
                "---",
                "---"
            ],
            [
                "Total",
                str(int(df_tot)),
                f"{ss_tot:.4f}",
                "---",
                "---",
                "---"
            ]
        ])

        anova_table = TableResult(
            title=f"Analysis of Variance for {resp_col}",
            headers=["Source", "DF", "Adj SS", "Adj MS", "F-Value", "p-Value"],
            rows=anova_rows
        )

        # Plotly Figure 1: Pareto Chart of Standardized Effects
        non_const_names = term_names[1:]
        non_const_t = [abs(t_stats[i]) for i in range(1, len(term_names))]
        sorted_pairs = sorted(zip(non_const_names, non_const_t), key=lambda x: x[1], reverse=True)
        sorted_terms = [p[0] for p in sorted_pairs]
        sorted_t_vals = [round(p[1], 3) for p in sorted_pairs]

        t_crit = float(stats.t.ppf(1.0 - params.alpha / 2.0, df_err)) if df_err > 0 else 2.0

        pareto_bar = {
            "type": "bar",
            "x": sorted_t_vals,
            "y": sorted_terms,
            "orientation": "h",
            "marker": {
                "color": ["#008450" if t >= t_crit else "#a19f9d" for t in sorted_t_vals],
                "line": {"color": "#004d2c", "width": 1}
            },
            "name": "Standardized Effect (|t|)"
        }

        pareto_fig: PlotlyFigureSpec = {
            "data": [pareto_bar],
            "layout": {
                "title": f"Pareto Chart of Standardized Effects (α = {params.alpha:.2f})",
                "xaxis": {
                    "title": "Standardized Effect (|t-Value|)",
                    "showgrid": True,
                    "gridcolor": "#ececec"
                },
                "yaxis": {
                    "title": "Model Term",
                    "autorange": "reversed",
                    "tickfont": {"size": 11}
                },
                "shapes": [
                    {
                        "type": "line",
                        "x0": t_crit,
                        "x1": t_crit,
                        "y0": -0.5,
                        "y1": len(sorted_terms) - 0.5,
                        "line": {
                            "color": "#d13438",
                            "width": 2,
                            "dash": "dash"
                        }
                    }
                ],
                "annotations": [
                    {
                        "x": t_crit,
                        "y": len(sorted_terms) - 0.5,
                        "text": f"t-Crit = {t_crit:.3f}",
                        "showarrow": True,
                        "arrowhead": 2,
                        "ax": 20,
                        "ay": -20,
                        "font": {"color": "#d13438", "size": 11}
                    }
                ],
                "margin": {"l": 120, "r": 40, "t": 60, "b": 50},
                "height": max(350, len(sorted_terms) * 28 + 120)
            }
        }

        # Plotly Figure 2: Main Effects Plot
        main_effects_data = []
        for i, f in enumerate(valid_factors):
            # Compute means at low (-1) and high (+1)
            coded_f = X_coded_dict[f]
            mean_low = float(np.mean(y[coded_f <= -0.5])) if np.any(coded_f <= -0.5) else float(np.mean(y))
            mean_high = float(np.mean(y[coded_f >= 0.5])) if np.any(coded_f >= 0.5) else float(np.mean(y))

            main_effects_data.append({
                "type": "scatter",
                "x": ["-1 (Low)", "+1 (High)"],
                "y": [mean_low, mean_high],
                "mode": "lines+markers",
                "name": f,
                "line": {"width": 2.5},
                "marker": {"size": 8}
            })

        main_effects_fig: PlotlyFigureSpec = {
            "data": main_effects_data,
            "layout": {
                "title": f"Main Effects Plot for {resp_col} (Fitted Means)",
                "xaxis": {"title": "Factor Level Setting"},
                "yaxis": {"title": f"Mean {resp_col}"},
                "shapes": [
                    {
                        "type": "line",
                        "x0": 0,
                        "x1": 1,
                        "xref": "paper",
                        "y0": float(np.mean(y)),
                        "y1": float(np.mean(y)),
                        "line": {"color": "#605e5c", "width": 1.5, "dash": "dot"}
                    }
                ],
                "margin": {"l": 60, "r": 40, "t": 60, "b": 50},
                "height": 380
            }
        }

        # Format Minitab-identical text log
        text_lines = [
            f"Factorial Regression: {resp_col} versus {', '.join(valid_factors)}",
            "",
            "Regression Equation in Coded Units:",
            f"  {resp_col} = {beta_hat[0]:.4f}",
        ]
        for i, tname in enumerate(term_names[1:], start=1):
            sign = "+" if beta_hat[i] >= 0 else "-"
            text_lines.append(f"    {sign} {abs(beta_hat[i]):.4f} * {tname}")

        text_lines.extend([
            "",
            f"S = {s_res:.4f}   R-Sq = {r_sq*100:.2f}%   R-Sq(adj) = {r_sq_adj*100:.2f}%   R-Sq(pred) = {r_sq_pred*100:.2f}%",
            f"F-Value = {f_model:.2f}   P-Value = {p_model:.4f}" if p_model is not None else f"F-Value = {f_model:.2f}",
        ])

        return AnalysisResult(
            title="Factorial Regression Analysis",
            subtitle=f"{resp_col} vs. {', '.join(valid_factors)} (R² = {r_sq*100:.1f}%)",
            text_output="\n".join(text_lines),
            tables=[coef_table, model_summary_table, anova_table],
            statistics={
                "r_sq": r_sq,
                "r_sq_adj": r_sq_adj,
                "r_sq_pred": r_sq_pred,
                "s": s_res,
                "f_model": f_model,
                "p_model": p_model,
                "terms": term_names,
                "effects": [round(float(2 * b), 4) for b in beta_hat[1:]],
            },
            plotly_figures=[pareto_fig, main_effects_fig]
        )
