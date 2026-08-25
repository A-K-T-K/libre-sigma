"""
Autocorrelation (ACF) Plugin for OpenMinitab.
Calculates Sample Autocorrelation Function coefficients, Standard Errors, and Ljung-Box Q statistics with interactive spike plot and critical significance bands.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import acf, q_stat
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class AutocorrelationParams(BaseModel):
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
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%) for Significance Bands",
        json_schema_extra={"sub_modal": "Options..."}
    )
    # Storage Sub-Modal
    store_acf: bool = Field(
        False,
        description="Store Autocorrelations in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_qstat: bool = Field(
        False,
        description="Store Ljung-Box Q Statistics in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_pvals: bool = Field(
        False,
        description="Store P-Values in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )


class AutocorrelationPlugin(AnalysisPlugin):
    id = "ts_autocorrelation"
    name = "Autocorrelation (ACF)"
    menu_path = ["Stat", "Time Series", "Autocorrelation"]
    description = "Calculates autocorrelation coefficients and Ljung-Box Q statistics with critical significance bands."
    param_schema = AutocorrelationParams

    def execute(self, df: pd.DataFrame, params: AutocorrelationParams) -> AnalysisResult:
        var_name = params.variable
        if var_name not in df.columns:
            raise ValueError(f"Column '{var_name}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[var_name], errors="coerce").dropna()
        n = len(raw_series)
        if n < 5:
            raise ValueError("Autocorrelation requires at least 5 observations.")

        # Determine number of lags
        if params.lag_mode == "user":
            k_lags = min(params.n_lags, n - 2)
        else:
            k_lags = min(max(4, n // 4), 25)

        y = raw_series.to_numpy(dtype=float)

        # Compute ACF and Ljung-Box Q statistics
        acf_vals, confint, qstat_vals, pvals = acf(
            y,
            nlags=k_lags,
            alpha=(1.0 - params.confidence_level / 100.0),
            qstat=True
        )

        # acf_vals[0] is lag 0 (which is 1.0)
        lags = list(range(1, k_lags + 1))
        acf_lags = acf_vals[1:k_lags + 1]

        # Standard error approximation: Bartlett's formula or 1/sqrt(N)
        z_crit = stats.norm.ppf(1.0 - (1.0 - params.confidence_level / 100.0) / 2.0)
        bound = z_crit / np.sqrt(n)

        # Calculate standard errors for each lag
        se_list = []
        for i in range(len(acf_lags)):
            if i == 0:
                se = 1.0 / np.sqrt(n)
            else:
                se = np.sqrt((1.0 + 2.0 * np.sum(acf_lags[:i] ** 2)) / n)
            se_list.append(se)

        # Plotly ACF spike plot
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
            # ACF Spikes
            {
                "x": lags,
                "y": [round(float(v), 4) for v in acf_lags],
                "type": "bar",
                "width": 0.25,
                "marker": {
                    "color": ["#d13438" if abs(v) > bound else "#005a9e" for v in acf_lags]
                },
                "name": "ACF Correlation"
            }
        ]

        layout = {
            "title": {"text": f"<b>Autocorrelation Function for {var_name}</b><br><span style='font-size:11px;color:#605e5c'>with {params.confidence_level:.0f}% Significance Limits (N = {n})</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Lag", "tickmode": "linear", "dtick": 1, "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Autocorrelation (r_k)", "range": [-1.05, 1.05], "showgrid": True, "gridcolor": "#f3f2f1"},
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 55, "r": 30, "t": 60, "b": 55}
        }

        # Table
        table_rows = []
        for i in range(len(lags)):
            q_val = qstat_vals[i] if i < len(qstat_vals) else None
            p_val = pvals[i] if i < len(pvals) else None
            table_rows.append([
                lags[i],
                round(float(acf_lags[i]), 4),
                round(float(se_list[i]), 4),
                round(float(q_val), 4) if q_val is not None else "N/A",
                round(float(p_val), 4) if p_val is not None else "N/A"
            ])

        table = TableResult(
            title=f"Autocorrelation Function: {var_name}",
            headers=["Lag", "ACF", "Std Error", "Ljung-Box Q", "P-Value"],
            rows=table_rows
        )

        text_lines = [
            f"Autocorrelation Function for {var_name}",
            f"Sample Size: {n} | Number of Lags: {k_lags}",
            "",
            f"  {'Lag':<6} {'ACF':>10} {'SE':>10} {'Q-Stat':>12} {'P-Value':>10}",
            f"  {'-'*6} {'-'*10} {'-'*10} {'-'*12} {'-'*10}",
        ]
        for r in table_rows:
            q_s = f"{r[3]:>12.4f}" if isinstance(r[3], (int, float)) else f"{r[3]:>12}"
            p_s = f"{r[4]:>10.4f}" if isinstance(r[4], (int, float)) else f"{r[4]:>10}"
            text_lines.append(f"  {r[0]:<6} {r[1]:>10.4f} {r[2]:>10.4f} {q_s} {p_s}")

        # Worksheet Storage
        storage_cols = []
        new_cols_dict: Dict[str, List[Any]] = {}

        if params.store_acf:
            storage_cols.append({"id": f"acf_{var_name.lower()}", "name": f"ACF_{var_name}", "type": "numeric"})
            new_cols_dict[f"acf_{var_name.lower()}"] = [round(float(v), 4) for v in acf_lags]

        if params.store_qstat:
            storage_cols.append({"id": f"qstat_{var_name.lower()}", "name": f"QSTAT_{var_name}", "type": "numeric"})
            new_cols_dict[f"qstat_{var_name.lower()}"] = [round(float(v), 4) for v in qstat_vals]

        if params.store_pvals:
            storage_cols.append({"id": f"pval_{var_name.lower()}", "name": f"PVAL_{var_name}", "type": "numeric"})
            new_cols_dict[f"pval_{var_name.lower()}"] = [round(float(v), 4) for v in pvals]

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
            title="Autocorrelation Function",
            subtitle=f"ACF of {var_name}",
            text_output="\n".join(text_lines),
            tables=[table],
            plotly_figure={"data": traces, "layout": layout},
            action_type=action_type,
            worksheet_data=worksheet_data
        )
