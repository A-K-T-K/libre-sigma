import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class CovarianceParams(BaseModel):
    variables: List[str] = Field(
        ...,
        description="Select 2 or more numeric variables",
        json_schema_extra={"ui_type": "column_multi_picker", "data_type": "numeric"}
    )


class CovariancePlugin(AnalysisPlugin):
    id = "covariance"
    name = "Covariance"
    menu_path = ["Stat", "Basic Statistics", "Covariance"]
    description = "Calculates the sample covariance matrix for numeric variables."
    param_schema = CovarianceParams

    def execute(self, df: pd.DataFrame, params: CovarianceParams) -> AnalysisResult:
        if len(params.variables) < 2:
            raise ValueError("Covariance requires at least 2 numeric variables.")

        valid_vars = [v for v in params.variables if v in df.columns]
        if len(valid_vars) < 2:
            raise ValueError("At least 2 selected variables must exist in the active worksheet.")

        sub_df = df[valid_vars].apply(pd.to_numeric, errors="coerce")
        clean_df = sub_df.dropna()
        n = len(clean_df)
        if n < 2:
            raise ValueError(f"Covariance requires at least 2 complete rows (found {n}).")

        cov_matrix = clean_df.cov().to_numpy()
        k = len(valid_vars)

        matrix_headers = [""] + valid_vars
        matrix_rows = []
        for i in range(k):
            row = [valid_vars[i]]
            for j in range(k):
                row.append(f"{cov_matrix[i, j]:.4f}")
            matrix_rows.append(row)

        text_lines = [
            f"Covariances: {', '.join(valid_vars)}",
            f"Sample size N = {n}",
            "",
            f"  {'':<15} " + "".join(f"{v:>14}" for v in valid_vars),
            f"  {'-'*15} " + "".join(f"{'-'*14}" for _ in valid_vars),
        ]
        for r in matrix_rows:
            text_lines.append(f"  {r[0]:<15} " + "".join(f"{str(val):>14}" for val in r[1:]))

        # Heatmap
        plot_data = [
            {
                "type": "heatmap",
                "z": cov_matrix.tolist(),
                "x": valid_vars,
                "y": valid_vars,
                "colorscale": "Blues",
            }
        ]

        layout = {
            "title": {"text": "<b>Covariance Matrix</b>", "x": 0.5},
            "margin": {"l": 100, "r": 50, "t": 70, "b": 70},
            "height": max(420, 100 + k * 45),
            "xaxis": {"tickangle": -30},
            "yaxis": {"autorange": "reversed"},
        }

        return AnalysisResult(
            title="Covariance",
            subtitle=f"{len(valid_vars)} Variables (N={n})",
            text_output="\n".join(text_lines),
            tables=[TableResult(title="Covariance Matrix", headers=matrix_headers, rows=matrix_rows)],
            statistics={"n": n},
            plotly_figure={"data": plot_data, "layout": layout}
        )
