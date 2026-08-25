"""
Box-Cox Transformation Plugin for OpenMinitab.
Transforms strictly positive non-normal time series or process data into approximately normal distribution.
Computes optimal Lambda (λ) with 95% Confidence Interval and Log-Likelihood curve, and stores transformed column into worksheet.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class BoxCoxParams(BaseModel):
    variable: str = Field(
        ...,
        description="Variable (strictly positive values)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    lambda_mode: str = Field(
        "optimal",
        description="Transformation Parameter Lambda (λ)",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Estimate Optimal Lambda (λ)", "value": "optimal"},
                {"label": "User-Specified Lambda (e.g. 0 for ln, 0.5 for sqrt, -1 for inverse)", "value": "user"}
            ]
        }
    )
    user_lambda: float = Field(
        0.0,
        description="User-Specified Lambda (λ)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Interval (%) for Lambda",
        json_schema_extra={"sub_modal": "Options..."}
    )
    store_column_name: str = Field(
        "Transformed",
        description="Store Transformed Series in (Column Name)"
    )


class BoxCoxPlugin(AnalysisPlugin):
    id = "ts_box_cox"
    name = "Box-Cox Transformation"
    menu_path = ["Stat", "Time Series", "Box-Cox Transformation"]
    description = "Estimates optimal Box-Cox transformation parameter Lambda (λ) to normalize positive time series data."
    param_schema = BoxCoxParams

    def execute(self, df: pd.DataFrame, params: BoxCoxParams) -> AnalysisResult:
        var_name = params.variable
        if var_name not in df.columns:
            raise ValueError(f"Column '{var_name}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[var_name], errors="coerce").dropna()
        n = len(raw_series)
        if n < 5:
            raise ValueError("Box-Cox transformation requires at least 5 positive observations.")

        y = raw_series.to_numpy(dtype=float)
        if np.any(y <= 0):
            min_val = float(np.min(y))
            raise ValueError(f"Box-Cox transformation requires all strictly positive values (min found: {min_val}).")

        # Estimate optimal lambda
        opt_lambda = float(stats.boxcox_normmax(y, method="mle", brack=(-3.0, 3.0)))
        
        # Calculate Log-Likelihood curve across lambda range
        lam_grid = np.linspace(opt_lambda - 2.5, opt_lambda + 2.5, 100)
        llf_grid = [stats.boxcox_llf(lam_val, y) for lam_val in lam_grid]
        max_llf = stats.boxcox_llf(opt_lambda, y)
        
        # 95% CI cutoff for log-likelihood: max_llf - 0.5 * chi2(1, 0.95) = max_llf - 1.92
        alpha = 1.0 - params.confidence_level / 100.0
        chi2_crit = stats.chi2.ppf(1.0 - alpha, df=1)
        llf_cutoff = max_llf - 0.5 * chi2_crit

        # Find CI limits on grid
        valid_ci_lams = [lam_grid[i] for i in range(len(lam_grid)) if llf_grid[i] >= llf_cutoff]
        ci_lower = float(np.min(valid_ci_lams)) if valid_ci_lams else float(opt_lambda - 0.5)
        ci_upper = float(np.max(valid_ci_lams)) if valid_ci_lams else float(opt_lambda + 0.5)

        # Selected lambda
        if params.lambda_mode == "user":
            chosen_lambda = params.user_lambda
            trans_y = stats.boxcox(y, lmbda=chosen_lambda)
            lam_desc = f"User Specified: λ = {chosen_lambda:.4f}"
        else:
            chosen_lambda = float(opt_lambda)
            trans_y = stats.boxcox(y, lmbda=chosen_lambda)
            lam_desc = f"Optimal Estimate: λ = {chosen_lambda:.4f}"

        # Standard rounded Minitab recommendations
        rounded_lambda = round(chosen_lambda * 2) / 2.0  # nearest 0.5

        # Plotly Log-Likelihood vs Lambda Curve
        traces = [
            {
                "x": [round(float(v), 3) for v in lam_grid],
                "y": [round(float(v), 3) for v in llf_grid],
                "mode": "lines",
                "name": "Log-Likelihood",
                "line": {"color": "#005a9e", "width": 2}
            },
            # Maximum line
            {
                "x": [opt_lambda, opt_lambda],
                "y": [float(np.min(llf_grid)), max_llf],
                "mode": "lines",
                "line": {"color": "#008450", "width": 1.5, "dash": "dash"},
                "name": f"Optimal λ = {opt_lambda:.3f}"
            },
            # Cutoff line
            {
                "x": [float(np.min(lam_grid)), float(np.max(lam_grid))],
                "y": [llf_cutoff, llf_cutoff],
                "mode": "lines",
                "line": {"color": "#d13438", "width": 1.5, "dash": "dot"},
                "name": f"{params.confidence_level:.0f}% CI Limit ({llf_cutoff:.2f})"
            }
        ]

        layout = {
            "title": {"text": f"<b>Box-Cox Transformation Plot for {var_name}</b><br><span style='font-size:11px;color:#605e5c'>Optimal λ = {opt_lambda:.4f} (95% CI: [{ci_lower:.3f}, {ci_upper:.3f}])</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Lambda (λ)", "showgrid": True, "gridcolor": "#f3f2f1", "linecolor": "#201f1e"},
            "yaxis": {"title": "Log-Likelihood", "showgrid": True, "gridcolor": "#f3f2f1", "linecolor": "#201f1e"},
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 55, "r": 30, "t": 60, "b": 55}
        }

        # Tables
        table = TableResult(
            title="Box-Cox Transformation Results",
            headers=["Parameter", "Value"],
            rows=[
                ["Optimal Lambda (λ)", f"{opt_lambda:.4f}"],
                [f"{params.confidence_level:.0f}% Confidence Interval", f"[{ci_lower:.4f}, {ci_upper:.4f}]"],
                ["Rounded Value Recommendation", f"{rounded_lambda:.1f}"],
                ["Selected Lambda for Transformation", f"{chosen_lambda:.4f}"]
            ]
        )

        col_name = params.store_column_name.strip() or f"BC_{var_name}"
        col_id = f"bc_{var_name.lower()}"

        text_lines = [
            f"Box-Cox Transformation of {var_name}",
            "",
            f"  Optimal Lambda (λ)     : {opt_lambda:.5f}",
            f"  {params.confidence_level:.0f}% CI for Lambda       : [{ci_lower:.5f}, {ci_upper:.5f}]",
            f"  Rounded Recommendation : {rounded_lambda:.1f}",
            f"  Applied Lambda         : {chosen_lambda:.5f}",
            "",
            f"Appended transformed data column '{col_name}' directly into active worksheet."
        ]

        # Prepare storage
        storage_cols = [{"id": col_id, "name": col_name, "type": "numeric"}]
        rows_data = []
        raw_full = pd.to_numeric(df[var_name], errors="coerce")
        for v in raw_full:
            if pd.isna(v) or v <= 0:
                rows_data.append({col_id: None})
            else:
                t_val = (v ** chosen_lambda - 1.0) / chosen_lambda if abs(chosen_lambda) > 1e-5 else np.log(v)
                rows_data.append({col_id: round(float(t_val), 5)})

        return AnalysisResult(
            title="Box-Cox Transformation",
            subtitle=f"{lam_desc} on {var_name}",
            text_output="\n".join(text_lines),
            tables=[table],
            plotly_figure={"data": traces, "layout": layout},
            action_type="worksheet_append_columns",
            worksheet_data={"columns": storage_cols, "rows": rows_data}
        )
