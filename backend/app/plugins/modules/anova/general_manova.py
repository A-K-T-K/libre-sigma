"""
General MANOVA (Multivariate ANOVA) Plugin for OpenMinitab.
Evaluates differences across multiple continuous response vectors using Wilks' Lambda, Pillai's Trace, Hotelling-Lawley Trace, and Roy's Largest Root.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class ManovaParams(BaseModel):
    response_columns: List[str] = Field(
        ...,
        description="Response Variables (Two or more Continuous Y columns)",
        json_schema_extra={"ui_type": "column_multi_picker", "data_type": "numeric"}
    )
    factor_column: str = Field(
        ...,
        description="Factor Variable (Categorical Grouping)",
        json_schema_extra={"ui_type": "column_picker"}
    )


class GeneralManovaPlugin(AnalysisPlugin):
    id = "general_manova"
    name = "General MANOVA"
    menu_path = ["Stat", "ANOVA", "General MANOVA"]
    description = "Tests for equality of multivariate mean vectors using Wilks' Lambda, Pillai's, Hotelling's, and Roy's multivariate test criteria."
    param_schema = ManovaParams

    def execute(self, df: pd.DataFrame, params: ManovaParams) -> AnalysisResult:
        y_cols = [col for col in params.response_columns if col in df.columns]
        f_col = params.factor_column

        if len(y_cols) < 2 or f_col not in df.columns:
            raise ValueError("MANOVA requires at least two numeric response variables and one factor column.")

        sub_df = df[y_cols + [f_col]].dropna().copy().reset_index(drop=True)
        for col in y_cols:
            sub_df[col] = pd.to_numeric(sub_df[col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n = len(sub_df)
        p = len(y_cols) # Number of response variables

        if n < p + 4:
            raise ValueError(f"MANOVA with {p} response variables requires at least {p + 4} observations.")

        groups = sorted(sub_df[f_col].unique())
        k = len(groups) # Number of factor levels

        if k < 2:
            raise ValueError("Factor variable must contain at least 2 distinct levels.")

        # Data Matrices
        Y = sub_df[y_cols].to_numpy(dtype=float)
        grand_mean_vec = np.mean(Y, axis=0)

        # Total SSP Matrix (T)
        Y_centered = Y - grand_mean_vec
        T_mat = Y_centered.T @ Y_centered

        # Hypothesis / Between-Group SSP Matrix (H)
        H_mat = np.zeros((p, p))
        # Error / Within-Group SSP Matrix (E)
        E_mat = np.zeros((p, p))

        for g in groups:
            Y_g = sub_df[sub_df[f_col] == g][y_cols].to_numpy(dtype=float)
            n_g = len(Y_g)
            g_mean_vec = np.mean(Y_g, axis=0)
            diff_mean = (g_mean_vec - grand_mean_vec).reshape(-1, 1)
            H_mat += n_g * (diff_mean @ diff_mean.T)
            Y_g_centered = Y_g - g_mean_vec
            E_mat += Y_g_centered.T @ Y_g_centered

        # Eigenvalues of E^-1 H
        E_inv = np.linalg.pinv(E_mat)
        eigvals = np.sort(np.real(np.linalg.eigvals(E_inv @ H_mat)))[::-1]
        eigvals = np.maximum(0.0, eigvals) # Non-negative roots

        s = min(p, k - 1)
        m = 0.5 * (abs(p - (k - 1)) - 1)
        N_deg = 0.5 * (n - k - p - 1)

        # 1. Wilks' Lambda
        det_E = np.linalg.det(E_mat)
        det_HE = np.linalg.det(H_mat + E_mat)
        wilks_lambda = (det_E / det_HE) if det_HE > 1e-12 else 0.0
        wilks_lambda = max(1e-12, min(1.0, wilks_lambda))

        # Rao's F approximation for Wilks' Lambda
        df_h = k - 1
        df_e = n - k
        w = df_e - 0.5 * (p - df_h + 1)
        t_term = math.sqrt((p**2 * df_h**2 - 4.0) / (p**2 + df_h**2 - 5.0)) if (p**2 + df_h**2 - 5.0) > 0 else 1.0
        df1_wilks = p * df_h
        df2_wilks = w * t_term - 0.5 * (p * df_h - 2.0)
        f_wilks = ((1.0 - wilks_lambda ** (1.0 / t_term)) / (wilks_lambda ** (1.0 / t_term))) * (df2_wilks / df1_wilks)
        p_wilks = float(1.0 - stats.f.cdf(f_wilks, df1_wilks, df2_wilks))

        # 2. Pillai's Trace
        pillai_trace = float(np.sum(eigvals / (1.0 + eigvals)))
        df1_pillai = s * (2 * m + s + 1)
        df2_pillai = s * (2 * N_deg + s + 1)
        f_pillai = (pillai_trace / (s - pillai_trace)) * (df2_pillai / df1_pillai) if (s - pillai_trace) > 1e-12 else 999.0
        p_pillai = float(1.0 - stats.f.cdf(f_pillai, df1_pillai, df2_pillai))

        # 3. Hotelling-Lawley Trace
        hotelling_trace = float(np.sum(eigvals))
        df1_hot = s * (2 * m + s + 1)
        df2_hot = 2 * (s * N_deg + 1)
        f_hot = (hotelling_trace / s) * (df2_hot / df1_hot)
        p_hot = float(1.0 - stats.f.cdf(f_hot, df1_hot, df2_hot))

        # 4. Roy's Largest Root
        roys_root = float(eigvals[0])
        df1_roy = max(p, df_h)
        df2_roy = df_e - df1_roy + df_h
        f_roy = roys_root * (df2_roy / df1_roy)
        p_roy = float(1.0 - stats.f.cdf(f_roy, df1_roy, df2_roy))

        # Build Session Log Tables
        manova_table = TableResult(
            title=f"Multivariate Tests for Factor: {f_col} (Responses: {', '.join(y_cols)})",
            headers=["Test Statistic", "Value", "Approx F", "Num DF", "Denom DF", "p-Value"],
            rows=[
                ["Wilks' Lambda (Λ)", f"{wilks_lambda:.4f}", f"{f_wilks:.2f}", f"{df1_wilks:.0f}", f"{df2_wilks:.0f}", f"{p_wilks:.4f}" if p_wilks >= 0.0001 else "< 0.0001"],
                ["Pillai's Trace (V)", f"{pillai_trace:.4f}", f"{f_pillai:.2f}", f"{df1_pillai:.0f}", f"{df2_pillai:.0f}", f"{p_pillai:.4f}" if p_pillai >= 0.0001 else "< 0.0001"],
                ["Hotelling-Lawley Trace (T)", f"{hotelling_trace:.4f}", f"{f_hot:.2f}", f"{df1_hot:.0f}", f"{df2_hot:.0f}", f"{p_hot:.4f}" if p_hot >= 0.0001 else "< 0.0001"],
                ["Roy's Largest Root (Θ)", f"{roys_root:.4f}", f"{f_roy:.2f}", f"{df1_roy:.0f}", f"{df2_roy:.0f}", f"{p_roy:.4f}" if p_roy >= 0.0001 else "< 0.0001"]
            ]
        )

        # Univariate ANOVA breakdowns
        univ_rows = []
        for i, col in enumerate(y_cols):
            ss_h_i = H_mat[i, i]
            ss_e_i = E_mat[i, i]
            ms_h_i = ss_h_i / max(1, df_h)
            ms_e_i = ss_e_i / max(1, df_e)
            f_i = ms_h_i / max(1e-12, ms_e_i)
            p_i = float(1.0 - stats.f.cdf(f_i, df_h, df_e))
            r_sq_i = ss_h_i / (ss_h_i + ss_e_i) if (ss_h_i + ss_e_i) > 0 else 0.0

            univ_rows.append([
                col,
                f"{ss_h_i:.4f}",
                f"{ss_e_i:.4f}",
                f"{f_i:.2f}",
                f"{p_i:.4f}" if p_i >= 0.0001 else "< 0.0001",
                f"{r_sq_i * 100:.2f}%"
            ])

        univ_table = TableResult(
            title="Univariate ANOVA Summary for Each Response Variable",
            headers=["Response Variable", "Hypothesis SS (H)", "Error SS (E)", "F-Value", "p-Value", "R-sq"],
            rows=univ_rows
        )

        # Plotly Bivariate Scatter Ellipse Plot (First 2 response variables)
        y1_name, y2_name = y_cols[0], y_cols[1]
        traces = []
        for g in groups:
            g_sub = sub_df[sub_df[f_col] == g]
            traces.append({
                "type": "scatter",
                "mode": "markers",
                "x": g_sub[y1_name].tolist(),
                "y": g_sub[y2_name].tolist(),
                "name": f"Group: {g}",
                "marker": {"size": 7}
            })

        plotly_fig = {
            "data": traces,
            "layout": {
                "title": f"Bivariate Response Scatter for {y1_name} vs {y2_name} by {f_col}",
                "xaxis": {"title": y1_name, "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": y2_name, "showgrid": True, "gridcolor": "#ececec"},
            }
        }

        return AnalysisResult(
            title=f"General MANOVA: Responses [{', '.join(y_cols)}] by {f_col}",
            subtitle=f"Wilks' Λ = {wilks_lambda:.4f} (p = {p_wilks:.4f}) | Pillai's V = {pillai_trace:.4f} (p = {p_pillai:.4f})",
            tables=[manova_table, univ_table],
            plotly_figure=plotly_fig,
            statistics={
                "wilks_lambda": wilks_lambda,
                "wilks_f": f_wilks,
                "wilks_p": p_wilks,
                "pillai_trace": pillai_trace,
                "hotelling_trace": hotelling_trace,
                "roys_root": roys_root
            }
        )
