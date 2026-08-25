"""
Cross Correlation (CCF) Plugin for OpenMinitab.
Calculates sample cross-correlation coefficients between two time series across leads and lags (-K to +K) with standard error significance bands.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class CrossCorrelationParams(BaseModel):
    first_series_x: str = Field(
        ...,
        description="First Series (X - Dependent)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    second_series_y: str = Field(
        ...,
        description="Second Series (Y - Independent)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    lag_mode: str = Field(
        "default",
        description="Number of Lags",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Default (from -K to +K, K = min(N/4, 15))", "value": "default"},
                {"label": "User-Specified Maximum Lag K", "value": "user"}
            ]
        }
    )
    max_lag: int = Field(
        15,
        ge=1,
        le=100,
        description="Maximum Lag K",
        json_schema_extra={"sub_modal": "Options..."}
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    # Storage Sub-Modal
    store_ccf: bool = Field(
        False,
        description="Store CCF Values in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_lags: bool = Field(
        False,
        description="Store Lags in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )


class CrossCorrelationPlugin(AnalysisPlugin):
    id = "ts_cross_correlation"
    name = "Cross Correlation (CCF)"
    menu_path = ["Stat", "Time Series", "Cross Correlation"]
    description = "Calculates cross-correlation coefficients between two time series at negative and positive lags with critical limits."
    param_schema = CrossCorrelationParams

    def execute(self, df: pd.DataFrame, params: CrossCorrelationParams) -> AnalysisResult:
        x_col, y_col = params.first_series_x, params.second_series_y
        if x_col not in df.columns or y_col not in df.columns:
            raise ValueError(f"Columns '{x_col}' and/or '{y_col}' not found in active worksheet.")

        sub_df = df[[x_col, y_col]].dropna().copy()
        sub_df[x_col] = pd.to_numeric(sub_df[x_col], errors="coerce")
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n = len(sub_df)
        if n < 6:
            raise ValueError("Cross Correlation requires at least 6 valid observation pairs.")

        if params.lag_mode == "user":
            k_max = min(params.max_lag, n - 2)
        else:
            k_max = min(max(4, n // 4), 15)

        x_vals = sub_df[x_col].to_numpy(dtype=float)
        y_vals = sub_df[y_col].to_numpy(dtype=float)

        x_mean = np.mean(x_vals)
        y_mean = np.mean(y_vals)
        x_dev = x_vals - x_mean
        y_dev = y_vals - y_mean
        denom = np.sqrt(np.sum(x_dev ** 2) * np.sum(y_dev ** 2))
        if denom < 1e-12:
            raise ValueError("One or both series have zero variance.")

        lags = list(range(-k_max, k_max + 1))
        ccf_vals = []

        for k in lags:
            if k >= 0:
                # CCF at lag +k: sum(x_t * y_{t+k}) / denom
                x_sub = x_dev[:n - k] if k < n else np.array([])
                y_sub = y_dev[k:] if k < n else np.array([])
            else:
                # CCF at lag -k: sum(x_t * y_{t-k}) / denom
                pos_k = abs(k)
                x_sub = x_dev[pos_k:] if pos_k < n else np.array([])
                y_sub = y_dev[:n - pos_k] if pos_k < n else np.array([])

            c_k = np.sum(x_sub * y_sub) / denom if len(x_sub) > 0 else 0.0
            ccf_vals.append(float(c_k))

        z_crit = stats.norm.ppf(1.0 - (1.0 - params.confidence_level / 100.0) / 2.0)
        bound = z_crit / np.sqrt(n)

        # Plotly CCF spike plot
        traces = [
            # Baseline
            {"x": [-k_max - 0.5, k_max + 0.5], "y": [0, 0], "mode": "lines", "line": {"color": "#605e5c", "width": 1}, "showlegend": False},
            # Upper Limit
            {"x": [-k_max - 0.5, k_max + 0.5], "y": [bound, bound], "mode": "lines", "line": {"color": "#d13438", "width": 1.5, "dash": "dash"}, "name": f"+{params.confidence_level:.0f}% Limit (+{bound:.3f})"},
            # Lower Limit
            {"x": [-k_max - 0.5, k_max + 0.5], "y": [-bound, -bound], "mode": "lines", "line": {"color": "#d13438", "width": 1.5, "dash": "dash"}, "name": f"-{params.confidence_level:.0f}% Limit (-{bound:.3f})"},
            # Spikes
            {
                "x": lags,
                "y": [round(float(v), 4) for v in ccf_vals],
                "type": "bar",
                "width": 0.25,
                "marker": {
                    "color": ["#d13438" if abs(v) > bound else "#005a9e" for v in ccf_vals]
                },
                "name": f"CCF({x_col}, {y_col})"
            }
        ]

        layout = {
            "title": {"text": f"<b>Cross Correlation Function: {x_col} & {y_col}</b><br><span style='font-size:11px;color:#605e5c'>{params.confidence_level:.0f}% Significance Limits (N = {n})</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Lag (k)", "tickmode": "linear", "dtick": 1, "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Cross Correlation", "range": [-1.05, 1.05], "showgrid": True, "gridcolor": "#f3f2f1"},
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 55, "r": 30, "t": 60, "b": 55}
        }

        # Tables
        table_rows = []
        for i in range(len(lags)):
            table_rows.append([
                lags[i],
                round(float(ccf_vals[i]), 4),
                round(float(1.0 / np.sqrt(n)), 4)
            ])

        table = TableResult(
            title=f"Cross Correlation: {x_col} and {y_col}",
            headers=["Lag (k)", "CCF", "Std Error"],
            rows=table_rows
        )

        text_lines = [
            f"Cross Correlation between {x_col} and {y_col}",
            f"Sample Size: {n} | Range: -{k_max} to +{k_max}",
            "",
            f"  {'Lag':<6} {'CCF':>10} {'SE':>10}",
            f"  {'-'*6} {'-'*10} {'-'*10}",
        ]
        for r in table_rows:
            text_lines.append(f"  {r[0]:<6} {r[1]:>10.4f} {r[2]:>10.4f}")

        # Worksheet Storage
        storage_cols = []
        new_cols_dict: Dict[str, List[Any]] = {}

        if params.store_lags:
            storage_cols.append({"id": "ccf_lags", "name": "CCF_Lags", "type": "numeric"})
            new_cols_dict["ccf_lags"] = lags

        if params.store_ccf:
            storage_cols.append({"id": f"ccf_{x_col.lower()}_{y_col.lower()}", "name": f"CCF_{x_col}_{y_col}", "type": "numeric"})
            new_cols_dict[f"ccf_{x_col.lower()}_{y_col.lower()}"] = [round(float(v), 4) for v in ccf_vals]

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
            title="Cross Correlation",
            subtitle=f"CCF between {x_col} and {y_col}",
            text_output="\n".join(text_lines),
            tables=[table],
            plotly_figure={"data": traces, "layout": layout},
            action_type=action_type,
            worksheet_data=worksheet_data
        )
