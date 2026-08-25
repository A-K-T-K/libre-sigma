import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class CorrelationParams(BaseModel):
    variables: List[str] = Field(
        ...,
        description="Select 2 or more numeric variables",
        json_schema_extra={"ui_type": "column_multi_picker", "data_type": "numeric"}
    )
    method: str = Field(
        "pearson",
        description="Correlation Type",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Pearson (linear correlation)", "value": "pearson"},
                {"label": "Spearman (monotonic rank correlation)", "value": "spearman"},
            ]
        }
    )
    display_p_values: bool = Field(
        True,
        description="Display P-Values in Correlation Matrix",
        json_schema_extra={"ui_type": "checkbox"}
    )
    confidence_level: float = Field(
        95.0,
        description="Confidence level (%) for pairwise correlations",
        json_schema_extra={"ui_type": "number"}
    )


class CorrelationPlugin(AnalysisPlugin):
    id = "correlation"
    name = "Correlation"
    menu_path = ["Stat", "Basic Statistics", "Correlation"]
    description = "Calculates Pearson and Spearman correlation matrices, p-values, Fisher Z confidence intervals, and correlation heatmaps."
    param_schema = CorrelationParams

    def execute(self, df: pd.DataFrame, params: CorrelationParams) -> AnalysisResult:
        if len(params.variables) < 2:
            raise ValueError("Correlation requires at least 2 numeric variables.")

        valid_vars = [v for v in params.variables if v in df.columns]
        if len(valid_vars) < 2:
            raise ValueError("At least 2 selected variables must exist in the active worksheet.")

        sub_df = df[valid_vars].apply(pd.to_numeric, errors="coerce")
        clean_df = sub_df.dropna()
        n = len(clean_df)
        if n < 3:
            raise ValueError(f"Correlation requires at least 3 complete cases (found {n}).")

        k = len(valid_vars)
        corr_mat = np.ones((k, k))
        pval_mat = np.zeros((k, k))
        pairwise_rows = []

        conf = params.confidence_level / 100.0
        z_crit = stats.norm.ppf(1.0 - (1.0 - conf) / 2.0)

        for i in range(k):
            for j in range(k):
                if i == j:
                    corr_mat[i, j] = 1.0
                    pval_mat[i, j] = 0.0
                else:
                    x = clean_df[valid_vars[i]].to_numpy(dtype=float)
                    y = clean_df[valid_vars[j]].to_numpy(dtype=float)
                    if params.method == "spearman":
                        res = stats.spearmanr(x, y)
                        r = float(res.statistic) if hasattr(res, "statistic") else float(res[0])
                        p = float(res.pvalue) if hasattr(res, "pvalue") else float(res[1])
                    else:
                        res = stats.pearsonr(x, y)
                        r = float(res.statistic) if hasattr(res, "statistic") else float(res[0])
                        p = float(res.pvalue) if hasattr(res, "pvalue") else float(res[1])

                    corr_mat[i, j] = r
                    pval_mat[i, j] = p

                    if i < j:
                        # Fisher Z CI for Pearson
                        if params.method == "pearson" and abs(r) < 1.0 and n > 3:
                            z_r = np.arctanh(r)
                            se_z = 1.0 / np.sqrt(n - 3)
                            ci_low = np.tanh(z_r - z_crit * se_z)
                            ci_high = np.tanh(z_r + z_crit * se_z)
                            ci_str = f"({ci_low:.4f}, {ci_high:.4f})"
                        else:
                            ci_str = "—"

                        pairwise_rows.append([
                            f"{valid_vars[i]} and {valid_vars[j]}",
                            n,
                            f"{r:.4f}",
                            ci_str,
                            f"{p:.4f}"
                        ])

        # Matrix Table (Minitab Style lower triangle)
        matrix_headers = [""] + valid_vars[:-1]
        matrix_rows = []
        for i in range(1, k):
            row_r = [valid_vars[i]]
            row_p = [""]
            for j in range(i):
                r_val = corr_mat[i, j]
                p_val = pval_mat[i, j]
                row_r.append(f"{r_val:.3f}")
                row_p.append(f"({p_val:.3f})" if params.display_p_values else "")
            matrix_rows.append(row_r)
            if params.display_p_values:
                matrix_rows.append(row_p)

        text_lines = [
            f"Correlation: {', '.join(valid_vars)}",
            f"Method: {params.method.capitalize()}",
            "",
            "Pairwise Correlations:",
            f"  {'Sample 1 & Sample 2':<30} {'N':>5} {'Correlation':>12} {f'{params.confidence_level}% CI':>25} {'P-Value':>10}",
            f"  {'-'*30} {'-'*5} {'-'*12} {'-'*25} {'-'*10}",
        ]
        for pr in pairwise_rows:
            text_lines.append(f"  {pr[0]:<30} {pr[1]:>5} {pr[2]:>12} {pr[3]:>25} {pr[4]:>10}")

        # Heatmap Plot
        plot_data = [
            {
                "type": "heatmap",
                "z": corr_mat.tolist(),
                "x": valid_vars,
                "y": valid_vars,
                "zmin": -1.0,
                "zmax": 1.0,
                "colorscale": [
                    [0.0, "#dc2626"],
                    [0.5, "#ffffff"],
                    [1.0, "#2563eb"],
                ],
                "hoverongaps": False,
            }
        ]

        layout = {
            "title": {"text": f"<b>{params.method.capitalize()} Correlation Matrix</b>", "x": 0.5},
            "margin": {"l": 100, "r": 50, "t": 70, "b": 70},
            "height": max(420, 100 + k * 45),
            "xaxis": {"tickangle": -30},
            "yaxis": {"autorange": "reversed"},
        }

        return AnalysisResult(
            title="Correlation",
            subtitle=f"{params.method.capitalize()} Correlation Matrix",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title=f"{params.method.capitalize()} Correlation Matrix", headers=matrix_headers, rows=matrix_rows),
                TableResult(title="Pairwise Pearson Correlations", headers=["Variables", "N", "Correlation", f"{params.confidence_level}% CI", "P-Value"], rows=pairwise_rows)
            ],
            statistics={"n": n, "method": params.method},
            plotly_figure={"data": plot_data, "layout": layout}
        )
