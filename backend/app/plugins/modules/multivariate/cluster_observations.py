import numpy as np
import pandas as pd
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from scipy.spatial.distance import pdist, squareform
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
from ...base import AnalysisPlugin, AnalysisResult, TableResult


class ClusterObsParams(BaseModel):
    variables: List[str] = Field(..., description="Continuous numeric variables to cluster")
    linkage_method: str = Field("Average", description="Linkage: Average, Complete, Single, Ward, Centroid, Median")
    distance_metric: str = Field("Euclidean", description="Distance metric: Euclidean, Squared Euclidean, Manhattan")
    standardize_variables: bool = Field(True, description="Standardize variables to zero mean and unit variance")
    num_clusters: int = Field(3, description="Number of final clusters to partition")
    storage_options: bool = Field(False, description="Store cluster membership (CLUST1) in active worksheet")


class ClusterObservationsPlugin(AnalysisPlugin):
    id: str = "cluster_observations"
    name: str = "Cluster Observations"
    menu_path: List[str] = ["Stat", "Multivariate", "Cluster Observations..."]
    description: str = "Perform Hierarchical Agglomerative Clustering on observations with Dendrogram and Amalgamation Schedule."
    param_schema: type[BaseModel] = ClusterObsParams

    def execute(self, df: pd.DataFrame, params: ClusterObsParams) -> AnalysisResult:
        var_cols = [c for c in params.variables if c in df.columns]
        if len(var_cols) < 1:
            raise ValueError("Clustering requires at least 1 numeric column.")

        clean_df = df[var_cols].dropna()
        n, p = clean_df.shape
        if n < 3:
            raise ValueError("Hierarchical clustering requires at least 3 observations.")

        k_clusters = max(1, min(params.num_clusters, n))

        X = clean_df.values.astype(float)
        if params.standardize_variables:
            means = np.mean(X, axis=0)
            stds = np.std(X, axis=0, ddof=1)
            stds = np.where(stds == 0, 1.0, stds)
            Z = (X - means) / stds
        else:
            Z = X.copy()

        # Linkage map
        link_map = {
            "average": "average",
            "complete": "complete",
            "single": "single",
            "ward": "ward",
            "centroid": "centroid",
            "median": "median",
        }
        l_method = link_map.get(params.linkage_method.lower(), "average")

        # Metric map
        metric_map = {
            "euclidean": "euclidean",
            "squared euclidean": "sqeuclidean",
            "manhattan": "cityblock",
        }
        d_metric = metric_map.get(params.distance_metric.lower(), "euclidean")

        # Ward requires euclidean
        if l_method == "ward":
            d_metric = "euclidean"

        # Pairwise distance and linkage matrix
        dist_vec = pdist(Z, metric=d_metric)
        Z_link = linkage(dist_vec, method=l_method)

        # Cut tree to obtain cluster labels
        cluster_labels = fcluster(Z_link, t=k_clusters, criterion="maxclust")

        # Amalgamation Schedule
        # Z_link has shape (n-1, 4): [cluster1, cluster2, distance, num_obs]
        max_dist = float(np.max(Z_link[:, 2])) if len(Z_link) > 0 else 1.0
        amalg_rows = []
        for step in range(len(Z_link)):
            c1 = int(Z_link[step, 0]) + 1
            c2 = int(Z_link[step, 1]) + 1
            dist = float(Z_link[step, 2])
            n_obs = int(Z_link[step, 3])
            sim_level = max(0.0, 100.0 * (1.0 - dist / max_dist)) if max_dist > 0 else 100.0
            amalg_rows.append([
                str(step + 1),
                str(n - step - 1),  # Number of clusters remaining
                f"{sim_level:.2f}%",
                f"{dist:.4f}",
                f"Cluster {c1}",
                f"Cluster {c2}",
                str(n_obs)
            ])

        amalg_table = TableResult(
            title=f"Amalgamation Schedule ({params.linkage_method} Linkage, {params.distance_metric} Distance)",
            headers=["Step", "Clusters Left", "Similarity Level", "Distance", "Joined Cluster 1", "Joined Cluster 2", "New Obs Count"],
            rows=amalg_rows[-15:] if len(amalg_rows) > 15 else amalg_rows  # Show last 15 steps
        )

        # Cluster Summary Table
        cluster_summary_rows = []
        for c_id in range(1, k_clusters + 1):
            mask = cluster_labels == c_id
            c_size = int(np.sum(mask))
            if c_size > 0:
                c_data = Z[mask]
                c_mean = np.mean(c_data, axis=0)
                ss_within = float(np.sum((c_data - c_mean) ** 2))
                dists_from_mean = np.linalg.norm(c_data - c_mean, axis=1)
                avg_dist = float(np.mean(dists_from_mean))
                max_dist_c = float(np.max(dists_from_mean))
                cluster_summary_rows.append([
                    f"Cluster {c_id}",
                    str(c_size),
                    f"{ss_within:.4f}",
                    f"{avg_dist:.4f}",
                    f"{max_dist_c:.4f}"
                ])

        cluster_summary_table = TableResult(
            title=f"Cluster Summary ({k_clusters} Partition Clusters)",
            headers=["Cluster", "Observations", "Within-Cluster SS", "Avg Dist to Centroid", "Max Dist to Centroid"],
            rows=cluster_summary_rows
        )

        # Compute Dendrogram Coordinates for Plotly
        dendro = dendrogram(Z_link, no_plot=True)
        icoord = dendro["icoord"]
        dcoord = dendro["dcoord"]
        ivl = dendro["ivl"]

        traces: List[Dict[str, Any]] = []

        # Color palette for tree
        for xs, ys in zip(icoord, dcoord):
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "x": xs,
                "y": ys,
                "line": {"color": "#008450", "width": 1.5},
                "showlegend": False,
                "hoverinfo": "none"
            })

        # Cutoff line based on k clusters
        if k_clusters > 1 and len(Z_link) >= k_clusters:
            cutoff_dist = float(Z_link[-(k_clusters - 1), 2])
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "x": [min(min(x) for x in icoord), max(max(x) for x in icoord)],
                "y": [cutoff_dist, cutoff_dist],
                "name": f"Partition Cutoff (k={k_clusters})",
                "line": {"color": "#d13438", "dash": "dash", "width": 2}
            })

        plotly_figure = {
            "data": traces,
            "layout": {
                "title": f"Dendrogram: {params.linkage_method} Linkage, {params.distance_metric} Distance ({k_clusters} Clusters)",
                "showlegend": True,
                "margin": {"l": 50, "r": 30, "t": 60, "b": 45},
                "xaxis": {"title": "Observations", "showticklabels": False},
                "yaxis": {"title": "Amalgamation Distance"}
            }
        }

        # Text Summary
        text_lines = [
            f"Hierarchical Clustering of Observations: {', '.join(var_cols)}",
            f"Linkage Method: {params.linkage_method} | Distance: {params.distance_metric} | Standardized: {params.standardize_variables}",
            f"Number of Final Clusters: {k_clusters}",
            "",
            "Final Partition Cluster Summary:",
            f"{'Cluster':<12} {'Obs':>8} {'Within SS':>12} {'Avg Dist':>12} {'Max Dist':>12}"
        ]
        for row in cluster_summary_rows:
            text_lines.append(f"{row[0]:<12} {row[1]:>8} {float(row[2]):>12.4f} {float(row[3]):>12.4f} {float(row[4]):>12.4f}")

        # Storage option: store CLUST1
        action_type = None
        worksheet_data = None
        if params.storage_options:
            stored_cols = [{
                "id": "clust_1",
                "name": "CLUST1",
                "type": "text",
                "role": "CATEGORICAL",
                "isLocked": True,
                "width": 100
            }]
            stored_rows = [{"clust_1": f"Cluster {int(lbl)}"} for lbl in cluster_labels]
            action_type = "worksheet_append_columns"
            worksheet_data = {
                "columns": stored_cols,
                "rows": stored_rows
            }

        return AnalysisResult(
            title=f"Hierarchical Cluster Observations ({k_clusters} Clusters)",
            subtitle=f"{params.linkage_method} Linkage | {params.distance_metric} Metric | {n} Observations",
            text_output="\n".join(text_lines),
            tables=[cluster_summary_table, amalg_table],
            plotly_figure=plotly_figure,
            action_type=action_type,
            worksheet_data=worksheet_data,
            statistics={
                "num_clusters": k_clusters,
                "linkage": params.linkage_method,
                "metric": params.distance_metric,
                "cluster_counts": [int(np.sum(cluster_labels == i)) for i in range(1, k_clusters + 1)],
                "variables": var_cols
            }
        )
