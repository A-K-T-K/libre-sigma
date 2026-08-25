import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class GraphicalSummaryParams(BaseModel):
    variable: str = Field(
        ...,
        description="Variable to analyze",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    confidence_level: float = Field(
        95.0,
        description="Confidence level (e.g. 95.0 for 95%)",
        json_schema_extra={"ui_type": "number"}
    )


class GraphicalSummaryPlugin(AnalysisPlugin):
    id = "graphical_summary"
    name = "Graphical Summary"
    menu_path = ["Stat", "Basic Statistics", "Graphical Summary"]
    description = "Generates Minitab's 4-in-1 Graphical Summary with Histogram & Normal Curve, Boxplot, Confidence Intervals, and Anderson-Darling Normality."
    param_schema = GraphicalSummaryParams

    def execute(self, df: pd.DataFrame, params: GraphicalSummaryParams) -> AnalysisResult:
        if params.variable not in df.columns:
            raise ValueError(f"Variable '{params.variable}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[params.variable], errors="coerce").dropna().to_numpy(dtype=float)
        n = len(raw_series)
        if n < 3:
            raise ValueError(f"Graphical Summary requires at least 3 data points (found {n}).")

        # Descriptive Statistics
        mean_val = float(np.mean(raw_series))
        stdev_val = float(np.std(raw_series, ddof=1))
        var_val = float(np.var(raw_series, ddof=1))
        skew_val = float(stats.skew(raw_series, bias=False)) if n > 2 else 0.0
        kurt_val = float(stats.kurtosis(raw_series, bias=False)) if n > 3 else 0.0

        min_val = float(np.min(raw_series))
        q1_val = float(np.percentile(raw_series, 25))
        med_val = float(np.median(raw_series))
        q3_val = float(np.percentile(raw_series, 75))
        max_val = float(np.max(raw_series))
        iqr_val = float(q3_val - q1_val)

        # Anderson-Darling Normality Test
        # Standardize for A-D
        std_z = (raw_series - mean_val) / stdev_val if stdev_val > 0 else np.zeros(n)
        ad_res = stats.anderson(raw_series, dist="norm")
        a_sq = float(ad_res.statistic)

        # Approximate p-value for Anderson-Darling using Stephens (1974) formula
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

        # Confidence Intervals
        conf = params.confidence_level / 100.0
        alpha = 1.0 - conf

        # Mean CI (t-distribution)
        t_crit = stats.t.ppf(1.0 - alpha / 2.0, df=n - 1)
        se_mean = stdev_val / np.sqrt(n)
        mean_ci = (mean_val - t_crit * se_mean, mean_val + t_crit * se_mean)

        # Median CI (Bonett-Price non-parametric CI)
        med_ci_low = float(np.percentile(raw_series, max(0, 50 - 50 * conf)))
        med_ci_high = float(np.percentile(raw_series, min(100, 50 + 50 * conf)))

        # StDev CI (Chi-Square distribution)
        chi2_low = stats.chi2.ppf(1.0 - alpha / 2.0, df=n - 1)
        chi2_high = stats.chi2.ppf(alpha / 2.0, df=n - 1)
        stdev_ci_low = np.sqrt((n - 1) * (stdev_val ** 2) / chi2_low) if chi2_low > 0 else 0.0
        stdev_ci_high = np.sqrt((n - 1) * (stdev_val ** 2) / chi2_high) if chi2_high > 0 else 0.0

        # Summary Table for Result
        summary_rows = [
            ["Anderson-Darling Normality Test", ""],
            ["  A-Squared", f"{a_sq:.3f}"],
            ["  P-Value", f"{ad_p:.4f}"],
            ["Mean", f"{mean_val:.4f}"],
            ["StDev", f"{stdev_val:.4f}"],
            ["Variance", f"{var_val:.4f}"],
            ["Skewness", f"{skew_val:.4f}"],
            ["Kurtosis", f"{kurt_val:.4f}"],
            ["N", str(n)],
            ["Minimum", f"{min_val:.4f}"],
            ["1st Quartile", f"{q1_val:.4f}"],
            ["Median", f"{med_val:.4f}"],
            ["3rd Quartile", f"{q3_val:.4f}"],
            ["Maximum", f"{max_val:.4f}"],
            [f"{params.confidence_level}% Confidence Interval for Mean", f"({mean_ci[0]:.4f}, {mean_ci[1]:.4f})"],
            [f"{params.confidence_level}% Confidence Interval for Median", f"({med_ci_low:.4f}, {med_ci_high:.4f})"],
            [f"{params.confidence_level}% Confidence Interval for StDev", f"({stdev_ci_low:.4f}, {stdev_ci_high:.4f})"],
        ]

        text_lines = [
            f"Summary Report for {params.variable}",
            "",
            f"Anderson-Darling Normality Test",
            f"  A-Squared: {a_sq:.3f}    P-Value: {ad_p:.4f}",
            "",
            f"Descriptive Statistics:",
            f"  Mean:      {mean_val:>10.4f}    Min:    {min_val:>10.4f}",
            f"  StDev:     {stdev_val:>10.4f}    Q1:     {q1_val:>10.4f}",
            f"  Variance:  {var_val:>10.4f}    Median: {med_val:>10.4f}",
            f"  Skewness:  {skew_val:>10.4f}    Q3:     {q3_val:>10.4f}",
            f"  Kurtosis:  {kurt_val:>10.4f}    Max:    {max_val:>10.4f}",
            f"  N:         {n:>10}",
            "",
            f"{params.confidence_level:.1f}% Confidence Intervals:",
            f"  Mean:   ({mean_ci[0]:.4f}, {mean_ci[1]:.4f})",
            f"  Median: ({med_ci_low:.4f}, {med_ci_high:.4f})",
            f"  StDev:  ({stdev_ci_low:.4f}, {stdev_ci_high:.4f})",
        ]

        # Multi-panel Graphical Summary Plot
        x_min, x_max = min_val, max_val
        x_span = max(0.1, x_max - x_min)
        x_curve = np.linspace(x_min - 0.1 * x_span, x_max + 0.1 * x_span, 120)
        y_curve = stats.norm.pdf(x_curve, mean_val, stdev_val)

        plot_data = [
            # 1. Histogram (Top Panel)
            {
                "type": "histogram",
                "x": raw_series.tolist(),
                "name": "Data",
                "histnorm": "probability density",
                "xaxis": "x",
                "yaxis": "y",
                "marker": {"color": "rgba(59, 130, 246, 0.7)", "line": {"color": "#1d4ed8", "width": 1}},
            },
            # Normal Fit Line
            {
                "type": "scatter",
                "mode": "lines",
                "x": x_curve.tolist(),
                "y": y_curve.tolist(),
                "name": "Normal Fit",
                "xaxis": "x",
                "yaxis": "y",
                "line": {"color": "#dc2626", "width": 2},
            },
            # 2. Boxplot (Middle Panel)
            {
                "type": "box",
                "x": raw_series.tolist(),
                "name": "Boxplot",
                "xaxis": "x",
                "yaxis": "y2",
                "orientation": "h",
                "marker": {"color": "#2563eb"},
                "boxpoints": "outliers",
            },
            # 3. 95% CIs Error Bars (Bottom Panel)
            {
                "type": "scatter",
                "mode": "markers",
                "x": [mean_val, med_val],
                "y": ["95% CI Mean", "95% CI Median"],
                "error_x": {
                    "type": "data",
                    "symmetric": False,
                    "array": [mean_ci[1] - mean_val, med_ci_high - med_val],
                    "arrayminus": [mean_val - mean_ci[0], med_val - med_ci_low],
                    "color": "#0f766e",
                    "thickness": 2,
                    "width": 8,
                },
                "xaxis": "x",
                "yaxis": "y3",
                "name": "Confidence Intervals",
                "marker": {"color": "#0f766e", "size": 8, "symbol": "diamond"},
            }
        ]

        layout = {
            "title": {
                "text": f"<b>Summary Report for {params.variable}</b>",
                "font": {"size": 16, "color": "#1e293b"},
                "x": 0.5,
                "y": 0.96,
                "yanchor": "top"
            },
            "paper_bgcolor": "#ffffff",
            "plot_bgcolor": "#ffffff",
            "showlegend": False,
            "margin": {"l": 110, "r": 50, "t": 75, "b": 60},
            "height": 520,
            "xaxis": {
                "title": {"text": params.variable, "font": {"size": 13}},
                "showgrid": True,
                "gridcolor": "#ececec",
                "showline": True,
                "linecolor": "#201f1e",
                "linewidth": 1.25,
                "mirror": True,
                "zeroline": False,
                "ticks": "inside",
                "tickcolor": "#201f1e",
                "ticklen": 4,
            },
            # Subplot 1: Histogram
            "yaxis": {
                "domain": [0.45, 1.0],
                "title": {"text": "Density", "font": {"size": 11}},
                "showgrid": True,
                "gridcolor": "#ececec",
                "showline": True,
                "linecolor": "#201f1e",
                "linewidth": 1.25,
                "mirror": True,
                "zeroline": False,
                "ticks": "inside",
                "tickcolor": "#201f1e",
                "ticklen": 4,
            },
            # Subplot 2: Boxplot
            "yaxis2": {
                "domain": [0.26, 0.40],
                "anchor": "x",
                "showticklabels": False,
                "showline": True,
                "linecolor": "#201f1e",
                "linewidth": 1.25,
                "mirror": True,
                "zeroline": False,
                "ticks": "",
            },
            # Subplot 3: Confidence Intervals
            "yaxis3": {
                "domain": [0.0, 0.22],
                "anchor": "x",
                "showgrid": True,
                "gridcolor": "#ececec",
                "showline": True,
                "linecolor": "#201f1e",
                "linewidth": 1.25,
                "mirror": True,
                "zeroline": False,
                "ticks": "inside",
                "tickcolor": "#201f1e",
                "ticklen": 4,
            },

            "annotations": [
                {
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.98,
                    "y": 0.95,
                    "xanchor": "right",
                    "yanchor": "top",
                    "text": f"<b>Anderson-Darling Normality</b><br>A-Squared: {a_sq:.3f}<br>P-Value: {ad_p:.4f}<br><br><b>Mean:</b> {mean_val:.4f}<br><b>StDev:</b> {stdev_val:.4f}<br><b>N:</b> {n}",
                    "showarrow": False,
                    "bordercolor": "#94a3b8",
                    "borderwidth": 1,
                    "borderpad": 6,
                    "bgcolor": "#ffffff",
                    "font": {"size": 11, "color": "#1e293b"},
                }
            ]
        }

        return AnalysisResult(
            title="Graphical Summary",
            subtitle=f"{params.variable} (Conf Level: {params.confidence_level}%)",
            text_output="\n".join(text_lines),
            tables=[TableResult(title=f"Summary Statistics for {params.variable}", headers=["Metric", "Value"], rows=summary_rows)],
            statistics={
                "mean": mean_val,
                "stdev": stdev_val,
                "n": n,
                "ad_stat": a_sq,
                "ad_p": ad_p,
                "ci_mean": list(mean_ci),
                "ci_median": [med_ci_low, med_ci_high]
            },
            plotly_figure={"data": plot_data, "layout": layout}
        )
