import numpy as np
import pandas as pd
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from sklearn.cluster import KMeans
from scipy.spatial import ConvexHull
from ...base import AnalysisPlugin, AnalysisResult, TableResult


class ClusterKMeansParams(BaseModel):
    variables: List[str] = Field(..., description="Continuous numeric variables for K-Means clustering")
    number_of_clusters: int = Field(3, description="Number of clusters K (>= 2)")
    standardize: bool = Field(True, description="Standardize variables to zero mean and unit variance")
    max_iterations: int = Field(100, description="Maximum iterations for centroid convergence")
    storage_options: bool = Field(False, description="Store cluster membership (KCLUST1) in active worksheet")


class ClusterKMeansPlugin(AnalysisPlugin):
    id: str = "cluster_kmeans"
    name: str = "Cluster K-Means"
    menu_path: List[str] = ["Stat", "Multivariate", "Cluster K-Means..."]
    description: str = "Perform K-Means clustering with Centroid Profile plots, Within/Between Sum of Squares, and 2D Projection."
    param_schema: type[BaseModel] = ClusterKMeansParams

    def execute(self, df: pd.DataFrame, params: ClusterKMeansParams) -> AnalysisResult:
        var_cols = [c for c in params.variables if c in df.columns]
        if len(var_cols) < 1:
            raise ValueError("K-Means requires at least 1 numeric column.")

        clean_df = df[var_cols].dropna()
        n, p = clean_df.shape
        if n < 4:
            raise ValueError("K-Means requires at least 4 observations.")

        K = max(2, min(params.number_of_clusters, n - 1))

        X = clean_df.values.astype(float)
        if params.standardize:
            means = np.mean(X, axis=0)
            stds = np.std(X, axis=0, ddof=1)
            stds = np.where(stds == 0, 1.0, stds)
            Z = (X - means) / stds
        else:
            Z = X.copy()

        # Run K-Means
        kmeans = KMeans(
            n_clusters=K,
            max_iter=params.max_iterations,
            n_init=10,
            random_state=42
        )
        labels = kmeans.fit_predict(Z)
        centroids_Z = kmeans.cluster_centers_

        # Unstandardized centroids for reporting
        if params.standardize:
            centroids_orig = centroids_Z * stds + means
        else:
            centroids_orig = centroids_Z

        # Sum of Squares decomposition
        overall_mean = np.mean(Z, axis=0)
        ss_total = float(np.sum((Z - overall_mean) ** 2))
        ss_within_total = float(kmeans.inertia_)

        cluster_counts = []
        ss_within_clusters = []
        avg_dists = []
        max_dists = []

        for k in range(K):
            mask = labels == k
            cnt = int(np.sum(mask))
            cluster_counts.append(cnt)
            if cnt > 0:
                c_pts = Z[mask]
                c_center = centroids_Z[k]
                ss_k = float(np.sum((c_pts - c_center) ** 2))
                ss_within_clusters.append(ss_k)
                dists = np.linalg.norm(c_pts - c_center, axis=1)
                avg_dists.append(float(np.mean(dists)))
                max_dists.append(float(np.max(dists)))
            else:
                ss_within_clusters.append(0.0)
                avg_dists.append(0.0)
                max_dists.append(0.0)

        ss_between = max(0.0, ss_total - ss_within_total)
        prop_between = (ss_between / ss_total * 100.0) if ss_total > 1e-12 else 0.0

        # Distance between centroids
        dist_between_centroids = np.zeros((K, K))
        for i in range(K):
            for j in range(K):
                dist_between_centroids[i, j] = np.linalg.norm(centroids_Z[i] - centroids_Z[j])

        # 1. Cluster Summary Table
        summary_rows = []
        for k in range(K):
            summary_rows.append([
                f"Cluster {k+1}",
                str(cluster_counts[k]),
                f"{ss_within_clusters[k]:.4f}",
                f"{avg_dists[k]:.4f}",
                f"{max_dists[k]:.4f}"
            ])

        summary_table = TableResult(
            title=f"K-Means Cluster Summary (K = {K})",
            headers=["Cluster", "Observations", "Within-Cluster SS", "Average Distance", "Max Distance"],
            rows=summary_rows
        )

        # 2. Final Cluster Centroids Table
        centroid_headers = ["Variable"] + [f"Cluster {k+1}" for k in range(K)]
        centroid_rows = []
        for j, vname in enumerate(var_cols):
            row = [vname] + [f"{centroids_orig[k, j]:.4f}" for k in range(K)]
            centroid_rows.append(row)

        centroid_table = TableResult(
            title="Final Cluster Centroids",
            headers=centroid_headers,
            rows=centroid_rows
        )

        # 3. Inter-Cluster Centroid Distance Table
        dist_headers = ["Cluster"] + [f"Cluster {k+1}" for k in range(K)]
        dist_rows = []
        for i in range(K):
            row = [f"Cluster {i+1}"] + [f"{dist_between_centroids[i, j]:.4f}" for j in range(K)]
            dist_rows.append(row)

        dist_table = TableResult(
            title="Distances Between Final Cluster Centroids",
            headers=dist_headers,
            rows=dist_rows
        )

        # Visual Plots: Profile Plot (Parallel coordinates of centroids) + 2D PCA Projected Scatter
        traces: List[Dict[str, Any]] = []
        color_palette = ["#008450", "#0f6cbd", "#d13438", "#881798", "#ffaa44", "#00b7c3", "#775533"]

        # Subplot 1: Centroid Profile Plot (x1, y1)
        for k in range(K):
            c_color = color_palette[k % len(color_palette)]
            traces.append({
                "type": "scatter",
                "mode": "lines+markers",
                "x": var_cols,
                "y": centroids_orig[k].tolist(),
                "name": f"Cluster {k+1} ({cluster_counts[k]} obs)",
                "line": {"color": c_color, "width": 2},
                "marker": {"size": 8, "color": c_color},
                "xaxis": "x1",
                "yaxis": "y1"
            })

        # Subplot 2: 2D Projected Scatter via PCA (x2, y2)
        if p >= 2:
            # Perform PCA on Z for 2D visualization
            cov_mat = np.cov(Z, rowvar=False)
            evals, evecs = np.linalg.eigh(cov_mat)
            idx = np.argsort(evals)[::-1]
            evecs = evecs[:, idx]
            proj_2d = Z @ evecs[:, :2]
            proj_centers = centroids_Z @ evecs[:, :2]
        else:
            proj_2d = np.column_stack([Z, np.random.normal(0, 0.05, size=n)])
            proj_centers = np.column_stack([centroids_Z, np.zeros(K)])

        for k in range(K):
            c_color = color_palette[k % len(color_palette)]
            mask = labels == k
            pts_k = proj_2d[mask]
            traces.append({
                "type": "scatter",
                "mode": "markers",
                "x": pts_k[:, 0].tolist(),
                "y": pts_k[:, 1].tolist(),
                "name": f"Cluster {k+1} Data",
                "marker": {"size": 6, "color": c_color, "opacity": 0.75},
                "showlegend": False,
                "xaxis": "x2",
                "yaxis": "y2"
            })

            # Convex hull if >= 3 points
            if len(pts_k) >= 3:
                try:
                    hull = ConvexHull(pts_k)
                    hull_pts = pts_k[hull.vertices]
                    # Close the loop
                    hull_pts = np.vstack([hull_pts, hull_pts[0]])
                    traces.append({
                        "type": "scatter",
                        "mode": "lines",
                        "x": hull_pts[:, 0].tolist(),
                        "y": hull_pts[:, 1].tolist(),
                        "line": {"color": c_color, "dash": "dot", "width": 1.5},
                        "fill": "toself",
                        "fillcolor": f"rgba(0, 132, 80, 0.06)",
                        "showlegend": False,
                        "xaxis": "x2",
                        "yaxis": "y2"
                    })
                except Exception:
                    pass

            # Centroid marker
            traces.append({
                "type": "scatter",
                "mode": "markers+text",
                "x": [proj_centers[k, 0]],
                "y": [proj_centers[k, 1]],
                "text": [f"C{k+1}"],
                "textposition": "top center",
                "marker": {"size": 12, "color": c_color, "symbol": "diamond-cross", "line": {"color": "#201f1e", "width": 1.5}},
                "showlegend": False,
                "xaxis": "x2",
                "yaxis": "y2"
            })

        plotly_figure = {
            "data": traces,
            "layout": {
                "title": f"K-Means Clustering Analytics (K = {K} Clusters | SS Between/Total = {prop_between:.2f}%)",
                "grid": {"rows": 1, "columns": 2, "pattern": "independent"},
                "showlegend": True,
                "margin": {"l": 50, "r": 30, "t": 60, "b": 45},
                "xaxis": {"title": "Variables (Centroid Profiles)", "domain": [0, 0.46]},
                "yaxis": {"title": "Centroid Value (Original Units)"},
                "xaxis2": {"title": "Principal Component 1", "domain": [0.54, 1.0]},
                "yaxis2": {"title": "Principal Component 2"}
            }
        }

        # Text Summary
        text_lines = [
            f"K-Means Clustering: {', '.join(var_cols)}",
            f"Number of Clusters: {K} | Total Observations: {n}",
            f"Total SS: {ss_total:.4f} | Within SS: {ss_within_total:.4f} | Between SS: {ss_between:.4f} ({prop_between:.2f}%)",
            "",
            "Cluster Summary:",
            f"{'Cluster':<12} {'Obs':>8} {'Within SS':>12} {'Avg Dist':>12} {'Max Dist':>12}"
        ]
        for row in summary_rows:
            text_lines.append(f"{row[0]:<12} {row[1]:>8} {float(row[2]):>12.4f} {float(row[3]):>12.4f} {float(row[4]):>12.4f}")

        # Storage option: store KCLUST1
        action_type = None
        worksheet_data = None
        if params.storage_options:
            stored_cols = [{
                "id": "kclust_1",
                "name": "KCLUST1",
                "type": "text",
                "role": "CATEGORICAL",
                "isLocked": True,
                "width": 100
            }]
            stored_rows = [{"kclust_1": f"Cluster {int(lbl) + 1}"} for lbl in labels]
            action_type = "worksheet_append_columns"
            worksheet_data = {
                "columns": stored_cols,
                "rows": stored_rows
            }

        return AnalysisResult(
            title=f"K-Means Clustering Analysis (K = {K})",
            subtitle=f"{n} Observations | Between-Cluster SS = {prop_between:.2f}% | Total SS = {ss_total:.2f}",
            text_output="\n".join(text_lines),
            tables=[summary_table, centroid_table, dist_table],
            plotly_figure=plotly_figure,
            action_type=action_type,
            worksheet_data=worksheet_data,
            statistics={
                "num_clusters": K,
                "ss_total": ss_total,
                "ss_within": ss_within_total,
                "ss_between": ss_between,
                "prop_between": prop_between,
                "cluster_counts": cluster_counts,
                "variables": var_cols
            }
        )
