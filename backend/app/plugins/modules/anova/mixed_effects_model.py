"""
Mixed Effects Model Plugin for OpenMinitab.
Fits linear mixed models with fixed effects, random intercepts/slopes, REML variance components, and BLUPs.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats, optimize
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class MixedEffectsParams(BaseModel):
    response_column: str = Field(
        ...,
        description="Response Variable (Continuous Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    fixed_factors: List[str] = Field(
        ...,
        description="Fixed Effect Variables",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )
    group_column: str = Field(
        ...,
        description="Subject / Grouping Variable (for Random Intercepts)",
        json_schema_extra={"ui_type": "column_picker"}
    )


class MixedEffectsPlugin(AnalysisPlugin):
    id = "mixed_effects_model"
    name = "Mixed Effects Model"
    menu_path = ["Stat", "ANOVA", "Mixed Effects Model"]
    description = "Fits linear mixed effects models (REML) combining fixed population effects with subject/cluster random intercepts."
    param_schema = MixedEffectsParams

    def execute(self, df: pd.DataFrame, params: MixedEffectsParams) -> AnalysisResult:
        y_col = params.response_column
        grp_col = params.group_column
        fixed_cols = [f for f in params.fixed_factors if f in df.columns]

        if y_col not in df.columns or grp_col not in df.columns or not fixed_cols:
            raise ValueError("Select response, grouping (subject), and at least one fixed effect variable.")

        sub_df = df[[y_col, grp_col] + fixed_cols].dropna().copy().reset_index(drop=True)
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n = len(sub_df)
        if n < 8:
            raise ValueError("Mixed Effects Model requires at least 8 observations.")

        groups = sorted(sub_df[grp_col].unique())
        k_groups = len(groups)
        if k_groups < 2:
            raise ValueError("Grouping variable must contain at least 2 distinct subjects/clusters.")

        y = sub_df[y_col].to_numpy(dtype=float)

        # Build Design Matrix X for fixed effects
        col_list = [np.ones(n, dtype=float)]
        term_names = ["Intercept"]

        for f in fixed_cols:
            if pd.api.types.is_numeric_dtype(sub_df[f]):
                col_list.append(sub_df[f].to_numpy(dtype=float))
                term_names.append(f)
            else:
                lvls = sorted(sub_df[f].unique())
                for lvl in lvls[1:]:
                    col_list.append((sub_df[f] == lvl).astype(float).to_numpy())
                    term_names.append(f"{f}_{lvl}")

        X_mat = np.column_stack(col_list)
        p = X_mat.shape[1]

        # Group indices
        grp_indices = [np.where(sub_df[grp_col] == g)[0] for g in groups]

        # REML Profile Likelihood Optimization for variance ratio gamma = var_group / var_res
        def reml_objective(log_gamma):
            gamma = math.exp(log_gamma)
            # Construct Block Diagonal V = I + gamma * Z Z^T
            # Fast inversion by Sherman-Morrison for each group
            log_det_V = 0.0
            log_det_XtVinvX = 0.0
            Xt_Vinv_y = np.zeros(p)
            Xt_Vinv_X = np.zeros((p, p))

            for idxs in grp_indices:
                n_i = len(idxs)
                X_i = X_mat[idxs]
                y_i = y[idxs]
                # V_i = I + gamma * 1 1^T => V_i^-1 = I - (gamma / (1 + n_i*gamma)) 1 1^T
                factor = gamma / (1.0 + n_i * gamma)
                log_det_V += math.log(1.0 + n_i * gamma)

                # y_i^T V_i^-1 y_i = sum(y_i^2) - factor * (sum(y_i))^2
                # X_i^T V_i^-1 y_i = X_i^T y_i - factor * sum(y_i) * (sum_rows(X_i))
                sum_y = np.sum(y_i)
                sum_X = np.sum(X_i, axis=0)

                Xt_Vinv_y += X_i.T @ y_i - factor * sum_y * sum_X
                Xt_Vinv_X += X_i.T @ X_i - factor * np.outer(sum_X, sum_X)

            beta_hat = np.linalg.pinv(Xt_Vinv_X) @ Xt_Vinv_y
            log_det_XtVinvX = np.linalg.slogdet(Xt_Vinv_X)[1]

            # Residual SS via V^-1
            res_quad = 0.0
            for idxs in grp_indices:
                n_i = len(idxs)
                X_i = X_mat[idxs]
                y_i = y[idxs]
                e_i = y_i - X_i @ beta_hat
                factor = gamma / (1.0 + n_i * gamma)
                res_quad += np.sum(e_i ** 2) - factor * (np.sum(e_i) ** 2)

            sigma_e_sq = res_quad / (n - p)
            reml_crit = 0.5 * ((n - p) * math.log(sigma_e_sq) + log_det_V + log_det_XtVinvX + (n - p))
            return reml_crit

        opt_res = optimize.minimize_scalar(reml_objective, bounds=(-10.0, 10.0), method="bounded")
        gamma_opt = math.exp(opt_res.x)

        # Compute Final Parameter Estimates
        Xt_Vinv_y = np.zeros(p)
        Xt_Vinv_X = np.zeros((p, p))
        for idxs in grp_indices:
            n_i = len(idxs)
            X_i = X_mat[idxs]
            y_i = y[idxs]
            factor = gamma_opt / (1.0 + n_i * gamma_opt)
            sum_y = np.sum(y_i)
            sum_X = np.sum(X_i, axis=0)
            Xt_Vinv_y += X_i.T @ y_i - factor * sum_y * sum_X
            Xt_Vinv_X += X_i.T @ X_i - factor * np.outer(sum_X, sum_X)

        cov_beta_unscaled = np.linalg.pinv(Xt_Vinv_X)
        beta_final = cov_beta_unscaled @ Xt_Vinv_y

        res_quad = 0.0
        blups = []
        for i, idxs in enumerate(grp_indices):
            n_i = len(idxs)
            X_i = X_mat[idxs]
            y_i = y[idxs]
            e_i = y_i - X_i @ beta_final
            factor = gamma_opt / (1.0 + n_i * gamma_opt)
            res_quad += np.sum(e_i ** 2) - factor * (np.sum(e_i) ** 2)
            # BLUP: b_i = (gamma / (1 + n_i * gamma)) * sum(e_i)
            blup_i = factor * np.sum(e_i)
            blups.append(blup_i)

        var_resid = float(res_quad / max(1, n - p))
        var_group = float(gamma_opt * var_resid)
        var_total = var_resid + var_group
        icc = (var_group / var_total) * 100.0

        cov_beta = var_resid * cov_beta_unscaled
        se_beta = np.sqrt(np.maximum(1e-12, np.diag(cov_beta)))
        z_stats = beta_final / np.maximum(1e-12, se_beta)
        df_satterthwaite = max(1, k_groups - 1)
        p_vals = [float(2.0 * (1.0 - stats.t.cdf(abs(z), df=df_satterthwaite))) for z in z_stats]

        # Build Session Log Tables
        fixed_rows = []
        for i, tname in enumerate(term_names):
            ci_low = beta_final[i] - 1.96 * se_beta[i]
            ci_high = beta_final[i] + 1.96 * se_beta[i]
            fixed_rows.append([
                tname,
                f"{beta_final[i]:.4f}",
                f"{se_beta[i]:.4f}",
                f"{z_stats[i]:.2f}",
                f"{p_vals[i]:.4f}" if p_vals[i] >= 0.0001 else "< 0.0001",
                f"({ci_low:.4f}, {ci_high:.4f})"
            ])

        fixed_table = TableResult(
            title="Fixed Effects Parameter Estimates",
            headers=["Effect", "Estimate", "SE", "t-Value", "p-Value", "95% CI"],
            rows=fixed_rows
        )

        var_comp_table = TableResult(
            title="Variance Components (REML Estimates)",
            headers=["Component", "Variance", "StdDev", "% of Total Variance"],
            rows=[
                [f"Random Intercept: {grp_col}", f"{var_group:.4f}", f"{math.sqrt(var_group):.4f}", f"{icc:.2f}%"],
                ["Residual Error", f"{var_resid:.4f}", f"{math.sqrt(var_resid):.4f}", f"{100.0 - icc:.2f}%"],
                ["Total Variance", f"{var_total:.4f}", f"{math.sqrt(var_total):.4f}", "100.00%"]
            ]
        )

        # Plotly BLUPs Caterpillar / Subject Prediction Plot
        blup_order = np.argsort(blups)
        plotly_fig = {
            "data": [
                {
                    "type": "bar",
                    "x": [str(groups[i]) for i in blup_order],
                    "y": [float(blups[i]) for i in blup_order],
                    "name": "BLUP (Random Intercept Deviation)",
                    "marker": {"color": "#0078d4"}
                }
            ],
            "layout": {
                "title": f"Best Linear Unbiased Predictors (BLUPs) by {grp_col}",
                "xaxis": {"title": grp_col, "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": "Random Intercept Effect (b_i)", "showgrid": True, "gridcolor": "#ececec"},
            }
        }

        return AnalysisResult(
            title=f"Mixed Effects Model: {y_col}",
            subtitle=f"REML Estimation | ICC = {icc:.2f}% | Var({grp_col}) = {var_group:.4f} | Var(Resid) = {var_resid:.4f}",
            tables=[fixed_table, var_comp_table],
            plotly_figure=plotly_fig,
            statistics={
                "var_random_intercept": var_group,
                "var_residual": var_resid,
                "icc": icc,
                "fixed_coefficients": dict(zip(term_names, beta_final.tolist())),
                "num_groups": k_groups
            }
        )
