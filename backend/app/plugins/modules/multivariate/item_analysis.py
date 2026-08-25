import numpy as np
import pandas as pd
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from ...base import AnalysisPlugin, AnalysisResult, TableResult


class ItemAnalysisParams(BaseModel):
    item_variables: List[str] = Field(..., description="Survey or test item columns (Likert scale or continuous)")
    storage_options: bool = Field(False, description="Store Total Score (TOTAL_SCORE) in active worksheet")


class ItemAnalysisPlugin(AnalysisPlugin):
    id: str = "item_analysis"
    name: str = "Item Analysis"
    menu_path: List[str] = ["Stat", "Multivariate", "Item Analysis..."]
    description: str = "Evaluate survey reliability with Cronbach's Alpha, Standardized Alpha, and Item-Omitted Diagnostics."
    param_schema: type[BaseModel] = ItemAnalysisParams

    def execute(self, df: pd.DataFrame, params: ItemAnalysisParams) -> AnalysisResult:
        item_cols = [c for c in params.item_variables if c in df.columns]
        if len(item_cols) < 2:
            raise ValueError("Item Analysis requires at least 2 survey item columns.")

        clean_df = df[item_cols].dropna()
        n, k = clean_df.shape
        if n < 3:
            raise ValueError("Item Analysis requires at least 3 completed survey response rows.")

        X = clean_df.values.astype(float)
        item_means = np.mean(X, axis=0)
        item_vars = np.var(X, axis=0, ddof=1)
        item_stds = np.std(X, axis=0, ddof=1)

        total_scores = np.sum(X, axis=1)
        total_mean = float(np.mean(total_scores))
        total_var = float(np.var(total_scores, ddof=1))
        total_std = float(np.std(total_scores, ddof=1))

        sum_item_vars = float(np.sum(item_vars))

        # Overall Cronbach's Alpha
        if total_var > 1e-12:
            overall_alpha = (k / (k - 1.0)) * (1.0 - (sum_item_vars / total_var))
        else:
            overall_alpha = 0.0

        # Standardized Alpha (based on correlation matrix)
        corr_matrix = np.corrcoef(X, rowvar=False)
        tri_indices = np.triu_indices(k, k=1)
        mean_r = float(np.mean(corr_matrix[tri_indices])) if len(tri_indices[0]) > 0 else 0.0
        if 1.0 + (k - 1.0) * mean_r > 1e-12:
            standardized_alpha = (k * mean_r) / (1.0 + (k - 1.0) * mean_r)
        else:
            standardized_alpha = 0.0

        # Item-Omitted Statistics
        omitted_stats = []
        adj_corrs = []
        omitted_alphas = []

        for j in range(k):
            # Omitted total: Sum without item j
            rest_X = np.delete(X, j, axis=1)
            omitted_total = np.sum(rest_X, axis=1)
            omitted_total_var = float(np.var(omitted_total, ddof=1))
            omitted_sum_vars = float(np.sum(item_vars) - item_vars[j])

            # Correlation between item j and omitted total
            if np.std(X[:, j], ddof=1) > 1e-12 and np.std(omitted_total, ddof=1) > 1e-12:
                adj_corr = float(np.corrcoef(X[:, j], omitted_total)[0, 1])
            else:
                adj_corr = 0.0
            adj_corrs.append(adj_corr)

            # Omitted Cronbach's alpha
            if omitted_total_var > 1e-12 and k > 2:
                adj_alpha = ((k - 1.0) / (k - 2.0)) * (1.0 - (omitted_sum_vars / omitted_total_var))
            else:
                adj_alpha = 0.0
            omitted_alphas.append(adj_alpha)

            omitted_stats.append([
                item_cols[j],
                f"{item_means[j]:.4f}",
                f"{item_stds[j]:.4f}",
                f"{adj_corr:.4f}",
                f"{adj_alpha:.4f}"
            ])

        # 1. Scale Summary Table
        summary_table = TableResult(
            title="Scale Reliability Statistics",
            headers=["Total Items", "Sample Size (N)", "Scale Mean", "Scale Std Dev", "Cronbach's Alpha", "Standardized Alpha"],
            rows=[[
                str(k),
                str(n),
                f"{total_mean:.4f}",
                f"{total_std:.4f}",
                f"{overall_alpha:.4f}",
                f"{standardized_alpha:.4f}"
            ]]
        )

        # 2. Item-Omitted Table
        omitted_table = TableResult(
            title="Item and Item-Omitted Statistics",
            headers=["Omitted Item", "Item Mean", "Item StDev", "Adj. Total Corr (r)", "Cronbach's Alpha if Deleted"],
            rows=omitted_stats
        )

        # Plots: Item-Omitted Alpha Bar Plot + Item Mean Profile Plot
        traces: List[Dict[str, Any]] = []

        # Subplot 1: Item-Omitted Alpha Bar Plot (x1, y1)
        bar_colors = ["#d13438" if a > overall_alpha else "#008450" for a in omitted_alphas]
        traces.append({
            "type": "bar",
            "x": item_cols,
            "y": omitted_alphas,
            "name": "Alpha if Item Deleted",
            "marker": {"color": bar_colors},
            "xaxis": "x1",
            "yaxis": "y1"
        })
        traces.append({
            "type": "scatter",
            "mode": "lines",
            "x": [item_cols[0], item_cols[-1]],
            "y": [overall_alpha, overall_alpha],
            "name": f"Overall Alpha ({overall_alpha:.3f})",
            "line": {"color": "#0f6cbd", "dash": "dash", "width": 2},
            "xaxis": "x1",
            "yaxis": "y1"
        })

        # Subplot 2: Item-Adjusted Total Correlation (x2, y2)
        traces.append({
            "type": "scatter",
            "mode": "lines+markers",
            "x": item_cols,
            "y": adj_corrs,
            "name": "Adj. Total Corr",
            "line": {"color": "#881798", "width": 2},
            "marker": {"size": 8, "color": "#881798"},
            "xaxis": "x2",
            "yaxis": "y2"
        })
        traces.append({
            "type": "scatter",
            "mode": "lines",
            "x": [item_cols[0], item_cols[-1]],
            "y": [0.3, 0.3],
            "name": "Acceptable Correlation Cutoff (0.30)",
            "line": {"color": "#605e5c", "dash": "dot", "width": 1},
            "xaxis": "x2",
            "yaxis": "y2"
        })

        plotly_figure = {
            "data": traces,
            "layout": {
                "title": f"Item Reliability Analysis: Cronbach's Alpha = {overall_alpha:.4f}",
                "grid": {"rows": 1, "columns": 2, "pattern": "independent"},
                "showlegend": True,
                "margin": {"l": 50, "r": 30, "t": 60, "b": 45},
                "xaxis": {"title": "Survey Item", "domain": [0, 0.46]},
                "yaxis": {"title": "Cronbach's Alpha if Deleted", "domain": [0, 1.0]},
                "xaxis2": {"title": "Survey Item", "domain": [0.54, 1.0]},
                "yaxis2": {"title": "Item-Adjusted Total Correlation", "domain": [0, 1.0], "range": [-0.1, 1.05]}
            }
        }

        # Text Summary
        text_lines = [
            f"Item Analysis of: {', '.join(item_cols)}",
            f"Number of Items: {k} | Sample Size: {n}",
            f"Total Cronbach's Alpha: {overall_alpha:.4f} | Standardized Alpha: {standardized_alpha:.4f}",
            "",
            "Item-Omitted Statistics:",
            f"{'Item':<14} {'Mean':>10} {'StDev':>10} {'Adj. Total r':>14} {'Alpha if Deleted':>18}"
        ]
        for row in omitted_stats:
            text_lines.append(f"{row[0]:<14} {float(row[1]):>10.4f} {float(row[2]):>10.4f} {float(row[3]):>14.4f} {float(row[4]):>18.4f}")

        # Storage option: store TOTAL_SCORE column
        action_type = None
        worksheet_data = None
        if params.storage_options:
            stored_cols = [{
                "id": "total_score",
                "name": "TOTAL_SCORE",
                "type": "numeric",
                "role": "CONTINUOUS",
                "isLocked": True,
                "width": 110
            }]
            stored_rows = [{"total_score": round(float(ts), 4)} for ts in total_scores]
            action_type = "worksheet_append_columns"
            worksheet_data = {
                "columns": stored_cols,
                "rows": stored_rows
            }

        return AnalysisResult(
            title=f"Item Analysis (Cronbach's Alpha = {overall_alpha:.4f})",
            subtitle=f"{k} Items | Mean Score = {total_mean:.2f} | Standardized Alpha = {standardized_alpha:.4f}",
            text_output="\n".join(text_lines),
            tables=[summary_table, omitted_table],
            plotly_figure=plotly_figure,
            action_type=action_type,
            worksheet_data=worksheet_data,
            statistics={
                "cronbach_alpha": overall_alpha,
                "standardized_alpha": standardized_alpha,
                "scale_mean": total_mean,
                "scale_std": total_std,
                "item_means": item_means.tolist(),
                "adj_correlations": adj_corrs,
                "omitted_alphas": omitted_alphas
            }
        )
