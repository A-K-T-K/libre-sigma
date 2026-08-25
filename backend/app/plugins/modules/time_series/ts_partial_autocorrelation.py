"""
Partial Autocorrelation (PACF) Plugin for OpenMinitab.
Calculates Partial Autocorrelation coefficients using Yule-Walker, OLS, or Levinson-Durbin algorithms with significance bounds and t-statistics.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import pacf
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class PartialAutocorrelationParams(BaseModel):
    variable: str = Field(
        ...,
        description="Series / Variable",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    lag_mode: str = Field(
        "default",
        description="Number of Lags",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Default (min(N/4, 25))", "value": "default"},
                {"label": "User-Specified Number of Lags", "value": "user"}
            ]
        }
    )
    n_lags: int = Field(
        20,
        ge=1,
        le=200,
        description="Number of Lags (if user-specified)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    method: str = Field(
        "ywadjusted",
        description="Estimation Method",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Yule-Walker (Adjusted)", "value": "ywadjusted"},
                {"label": "OLS (Ordinary Least Squares)", "value": "ols"},
                {"label": "Levinson-Durbin (Yule-Walker Unadjusted)", "value": "ywm"}
            ]
        }
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    # Storage Sub-Modal
    store_pacf: bool = Field(
        False,
        description="Store PACF Values in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_tstats: bool = Field(
        False,
        description="Store T-Statistics in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )


class PartialAutocorrelationPlugin(AnalysisPlugin):
    id = "ts_partial_autocorrelation"
    name = "Partial Autocorrelation (PACF)"
    menu_path = ["Stat", "Time Series", "Partial Autocorrelation"]
    description = "Calculates sample partial autocorrelation function (PACF) coefficients with critical significance bounds and t-statistics."
    param_schema = PartialAutocorrelationParams

    def execute(self, df: pd.DataFrame, params: PartialAutocorrelationParams) -> AnalysisResult:
        var_name = params.variable
        if var_name not in df.columns:
            raise ValueError(f"Column '{var_name}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[var_name], errors="coerce").dropna()
        n = len(raw_series)
        if n < 5:
            raise ValueError("Partial Autocorrelation requires at least 5 observations.")

        if params.lag_mode == "user":
            k_lags = min(params.n_lags, (n // 2) - 1)
        else:
            k_lags = min(max(4, n // 4), 25, (n // 2) - 1)

        y = raw_series.to_numpy(dtype=float)

        # Compute PACF
        pacf_vals = pacf(
            y,
            nlags=k_lags,
            method=params.method
        )

        lags = list(range(1, k_lags + 1))
        pacf_lags = pacf_vals[1:k_lags + 1]

        z_crit = stats.norm.ppf(1.0 - (1.0 - params.confidence_level / 100.0) / 2.0)
        bound = z_crit / np.sqrt(n)

        # Standard error is 1/sqrt(N); T-stat is PACF / (1/sqrt(N)) = PACF * sqrt(N)
        se_val = 1.0 / np.sqrt(n)
        t_stats = [v * np.sqrt(n) for v in pacf_lags]

        # Plotly PACF chart
        traces = [
            # Zero baseline
            {
                "x": [0, k_lags + 0.5],
                "y": [0, 0],
                "mode": "lines",
                "line": {"color": "#605e5c", "width": 1},
                "showlegend": False,
                "hoverinfo": "none"
            },
            # Upper Bound
            {
                "x": [0.5, k_lags + 0.5],
                "y": [bound, bound],
                "mode": "lines",
                "line": {"color": "#d13438", "width": 1.5, "dash": "dash"},
                "name": f"+{params.confidence_level:.0f}% Limit (+{bound:.3f})"
            },
            # Lower Bound
            {
                "x": [0.5, k_lags + 0.5],
                "y": [-bound, -bound],
                "mode": "lines",
                "line": {"color": "#d13438", "width": 1.5, "dash": "dash"},
                "name": f"-{params.confidence_level:.0f}% Limit (-{bound:.3f})"
            },
            # PACF Bars
            {
                "x": lags,
                "y": [round(float(v), 4) for v in pacf_lags],
                "type": "bar",
                "width": 0.25,
                "marker": {
                    "color": ["#d13438" if abs(v) > bound else "#005a9e" for v in pacf_lags]
                },
                "name": "PACF Correlation"
            }
        ]

        layout = {
            "title": {"text": f"<b>Partial Autocorrelation Function for {var_name}</b><br><span style='font-size:11px;color:#605e5c'>Method: {params.method.upper()} with {params.confidence_level:.0f}% Limits (N = {n})</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Lag", "tickmode": "linear", "dtick": 1, "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Partial Autocorrelation", "range": [-1.05, 1.05], "showgrid": True, "gridcolor": "#f3f2f1"},
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 55, "r": 30, "t": 60, "b": 55}
        }

        # Table
        table_rows = []
        for i in range(len(lags)):
            table_rows.append([
                lags[i],
                round(float(pacf_lags[i]), 4),
                round(float(se_val), 4),
                round(float(t_stats[i]), 4)
            ])

        table = TableResult(
            title=f"Partial Autocorrelation Function: {var_name}",
            headers=["Lag", "PACF", "Std Error", "T-Statistic"],
            rows=table_rows
        )

        text_lines = [
            f"Partial Autocorrelation Function for {var_name}",
            f"Method: {params.method.upper()} | Sample Size: {n} | Number of Lags: {k_lags}",
            "",
            f"  {'Lag':<6} {'PACF':>10} {'SE':>10} {'T-Stat':>10}",
            f"  {'-'*6} {'-'*10} {'-'*10} {'-'*10}",
        ]
        for r in table_rows:
            text_lines.append(f"  {r[0]:<6} {r[1]:>10.4f} {r[2]:>10.4f} {r[3]:>10.4f}")

        # Worksheet Storage
        storage_cols = []
        new_cols_dict: Dict[str, List[Any]] = {}

        if params.store_pacf:
            storage_cols.append({"id": f"pacf_{var_name.lower()}", "name": f"PACF_{var_name}", "type": "numeric"})
            new_cols_dict[f"pacf_{var_name.lower()}"] = [round(float(v), 4) for v in pacf_lags]

        if params.store_tstats:
            storage_cols.append({"id": f"tstat_{var_name.lower()}", "name": f"TSTAT_{var_name}", "type": "numeric"})
            new_cols_dict[f"tstat_{var_name.lower()}"] = [round(float(v), 4) for v in t_stats]

        action_type = None
        worksheet_data = None
        if storage_cols:
            rows_data = []
            for r_i in range(len(lags)):
                r_dict = {}
                for col_spec in storage_cols:
                    c_id = col_spec["id"]
                    val_list = new_cols_dict.get(c_id, [])
                    r_dict[c_id] = val_list[r_i] if r_i < len(val_list) else None
                rows_data.append(r_dict)

            action_type = "worksheet_append_columns"
            worksheet_data = {"columns": storage_cols, "rows": rows_data}

        return AnalysisResult(
            title="Partial Autocorrelation Function",
            subtitle=f"PACF of {var_name}",
            text_output="\n".join(text_lines),
            tables=[table],
            plotly_figure={"data": traces, "layout": layout},
            action_type=action_type,
            worksheet_data=worksheet_data
        )
