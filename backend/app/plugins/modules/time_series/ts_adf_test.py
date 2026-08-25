"""
Augmented Dickey-Fuller (ADF) Test Plugin for OpenMinitab.
Tests the null hypothesis that a unit root is present in a time series (non-stationarity).
Displays ADF Statistic, p-value, Critical Values (1%, 5%, 10%), lag selection, and stationarity conclusion.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class ADFTestParams(BaseModel):
    variable: str = Field(
        ...,
        description="Series / Variable (Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    regression_type: str = Field(
        "c",
        description="Model / Regression Type",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Constant only (c)", "value": "c"},
                {"label": "Constant and Trend (ct)", "value": "ct"},
                {"label": "No constant, no trend (n)", "value": "n"},
                {"label": "Constant, Linear & Quadratic Trend (ctt)", "value": "ctt"}
            ]
        }
    )
    lag_criterion: str = Field(
        "AIC",
        description="Lag Selection Criteria",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Akaike Information Criterion (AIC)", "value": "AIC"},
                {"label": "Bayesian Information Criterion (BIC)", "value": "BIC"},
                {"label": "Fixed Maximum Lag (t-stat)", "value": "t-stat"}
            ]
        }
    )
    max_lag: Optional[int] = Field(
        None,
        ge=0,
        le=50,
        description="Maximum Lag (Optional)"
    )


class ADFTestPlugin(AnalysisPlugin):
    id = "ts_adf_test"
    name = "Augmented Dickey-Fuller Test"
    menu_path = ["Stat", "Time Series", "Augmented Dickey-Fuller Test"]
    description = "Tests for unit roots and stationarity in a time series using the Augmented Dickey-Fuller (ADF) test."
    param_schema = ADFTestParams

    def execute(self, df: pd.DataFrame, params: ADFTestParams) -> AnalysisResult:
        var_name = params.variable
        if var_name not in df.columns:
            raise ValueError(f"Column '{var_name}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[var_name], errors="coerce").dropna()
        n = len(raw_series)
        if n < 8:
            raise ValueError("Augmented Dickey-Fuller test requires at least 8 observations.")

        y = raw_series.to_numpy(dtype=float)

        # Run ADF test
        autolag_arg = params.lag_criterion if params.lag_criterion in ["AIC", "BIC", "t-stat"] else "AIC"
        
        adf_res = adfuller(
            y,
            maxlag=params.max_lag,
            regression=params.regression_type,
            autolag=autolag_arg
        )

        test_stat = float(adf_res[0])
        p_val = float(adf_res[1])
        used_lag = int(adf_res[2])
        n_obs = int(adf_res[3])
        crit_vals = adf_res[4]  # dict: {"1%": val, "5%": val, "10%": val}
        ic_best = float(adf_res[5]) if len(adf_res) > 5 else None

        is_stationary = p_val < 0.05
        conclusion_text = (
            "Evidence suggests the data is STATIONARY (Reject Null Hypothesis of Unit Root at α=0.05)"
            if is_stationary
            else "Evidence suggests the data is NON-STATIONARY (Fail to Reject Null Hypothesis; Unit Root Present)"
        )

        reg_name_map = {
            "c": "Constant only",
            "ct": "Constant and Trend",
            "n": "No constant, No trend",
            "ctt": "Constant, Linear & Quadratic Trend"
        }

        # Tables
        main_table = TableResult(
            title=f"Augmented Dickey-Fuller Test for {var_name}",
            headers=["Statistic / Metric", "Value"],
            rows=[
                ["ADF Test Statistic", f"{test_stat:.5f}"],
                ["P-Value", f"{p_val:.5f}"],
                ["Number of Lags Used", str(used_lag)],
                ["Number of Observations", str(n_obs)],
                ["Regression Model", reg_name_map.get(params.regression_type, params.regression_type)],
                ["Lag Selection Criterion", autolag_arg],
                ["Crit Value (1%)", f"{crit_vals.get('1%', 0.0):.4f}"],
                ["Crit Value (5%)", f"{crit_vals.get('5%', 0.0):.4f}"],
                ["Crit Value (10%)", f"{crit_vals.get('10%', 0.0):.4f}"],
                ["Conclusion (α = 0.05)", "Stationary" if is_stationary else "Non-Stationary"]
            ]
        )

        # Plotly chart showing series with stationary indicator banner
        t_indices = list(range(1, n + 1))
        traces = [
            {
                "x": t_indices,
                "y": y.tolist(),
                "mode": "lines+markers",
                "name": var_name,
                "line": {"color": "#008450" if is_stationary else "#d13438", "width": 2},
                "marker": {"size": 5, "color": "#008450" if is_stationary else "#d13438"}
            }
        ]

        banner_color = "#008450" if is_stationary else "#d13438"
        status_label = "STATIONARY (p < 0.05)" if is_stationary else "NON-STATIONARY (p ≥ 0.05)"

        layout = {
            "title": {"text": f"<b>ADF Test for {var_name}: {status_label}</b><br><span style='font-size:11px;color:{banner_color}'>ADF = {test_stat:.4f}, p-value = {p_val:.5f} (Used Lag = {used_lag})</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Index / Time (t)", "showgrid": True, "gridcolor": "#f3f2f1", "linecolor": "#201f1e"},
            "yaxis": {"title": var_name, "showgrid": True, "gridcolor": "#f3f2f1", "linecolor": "#201f1e"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 55, "r": 30, "t": 65, "b": 50}
        }

        text_lines = [
            f"Augmented Dickey-Fuller (ADF) Test for {var_name}",
            "",
            f"Null Hypothesis (H0)        : The series has a unit root (Non-Stationary)",
            f"Alternative Hypothesis (H1) : The series does not have a unit root (Stationary)",
            "",
            f"  ADF Test Statistic : {test_stat:.5f}",
            f"  Calculated P-Value : {p_val:.5f}",
            f"  Lags Selected      : {used_lag} (via {autolag_arg})",
            f"  Observations (N)   : {n_obs}",
            "",
            "Critical Values:",
            f"  1%  Level : {crit_vals.get('1%', 0.0):.4f}",
            f"  5%  Level : {crit_vals.get('5%', 0.0):.4f}",
            f"  10% Level : {crit_vals.get('10%', 0.0):.4f}",
            "",
            f"Conclusion: {conclusion_text}"
        ]

        return AnalysisResult(
            title="Augmented Dickey-Fuller Test",
            subtitle=f"{status_label} for {var_name}",
            text_output="\n".join(text_lines),
            tables=[main_table],
            plotly_figure={"data": traces, "layout": layout},
            statistics={
                "adf_stat": test_stat,
                "p_value": p_val,
                "lags_used": used_lag,
                "is_stationary": is_stationary
            }
        )
