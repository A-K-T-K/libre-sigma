import numpy as np
import pandas as pd
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from ...base import AnalysisPlugin, AnalysisResult, TableResult


class PcaParams(BaseModel):
    variables: List[str] = Field(..., description="Continuous numeric columns to analyze")
    matrix_type: str = Field("Correlation Matrix", description="Analyze Correlation or Covariance matrix")
    num_components_to_extract: Optional[int] = Field(None, description="Number of PCs to retain (default: Kaiser rule eigenvalue > 1)")
    storage_options: bool = Field(False, description="Store PC scores (SCORE1, SCORE2, ...) in active worksheet")


class PrincipalComponentAnalysisPlugin(AnalysisPlugin):
    id: str = "pca"
    name: str = "Principal Components Analysis"
    menu_path: List[str] = ["Stat", "Multivariate", "Principal Components..."]
    description: str = "Perform Eigen-decomposition of correlation or covariance matrix with Scree, Score, Loading, and Biplot visualizations."
    param_schema: type[BaseModel] = PcaParams

    def execute(self, df: pd.DataFrame, params: PcaParams) -> AnalysisResult:
        var_cols = [c for c in params.variables if c in df.columns]
        if len(var_cols) < 2:
            raise ValueError("PCA requires at least 2 valid numeric columns.")

        clean_df = df[var_cols].dropna()
        n, p = clean_df.shape
        if n < 3:
            raise ValueError("PCA requires at least 3 rows of complete data.")

        X = clean_df.values.astype(float)
        means = np.mean(X, axis=0)
        stds = np.std(X, axis=0, ddof=1)
        stds = np.where(stds == 0, 1.0, stds)

        is_corr = "correlation" in params.matrix_type.lower()

        if is_corr:
            # Standardized matrix
            Z = (X - means) / stds
            # Sample correlation matrix
            matrix = np.corrcoef(X, rowvar=False)
            matrix_title = "Correlation Matrix"
        else:
            # Centered matrix
            Z = X - means
            # Sample covariance matrix
            matrix = np.cov(X, rowvar=False, ddof=1)
            matrix_title = "Covariance Matrix"

        # Eigen-decomposition
        eigenvalues, eigenvectors = np.linalg.eigh(matrix)
        # Sort in descending order
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]

        # Prevent negative near-zero values
        eigenvalues = np.maximum(0.0, eigenvalues)
        total_var = np.sum(eigenvalues)
        proportions = eigenvalues / total_var if total_var > 0 else np.zeros(p)
        cumulative = np.cumsum(proportions)

        # Kaiser criterion or user specified
        if params.num_components_to_extract and params.num_components_to_extract > 0:
            k = min(p, params.num_components_to_extract)
        elif is_corr:
            k = int(np.sum(eigenvalues >= 1.0))
            k = max(1, min(k, p))
        else:
            k = min(p, 3)

        pc_names = [f"PC{i+1}" for i in range(p)]
        extracted_pc_names = pc_names[:k]

        # Component Scores: Z * V
        scores = Z @ eigenvectors[:, :k]

        # 1. Eigenanalysis Table
        eigen_headers = ["Metric"] + pc_names
        eigen_rows = [
            ["Eigenvalue"] + [f"{ev:.4f}" for ev in eigenvalues],
            ["Proportion"] + [f"{prop:.4f}" for prop in proportions],
            ["Cumulative"] + [f"{cum:.4f}" for cum in cumulative],
        ]
        eigen_table = TableResult(
            title=f"Eigenanalysis of the {matrix_title}",
            headers=eigen_headers,
            rows=eigen_rows
        )

        # 2. Eigenvectors / Loadings Table
        loadings_headers = ["Variable"] + pc_names
        loadings_rows = []
        for i, vname in enumerate(var_cols):
            row = [vname] + [f"{eigenvectors[i, j]:.4f}" for j in range(p)]
            loadings_rows.append(row)

        loadings_table = TableResult(
            title="Eigenvectors (Component Loadings)",
            headers=loadings_headers,
            rows=loadings_rows
        )

        # Text output summary
        text_lines = [
            f"Principal Component Analysis: {', '.join(var_cols)}",
            f"Matrix Type: {matrix_title} | Observations: {n} | Variables: {p}",
            "",
            f"Eigenanalysis of the {matrix_title}:",
            " ".join([f"{'':<12}"] + [f"{name:>10}" for name in pc_names]),
            " ".join([f"{'Eigenvalue':<12}"] + [f"{ev:>10.4f}" for ev in eigenvalues]),
            " ".join([f"{'Proportion':<12}"] + [f"{prop:>10.4f}" for prop in proportions]),
            " ".join([f"{'Cumulative':<12}"] + [f"{cum:>10.4f}" for cum in cumulative]),
            "",
            "Eigenvectors (Loadings):",
            " ".join([f"{'Variable':<14}"] + [f"{name:>10}" for name in pc_names])
        ]
        for i, vname in enumerate(var_cols):
            text_lines.append(" ".join([f"{vname:<14}"] + [f"{eigenvectors[i, j]:>10.4f}" for j in range(p)]))

        # Visual Plots: 4-in-1 PCA Visualizer (Scree Plot, Score Plot, Loading Plot, Biplot)
        traces: List[Dict[str, Any]] = []

        # Panel 1: Scree Plot (x1, y1)
        traces.append({
            "type": "bar",
            "x": pc_names,
            "y": eigenvalues.tolist(),
            "name": "Eigenvalue",
            "marker": {"color": "#008450", "opacity": 0.75},
            "xaxis": "x1",
            "yaxis": "y1"
        })
        traces.append({
            "type": "scatter",
            "mode": "lines+markers",
            "x": pc_names,
            "y": eigenvalues.tolist(),
            "name": "Scree Profile",
            "line": {"color": "#004d2c", "width": 2},
            "marker": {"size": 7, "color": "#004d2c"},
            "xaxis": "x1",
            "yaxis": "y1"
        })
        if is_corr:
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "x": [pc_names[0], pc_names[-1]],
                "y": [1.0, 1.0],
                "name": "Kaiser Criterion (1.0)",
                "line": {"color": "#d13438", "dash": "dash", "width": 1.5},
                "xaxis": "x1",
                "yaxis": "y1"
            })

        # Panel 2: Score Plot PC1 vs PC2 (x2, y2)
        traces.append({
            "type": "scatter",
            "mode": "markers",
            "x": scores[:, 0].tolist(),
            "y": (scores[:, 1] if k > 1 else np.zeros(n)).tolist(),
            "name": "Observations",
            "marker": {"size": 6, "color": "#0f6cbd", "opacity": 0.8},
            "xaxis": "x2",
            "yaxis": "y2"
        })

        # Panel 3: Loading Plot (x3, y3)
        v1 = eigenvectors[:, 0]
        v2 = eigenvectors[:, 1] if p > 1 else np.zeros(p)
        for i, vname in enumerate(var_cols):
            traces.append({
                "type": "scatter",
                "mode": "lines+text",
                "x": [0, v1[i]],
                "y": [0, v2[i]],
                "text": ["", f" {vname}"],
                "textposition": "top right",
                "textfont": {"size": 10, "color": "#201f1e"},
                "line": {"color": "#008450", "width": 1.5},
                "name": vname,
                "showlegend": False,
                "xaxis": "x3",
                "yaxis": "y3"
            })

        # Panel 4: Biplot (x4, y4)
        # Scaled scores
        max_s = np.max(np.abs(scores[:, :2])) if np.max(np.abs(scores[:, :2])) > 0 else 1.0
        max_v = np.max(np.abs(eigenvectors[:, :2])) if np.max(np.abs(eigenvectors[:, :2])) > 0 else 1.0
        scale_factor = max_s / max_v if max_v > 0 else 1.0

        traces.append({
            "type": "scatter",
            "mode": "markers",
            "x": scores[:, 0].tolist(),
            "y": (scores[:, 1] if k > 1 else np.zeros(n)).tolist(),
            "name": "Scores",
            "marker": {"size": 5, "color": "#881798", "opacity": 0.6},
            "xaxis": "x4",
            "yaxis": "y4"
        })
        for i, vname in enumerate(var_cols):
            traces.append({
                "type": "scatter",
                "mode": "lines+text",
                "x": [0, v1[i] * scale_factor * 0.8],
                "y": [0, v2[i] * scale_factor * 0.8],
                "text": ["", f" {vname}"],
                "textposition": "top right",
                "textfont": {"size": 10, "color": "#d13438"},
                "line": {"color": "#d13438", "width": 2},
                "showlegend": False,
                "xaxis": "x4",
                "yaxis": "y4"
            })

        plotly_figure = {
            "data": traces,
            "layout": {
                "title": f"PCA Visual Analytics: {', '.join(var_cols[:3])}{'...' if len(var_cols) > 3 else ''}",
                "grid": {"rows": 2, "columns": 2, "pattern": "independent"},
                "showlegend": False,
                "margin": {"l": 45, "r": 30, "t": 60, "b": 45},
                "xaxis": {"title": "Component", "domain": [0, 0.46]},
                "yaxis": {"title": "Eigenvalue", "domain": [0.56, 1.0]},
                "xaxis2": {"title": f"PC1 ({proportions[0]*100:.1f}%)", "domain": [0.54, 1.0]},
                "yaxis2": {"title": f"PC2 ({proportions[1]*100 if p > 1 else 0:.1f}%)", "domain": [0.56, 1.0]},
                "xaxis3": {"title": "Loading on PC1", "domain": [0, 0.46], "range": [-1.1, 1.1]},
                "yaxis3": {"title": "Loading on PC2", "domain": [0, 0.44], "range": [-1.1, 1.1]},
                "xaxis4": {"title": "Biplot PC1", "domain": [0.54, 1.0]},
                "yaxis4": {"title": "Biplot PC2", "domain": [0, 0.44]}
            }
        }

        # Storage option: return columns for worksheet injection
        action_type = None
        worksheet_data = None
        if params.storage_options:
            stored_cols = []
            for j in range(k):
                stored_cols.append({
                    "id": f"score_{j+1}",
                    "name": f"SCORE{j+1}",
                    "type": "numeric",
                    "role": "CONTINUOUS",
                    "isLocked": True,
                    "width": 110
                })
            stored_rows = []
            for i in range(n):
                r_dict: Dict[str, Any] = {}
                for j in range(k):
                    r_dict[f"score_{j+1}"] = round(float(scores[i, j]), 4)
                stored_rows.append(r_dict)

            action_type = "worksheet_append_columns"
            worksheet_data = {
                "columns": stored_cols,
                "rows": stored_rows
            }

        return AnalysisResult(
            title=f"Principal Component Analysis: {', '.join(var_cols)}",
            subtitle=f"Retained {k} of {p} components | Total Variance Explained = {cumulative[k-1]*100:.2f}%",
            text_output="\n".join(text_lines),
            tables=[eigen_table, loadings_table],
            plotly_figure=plotly_figure,
            action_type=action_type,
            worksheet_data=worksheet_data,
            statistics={
                "eigenvalues": eigenvalues.tolist(),
                "proportions": proportions.tolist(),
                "cumulative": cumulative.tolist(),
                "num_components_extracted": k,
                "matrix_type": matrix_title,
                "variables": var_cols
            }
        )
