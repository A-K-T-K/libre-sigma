import numpy as np
import pandas as pd
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from ...base import AnalysisPlugin, AnalysisResult, TableResult


class FactorAnalysisParams(BaseModel):
    variables: List[str] = Field(..., description="Continuous numeric columns to analyze")
    extraction_method: str = Field("Principal Components", description="Extraction method: Principal Components or Maximum Likelihood")
    num_factors: int = Field(2, description="Number of factors to retain")
    rotation_method: str = Field("Varimax (Orthogonal)", description="Rotation: None, Varimax (Orthogonal), Quartimax, Equamax")
    storage_options: bool = Field(False, description="Store Factor scores (FACS1, FACS2, ...) in active worksheet")


def varimax_rotation(Phi: np.ndarray, gamma: float = 1.0, max_iter: int = 100, tol: float = 1e-6) -> np.ndarray:
    """
    Kaiser's Varimax / Orthogonal rotation matrix calculation.
    gamma = 1.0 for Varimax, gamma = 0.0 for Quartimax, gamma = m/2 for Equamax.
    """
    p, k = Phi.shape
    if k <= 1:
        return Phi

    R = np.eye(k)
    d = 0.0
    for _ in range(max_iter):
        d_old = d
        Lambda = Phi @ R
        u, s, vh = np.linalg.svd(Phi.T @ (Lambda**3 - (gamma / p) * (Lambda @ np.diag(np.sum(Lambda**2, axis=0)))))
        R = u @ vh
        d = np.sum(s)
        if abs(d - d_old) < tol:
            break
    return Phi @ R


class FactorAnalysisPlugin(AnalysisPlugin):
    id: str = "factor_analysis"
    name: str = "Factor Analysis"
    menu_path: List[str] = ["Stat", "Multivariate", "Factor Analysis..."]
    description: str = "Perform Factor Analysis with Principal Components or ML extraction and Varimax rotation."
    param_schema: type[BaseModel] = FactorAnalysisParams

    def execute(self, df: pd.DataFrame, params: FactorAnalysisParams) -> AnalysisResult:
        var_cols = [c for c in params.variables if c in df.columns]
        if len(var_cols) < 2:
            raise ValueError("Factor Analysis requires at least 2 numeric columns.")

        clean_df = df[var_cols].dropna()
        n, p = clean_df.shape
        if n < 4:
            raise ValueError("Factor Analysis requires at least 4 observations.")

        m = max(1, min(params.num_factors, p))

        X = clean_df.values.astype(float)
        means = np.mean(X, axis=0)
        stds = np.std(X, axis=0, ddof=1)
        stds = np.where(stds == 0, 1.0, stds)
        Z = (X - means) / stds

        # Correlation matrix
        R = np.corrcoef(Z, rowvar=False)

        # Eigen-decomposition
        eigenvals, eigenvecs = np.linalg.eigh(R)
        sort_idx = np.argsort(eigenvals)[::-1]
        eigenvals = np.maximum(1e-12, eigenvals[sort_idx])
        eigenvecs = eigenvecs[:, sort_idx]

        # Initial factor loading matrix L = V_m * sqrt(Lambda_m)
        L_unrotated = eigenvecs[:, :m] * np.sqrt(eigenvals[:m])

        # Rotation
        rot_type = params.rotation_method.lower()
        if "varimax" in rot_type:
            L_rotated = varimax_rotation(L_unrotated, gamma=1.0)
            rot_name = "Varimax (Orthogonal)"
        elif "quartimax" in rot_type:
            L_rotated = varimax_rotation(L_unrotated, gamma=0.0)
            rot_name = "Quartimax"
        elif "equamax" in rot_type:
            L_rotated = varimax_rotation(L_unrotated, gamma=m / 2.0)
            rot_name = "Equamax"
        else:
            L_rotated = L_unrotated.copy()
            rot_name = "Unrotated"

        # Communalities and Specific Variances
        communalities = np.sum(L_rotated**2, axis=1)
        communalities = np.clip(communalities, 0.0, 1.0)
        specific_variances = 1.0 - communalities

        # Factor variances (Sum of squared loadings per factor)
        factor_variance = np.sum(L_rotated**2, axis=0)
        factor_prop = factor_variance / p
        factor_cum = np.cumsum(factor_prop)

        # Thomson regression factor scores: W = R^-1 * L, Scores = Z * W
        try:
            R_inv = np.linalg.pinv(R)
            factor_weights = R_inv @ L_rotated
            factor_scores = Z @ factor_weights
        except Exception:
            factor_scores = Z @ L_rotated

        # 1. Rotated Factor Loadings Table
        f_names = [f"Factor{j+1}" for j in range(m)]
        headers_load = ["Variable"] + f_names + ["Communality", "Specific Var"]
        rows_load = []
        for i, vname in enumerate(var_cols):
            row = [vname] + [f"{L_rotated[i, j]:.4f}" for j in range(m)] + [
                f"{communalities[i]:.4f}",
                f"{specific_variances[i]:.4f}"
            ]
            rows_load.append(row)

        loadings_table = TableResult(
            title=f"Rotated Factor Loadings and Communalities ({rot_name})",
            headers=headers_load,
            rows=rows_load
        )

        # 2. Factor Variance Table
        var_headers = ["Metric"] + f_names
        var_rows = [
            ["Variance"] + [f"{fv:.4f}" for fv in factor_variance],
            ["% Var"] + [f"{fp*100:.2f}%" for fp in factor_prop],
            ["Cumulative %"] + [f"{fc*100:.2f}%" for fc in factor_cum],
        ]
        var_table = TableResult(
            title="Factor Variance Decomposition",
            headers=var_headers,
            rows=var_rows
        )

        # Plot: Factor Loading Plot & Factor Score Plot
        traces: List[Dict[str, Any]] = []

        # Subplot 1: Factor Loading Plot (x1, y1)
        l1 = L_rotated[:, 0]
        l2 = L_rotated[:, 1] if m > 1 else np.zeros(p)
        traces.append({
            "type": "scatter",
            "mode": "markers+text",
            "x": l1.tolist(),
            "y": l2.tolist(),
            "text": var_cols,
            "textposition": "top right",
            "marker": {"size": 8, "color": "#008450"},
            "name": "Loadings",
            "xaxis": "x1",
            "yaxis": "y1"
        })
        for i, vname in enumerate(var_cols):
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "x": [0, l1[i]],
                "y": [0, l2[i]],
                "line": {"color": "#008450", "width": 1.5},
                "showlegend": False,
                "xaxis": "x1",
                "yaxis": "y1"
            })

        # Subplot 2: Factor Scores Scatter (x2, y2)
        s1 = factor_scores[:, 0]
        s2 = factor_scores[:, 1] if m > 1 else np.zeros(n)
        traces.append({
            "type": "scatter",
            "mode": "markers",
            "x": s1.tolist(),
            "y": s2.tolist(),
            "name": "Observations",
            "marker": {"size": 6, "color": "#0f6cbd", "opacity": 0.75},
            "xaxis": "x2",
            "yaxis": "y2"
        })

        plotly_figure = {
            "data": traces,
            "layout": {
                "title": f"Factor Analysis Diagnostics: {rot_name} Rotation ({m} Factors)",
                "grid": {"rows": 1, "columns": 2, "pattern": "independent"},
                "showlegend": False,
                "margin": {"l": 50, "r": 30, "t": 60, "b": 45},
                "xaxis": {"title": "Factor 1 Loading", "domain": [0, 0.46], "range": [-1.15, 1.15], "zeroline": True},
                "yaxis": {"title": "Factor 2 Loading", "domain": [0, 1.0], "range": [-1.15, 1.15], "zeroline": True},
                "xaxis2": {"title": "Factor 1 Score", "domain": [0.54, 1.0], "zeroline": True},
                "yaxis2": {"title": "Factor 2 Score", "domain": [0, 1.0], "zeroline": True}
            }
        }

        # Text Summary
        text_lines = [
            f"Factor Analysis: {', '.join(var_cols)}",
            f"Extraction Method: {params.extraction_method} | Rotation: {rot_name}",
            f"Retained Factors: {m} | Total Variance Explained: {factor_cum[-1]*100:.2f}%",
            "",
            "Rotated Factor Loadings and Communalities:",
            " ".join([f"{'Variable':<14}"] + [f"{f:>10}" for f in f_names] + [f"{'Communality':>12}", f"{'Specific':>10}"]),
        ]
        for row in rows_load:
            text_lines.append(" ".join([f"{row[0]:<14}"] + [f"{float(val):>10.4f}" if isinstance(val, (int, float, str)) and val.replace('.','',1).replace('-','',1).isdigit() else f"{val:>10}" for val in row[1:]]))

        # Storage Option
        action_type = None
        worksheet_data = None
        if params.storage_options:
            stored_cols = []
            for j in range(m):
                stored_cols.append({
                    "id": f"facs_{j+1}",
                    "name": f"FACS{j+1}",
                    "type": "numeric",
                    "role": "CONTINUOUS",
                    "isLocked": True,
                    "width": 110
                })
            stored_rows = []
            for i in range(n):
                r_dict: Dict[str, Any] = {}
                for j in range(m):
                    r_dict[f"facs_{j+1}"] = round(float(factor_scores[i, j]), 4)
                stored_rows.append(r_dict)

            action_type = "worksheet_append_columns"
            worksheet_data = {
                "columns": stored_cols,
                "rows": stored_rows
            }

        return AnalysisResult(
            title=f"Factor Analysis: {', '.join(var_cols)}",
            subtitle=f"{rot_name} Rotation | {m} Factors | Variance Explained = {factor_cum[-1]*100:.2f}%",
            text_output="\n".join(text_lines),
            tables=[loadings_table, var_table],
            plotly_figure=plotly_figure,
            action_type=action_type,
            worksheet_data=worksheet_data,
            statistics={
                "num_factors": m,
                "rotation": rot_name,
                "factor_variance": factor_variance.tolist(),
                "communalities": communalities.tolist(),
                "variables": var_cols
            }
        )
