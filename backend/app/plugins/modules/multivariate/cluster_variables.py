import numpy as np
import pandas as pd
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from scipy.spatial.distance import squareform
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
from ...base import AnalysisPlugin, AnalysisResult, TableResult


class ClusterVarsParams(BaseModel):
    variables: List[str] = Field(..., description="Continuous numeric variables to cluster")
    linkage_method: str = Field("Average", description="Linkage: Average, Complete, Single, Ward, Centroid")
    distance_metric: str = Field("Correlation (1 - r)", description="Distance measure: Correlation (1 - r) or Absolute Correlation (1 - |r|)")
    num_clusters: int = Field(2, description="Number of final variable clusters to partition")


class ClusterVariablesPlugin(AnalysisPlugin):
    id: str = "cluster_variables"
    name: str = "Cluster Variables"
    menu_path: List[str] = ["Stat", "Multivariate", "Cluster Variables..."]
    description: str = "Hierarchical clustering of variables based on correlation matrix distance space."
    param_schema: type[BaseModel] = ClusterVarsParams

    def execute(self, df: pd.DataFrame, params: ClusterVarsParams) -> AnalysisResult:
        var_cols = [c for c in params.variables if c in df.columns]
        if len(var_cols) < 3:
            raise ValueError("Clustering variables requires at least 3 numeric columns.")

        clean_df = df[var_cols].dropna()
        n, p = clean_df.shape
        if n < 3:
            raise ValueError("Clustering variables requires at least 3 rows of complete data.")

        k_clusters = max(1, min(params.num_clusters, p))

        # Correlation matrix
        R = clean_df.corr().values

        # Distance matrix
        is_abs = "absolute" in params.distance_metric.lower()
        if is_abs:
            D = 1.0 - np.abs(R)
        else:
            D = 1.0 - R

        # Ensure diagonal is zero and symmetric
        np.fill_diagonal(D, 0.0)
        D = np.clip(D, 0.0, 2.0)
        D = 0.5 * (D + D.T)

        dist_condensed = squareform(D)

        link_map = {
            "average": "average",
            "complete": "complete",
            "single": "single",
            "ward": "ward",
            "centroid": "centroid",
        }
        l_method = link_map.get(params.linkage_method.lower(), "average")

        Z_link = linkage(dist_condensed, method=l_method)

        # Cluster labels for variables
        var_cluster_labels = fcluster(Z_link, t=k_clusters, criterion="maxclust")

        # Amalgamation Schedule
        max_dist = float(np.max(Z_link[:, 2])) if len(Z_link) > 0 else 1.0
        amalg_rows = []
        for step in range(len(Z_link)):
            c1 = int(Z_link[step, 0])
            c2 = int(Z_link[step, 1])
            name1 = var_cols[c1] if c1 < p else f"Cluster {c1 + 1}"
            name2 = var_cols[c2] if c2 < p else f"Cluster {c2 + 1}"
            dist = float(Z_link[step, 2])
            n_vars = int(Z_link[step, 3])
            sim_level = max(0.0, 100.0 * (1.0 - dist / max_dist)) if max_dist > 0 else 100.0
            amalg_rows.append([
                str(step + 1),
                str(p - step - 1),
                f"{sim_level:.2f}%",
                f"{dist:.4f}",
                name1,
                name2,
                str(n_vars)
            ])

        amalg_table = TableResult(
            title=f"Amalgamation Schedule for Variables ({params.linkage_method} Linkage)",
            headers=["Step", "Clusters Left", "Similarity", "Distance", "Joined Var 1", "Joined Var 2", "Vars in Cluster"],
            rows=amalg_rows
        )

        # Variable Partition Summary Table
        part_rows = []
        for i, vname in enumerate(var_cols):
            c_id = int(var_cluster_labels[i])
            part_rows.append([
                vname,
                f"Cluster {c_id}"
            ])

        part_table = TableResult(
            title=f"Variable Cluster Membership ({k_clusters} Clusters)",
            headers=["Variable", "Assigned Cluster"],
            rows=part_rows
        )

        # Dendrogram computation for variables
        dendro = dendrogram(Z_link, labels=var_cols, no_plot=True)
        icoord = dendro["icoord"]
        dcoord = dendro["dcoord"]
        ivl = dendro["ivl"]

        traces: List[Dict[str, Any]] = []
        for xs, ys in zip(icoord, dcoord):
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "x": xs,
                "y": ys,
                "line": {"color": "#008450", "width": 2},
                "showlegend": False,
                "hoverinfo": "none"
            })

        # Cutoff line
        if k_clusters > 1 and len(Z_link) >= k_clusters:
            cutoff_dist = float(Z_link[-(k_clusters - 1), 2])
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "x": [min(min(x) for x in icoord), max(max(x) for x in icoord)],
                "y": [cutoff_dist, cutoff_dist],
                "name": f"Partition Threshold (k={k_clusters})",
                "line": {"color": "#d13438", "dash": "dash", "width": 2}
            })

        # Create leaf label ticks
        tickvals = [5 + 10 * i for i in range(len(ivl))]

        plotly_figure = {
            "data": traces,
            "layout": {
                "title": f"Variable Dendrogram: {params.linkage_method} Linkage, {params.distance_metric}",
                "showlegend": True,
                "margin": {"l": 50, "r": 30, "t": 60, "b": 60},
                "xaxis": {
                    "title": "Variables",
                    "tickmode": "array",
                    "tickvals": tickvals,
                    "ticktext": ivl,
                    "tickangle": -30
                },
                "yaxis": {"title": "Correlation Distance"}
            }
        }

        text_lines = [
            f"Hierarchical Clustering of Variables: {', '.join(var_cols)}",
            f"Linkage: {params.linkage_method} | Distance: {params.distance_metric}",
            f"Number of Clusters: {k_clusters}",
            "",
            "Variable Cluster Assignments:",
            f"{'Variable':<16} {'Assigned Cluster':<16}"
        ]
        for row in part_rows:
            text_lines.append(f"{row[0]:<16} {row[1]:<16}")

        return AnalysisResult(
            title=f"Hierarchical Clustering of Variables ({k_clusters} Clusters)",
            subtitle=f"{params.linkage_method} Linkage | {p} Variables Grouped",
            text_output="\n".join(text_lines),
            tables=[part_table, amalg_table],
            plotly_figure=plotly_figure,
            statistics={
                "num_clusters": k_clusters,
                "linkage": params.linkage_method,
                "variables": var_cols,
                "cluster_assignments": {var_cols[i]: int(var_cluster_labels[i]) for i in range(p)}
            }
        )
