import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class OutlierTestParams(BaseModel):
    variable: str = Field(
        ...,
        description="Variable to test for outliers",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    significance_level: float = Field(
        0.05,
        description="Significance level (alpha, e.g. 0.05 for 5%)",
        json_schema_extra={"ui_type": "number"}
    )


class OutlierTestPlugin(AnalysisPlugin):
    id = "outlier_test"
    name = "Outlier Test"
    menu_path = ["Stat", "Basic Statistics", "Outlier Test"]
    description = "Performs Grubbs' test to detect single extreme outliers and computes 10% trimmed mean diagnostics."
    param_schema = OutlierTestParams

    def execute(self, df: pd.DataFrame, params: OutlierTestParams) -> AnalysisResult:
        if params.variable not in df.columns:
            raise ValueError(f"Variable '{params.variable}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[params.variable], errors="coerce").dropna().to_numpy(dtype=float)
        n = len(raw_series)
        if n < 3:
            raise ValueError(f"Grubbs' outlier test requires at least 3 valid observations (found {n}).")

        mean_val = float(np.mean(raw_series))
        stdev_val = float(np.std(raw_series, ddof=1))

        # Deviations from mean
        deviations = np.abs(raw_series - mean_val)
        max_idx = int(np.argmax(deviations))
        outlier_val = float(raw_series[max_idx])
        g_stat = float(deviations[max_idx] / stdev_val) if stdev_val > 0 else 0.0

        # Grubbs Critical Value and P-Value
        alpha = float(params.significance_level)
        t_crit = stats.t.ppf(1.0 - alpha / (2.0 * n), df=n - 2)
        g_crit = ((n - 1) / np.sqrt(n)) * np.sqrt((t_crit ** 2) / (n - 2 + (t_crit ** 2)))

        # Approximate P-Value using t distribution CDF
        # Invert G to t: t^2 = (n - 2) * G^2 / ((n - 1)^2 - n * G^2)
        term = ((n - 1) ** 2) - n * (g_stat ** 2)
        if term > 0:
            t_equiv = np.sqrt((n - 2) * (g_stat ** 2) / term)
            p_val = n * 2.0 * (1.0 - stats.t.cdf(t_equiv, df=n - 2))
            p_val = min(max(float(p_val), 0.0001), 1.0)
        else:
            p_val = 0.0001

        is_outlier = bool(p_val <= alpha)

        # 10% Trimmed Mean
        trimmed_mean = float(stats.trim_mean(raw_series, 0.10))

        # Tables
        desc_headers = ["N", "Mean", "StDev", "10% Trimmed Mean", "Min", "Median", "Max"]
        desc_rows = [[
            n,
            f"{mean_val:.4f}",
            f"{stdev_val:.4f}",
            f"{trimmed_mean:.4f}",
            f"{np.min(raw_series):.4f}",
            f"{np.median(raw_series):.4f}",
            f"{np.max(raw_series):.4f}",
        ]]

        test_headers = ["Suspected Value", "G Statistic", "Critical G (α=" + str(alpha) + ")", "P-Value", "Conclusion"]
        conclusion = "Outlier detected (Reject H₀)" if is_outlier else "No outlier detected (Fail to reject H₀)"
        test_rows = [[f"{outlier_val:.4f} (Row {max_idx + 1})", f"{g_stat:.3f}", f"{g_crit:.3f}", f"{p_val:.4f}", conclusion]]

        text_lines = [
            f"Grubbs' Outlier Test: {params.variable}",
            "",
            "Descriptive Statistics",
            f"  {'N':>5} {'Mean':>10} {'StDev':>10} {'10% Trimmed':>12} {'Median':>10}",
            f"  {'-'*5} {'-'*10} {'-'*10} {'-'*12} {'-'*10}",
            f"  {n:>5} {mean_val:>10.4f} {stdev_val:>10.4f} {trimmed_mean:>12.4f} {np.median(raw_series):>10.4f}",
            "",
            "Test",
            "  Null hypothesis:         All data values come from the same normal population",
            "  Alternative hypothesis:  The smallest or largest data value is an outlier",
            f"  Grubbs' Test Statistic: G = {g_stat:.3f}",
            f"  Critical Value:         G_crit = {g_crit:.3f}",
            f"  P-Value:                {p_val:.4f}",
            "",
            f"  Result: {conclusion} at α = {alpha}",
        ]

        # Plot: Individual Values Plot with Suspected Outlier Highlighted
        x_indices = list(range(1, n + 1))
        point_colors = ["#dc2626" if i == max_idx and is_outlier else "#1d4ed8" for i in range(n)]

        plot_data = [
            {
                "type": "scatter",
                "x": x_indices,
                "y": raw_series.tolist(),
                "mode": "markers",
                "name": "Data Values",
                "marker": {"color": point_colors, "size": 8},
                "hoverinfo": "x+y",
            },
            {
                "type": "scatter",
                "x": [1, n],
                "y": [mean_val, mean_val],
                "mode": "lines",
                "name": "Mean",
                "line": {"color": "#16a34a", "width": 1.5, "dash": "dash"},
            }
        ]

        layout = {
            "title": {"text": f"<b>Outlier Plot of {params.variable} (Grubbs' G = {g_stat:.3f})</b>", "x": 0.5},
            "showlegend": True,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 400,
            "xaxis": {"title": {"text": "Observation Order"}, "showgrid": True, "gridcolor": "#ececec"},
            "yaxis": {"title": {"text": params.variable}, "showgrid": True, "gridcolor": "#ececec"},
        }

        return AnalysisResult(
            title="Outlier Test",
            subtitle=f"{params.variable} (Grubbs' Test)",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title="Descriptive Statistics", headers=desc_headers, rows=desc_rows),
                TableResult(title="Grubbs' Test for Outlier", headers=test_headers, rows=test_rows)
            ],
            statistics={"g_stat": g_stat, "g_crit": g_crit, "p_value": p_val, "outlier_val": outlier_val, "is_outlier": is_outlier},
            plotly_figure={"data": plot_data, "layout": layout}
        )
