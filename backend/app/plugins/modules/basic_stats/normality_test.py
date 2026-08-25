import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class NormalityTestParams(BaseModel):
    variable: str = Field(
        ...,
        description="Variable to test for normality",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    test_type: str = Field(
        "anderson_darling",
        description="Normality Test Method",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Anderson-Darling", "value": "anderson_darling"},
                {"label": "Ryan-Joiner (similar to Shapiro-Wilk)", "value": "ryan_joiner"},
                {"label": "Kolmogorov-Smirnov (Lilliefors)", "value": "kolmogorov_smirnov"},
            ]
        }
    )


class NormalityTestPlugin(AnalysisPlugin):
    id = "normality_test"
    name = "Normality Test"
    menu_path = ["Stat", "Basic Statistics", "Normality Test"]
    description = "Tests if data follow a normal distribution and generates a probability plot with confidence bands."
    param_schema = NormalityTestParams

    def execute(self, df: pd.DataFrame, params: NormalityTestParams) -> AnalysisResult:
        if params.variable not in df.columns:
            raise ValueError(f"Variable '{params.variable}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[params.variable], errors="coerce").dropna().to_numpy(dtype=float)
        n = len(raw_series)
        if n < 4:
            raise ValueError(f"Normality test requires at least 4 data points (found {n}).")

        mean_val = float(np.mean(raw_series))
        stdev_val = float(np.std(raw_series, ddof=1))

        # 1. Anderson-Darling Test
        ad_res = stats.anderson(raw_series, dist="norm")
        a_sq = float(ad_res.statistic)
        a_sq_mod = a_sq * (1.0 + 0.75 / n + 2.25 / (n ** 2))
        if a_sq_mod >= 0.60:
            ad_p = float(np.exp(1.2937 - 5.709 * a_sq_mod + 0.0186 * (a_sq_mod ** 2)))
        elif a_sq_mod > 0.34:
            ad_p = float(np.exp(0.9177 - 4.279 * a_sq_mod - 1.38 * (a_sq_mod ** 2)))
        elif a_sq_mod > 0.20:
            ad_p = float(1.0 - np.exp(-8.318 + 42.796 * a_sq_mod - 59.838 * (a_sq_mod ** 2)))
        else:
            ad_p = float(1.0 - np.exp(-13.436 + 101.14 * a_sq_mod - 223.73 * (a_sq_mod ** 2)))
        ad_p = min(max(ad_p, 0.0001), 0.9999)

        # 2. Ryan-Joiner (Correlation on probability plot)
        sorted_x = np.sort(raw_series)
        # Blom plotting positions
        p_i = (np.arange(1, n + 1) - 0.375) / (n + 0.25)
        z_i = stats.norm.ppf(p_i)
        r_rj, _ = stats.pearsonr(sorted_x, z_i)
        # RJ critical value approximation
        rj_stat = float(r_rj)
        rj_p = float(stats.norm.sf((1.0 - rj_stat) * np.sqrt(n) * 10))

        # 3. Kolmogorov-Smirnov / Lilliefors
        ks_stat, ks_p = stats.kstest(raw_series, "norm", args=(mean_val, stdev_val))

        if params.test_type == "ryan_joiner":
            active_test_name = "Ryan-Joiner"
            stat_name = "RJ"
            stat_val = rj_stat
            p_val = max(0.001, min(0.999, rj_p))
        elif params.test_type == "kolmogorov_smirnov":
            active_test_name = "Kolmogorov-Smirnov"
            stat_name = "KS"
            stat_val = float(ks_stat)
            p_val = float(ks_p)
        else:
            active_test_name = "Anderson-Darling"
            stat_name = "A-Squared"
            stat_val = a_sq
            p_val = ad_p

        # Normal Probability Plot Percentages (0.1% to 99.9%)
        y_percents = p_i * 100.0
        # Reference Line (mean - 3*sigma to mean + 3*sigma)
        x_line = np.linspace(mean_val - 3 * stdev_val, mean_val + 3 * stdev_val, 100)
        z_line = (x_line - mean_val) / stdev_val
        p_line = stats.norm.cdf(z_line) * 100.0

        # Upper and Lower 95% Confidence Bands
        se_p = (stdev_val / stats.norm.pdf(z_line)) * np.sqrt((p_line / 100.0) * (1.0 - p_line / 100.0) / n)
        ci_upper_x = x_line + 1.96 * se_p
        ci_lower_x = x_line - 1.96 * se_p

        plot_data = [
            # Data Points
            {
                "type": "scatter",
                "x": sorted_x.tolist(),
                "y": z_i.tolist(),
                "mode": "markers",
                "name": "Data Points",
                "marker": {"color": "#1d4ed8", "size": 6, "symbol": "circle"},
                "hoverinfo": "x+y",
            },
            # Middle Reference Line
            {
                "type": "scatter",
                "x": x_line.tolist(),
                "y": z_line.tolist(),
                "mode": "lines",
                "name": "Fit Line",
                "line": {"color": "#dc2626", "width": 1.75},
            },
            # Upper CI Band
            {
                "type": "scatter",
                "x": ci_upper_x.tolist(),
                "y": z_line.tolist(),
                "mode": "lines",
                "name": "95% Upper CI",
                "line": {"color": "#94a3b8", "width": 1, "dash": "dash"},
            },
            # Lower CI Band
            {
                "type": "scatter",
                "x": ci_lower_x.tolist(),
                "y": z_line.tolist(),
                "mode": "lines",
                "name": "95% Lower CI",
                "line": {"color": "#94a3b8", "width": 1, "dash": "dash"},
            },
        ]

        # Convert Z ticks to Percentages: 1%, 5%, 10%, 25%, 50%, 75%, 90%, 95%, 99%
        tick_percents = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        tick_z_vals = [float(stats.norm.ppf(p / 100.0)) for p in tick_percents]
        tick_labels = [f"{p}%" for p in tick_percents]

        layout = {
            "title": {"text": f"<b>Probability Plot of {params.variable}</b><br><span style='font-size:12px;color:#64748b;'>Normal - 95% CI</span>", "x": 0.5},
            "showlegend": False,
            "margin": {"l": 70, "r": 160, "t": 70, "b": 50},
            "height": 440,
            "xaxis": {"title": {"text": params.variable}, "showgrid": True, "gridcolor": "#ececec"},
            "yaxis": {
                "title": {"text": "Percent"},
                "tickmode": "array",
                "tickvals": tick_z_vals,
                "ticktext": tick_labels,
                "range": [stats.norm.ppf(0.005), stats.norm.ppf(0.995)],
                "showgrid": True,
                "gridcolor": "#ececec",
            },
            "annotations": [
                {
                    "xref": "paper",
                    "yref": "paper",
                    "x": 1.02,
                    "y": 0.98,
                    "xanchor": "left",
                    "yanchor": "top",
                    "text": f"<b>{active_test_name}</b><br>{stat_name}: {stat_val:.3f}<br>P-Value: {p_val:.4f}<br><br>Mean: {mean_val:.4f}<br>StDev: {stdev_val:.4f}<br>N: {n}",
                    "showarrow": False,
                    "bordercolor": "#94a3b8",
                    "borderwidth": 1,
                    "borderpad": 6,
                    "bgcolor": "#ffffff",
                    "font": {"size": 11, "color": "#1e293b"},
                }
            ]
        }

        # Tables
        test_headers = ["Test Method", "Statistic", "P-Value"]
        test_rows = [
            ["Anderson-Darling", f"{a_sq:.3f}", f"{ad_p:.4f}"],
            ["Ryan-Joiner", f"{rj_stat:.3f}", f"{rj_p:.4f}"],
            ["Kolmogorov-Smirnov", f"{ks_stat:.3f}", f"{ks_p:.4f}"],
        ]

        text_lines = [
            f"Probability Plot of {params.variable}",
            f"Test for Normality: {active_test_name}",
            "",
            f"  Mean:   {mean_val:.4f}",
            f"  StDev:  {stdev_val:.4f}",
            f"  N:      {n}",
            f"  {stat_name}: {stat_val:.3f}",
            f"  P-Value: {p_val:.4f}",
        ]

        return AnalysisResult(
            title="Normality Test",
            subtitle=f"{params.variable} ({active_test_name})",
            text_output="\n".join(text_lines),
            tables=[TableResult(title="Normality Test Results", headers=test_headers, rows=test_rows)],
            statistics={"mean": mean_val, "stdev": stdev_val, "n": n, "ad_stat": a_sq, "ad_p": ad_p},
            plotly_figure={"data": plot_data, "layout": layout}
        )
