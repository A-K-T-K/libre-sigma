import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class DisplayDescriptivesParams(BaseModel):
    variables: List[str] = Field(
        ...,
        description="Variables to compute statistics for",
        json_schema_extra={"ui_type": "column_multi_picker", "data_type": "numeric"}
    )
    by_variable: Optional[str] = Field(
        None,
        description="By variable (optional group variable)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    graph_histogram: bool = Field(
        True,
        description="Histogram of data with normal curve",
        json_schema_extra={"ui_type": "checkbox"}
    )
    graph_boxplot: bool = Field(
        True,
        description="Boxplot of data",
        json_schema_extra={"ui_type": "checkbox"}
    )


class DisplayDescriptivesPlugin(AnalysisPlugin):
    id = "display_descriptives"
    name = "Display Descriptive Statistics"
    menu_path = ["Stat", "Basic Statistics", "Display Descriptive Statistics"]
    description = "Calculates descriptive statistics (Mean, SE Mean, StDev, Variance, CoefVar, Min, Q1, Median, Q3, Max, IQR, Skewness, Kurtosis) for numeric columns with optional grouping and graphs."
    param_schema = DisplayDescriptivesParams

    def execute(self, df: pd.DataFrame, params: DisplayDescriptivesParams) -> AnalysisResult:
        if not params.variables:
            raise ValueError("Select at least one numeric variable.")

        has_group = bool(params.by_variable and params.by_variable in df.columns)
        
        headers = [
            "Variable",
            *(["By"] if has_group else []),
            "N", "N*", "Mean", "SE Mean", "StDev", "Variance", "CoefVar",
            "Minimum", "Q1", "Median", "Q3", "Maximum", "IQR", "Skewness", "Kurtosis"
        ]
        
        rows: List[List[Any]] = []
        text_lines: List[str] = [
            "Descriptive Statistics: " + ", ".join(params.variables) + (f" by {params.by_variable}" if has_group else ""),
            "",
            f"  {'Variable':<12} " + (f"{'By':<10} " if has_group else "") + f"{'N':>5} {'N*':>4} {'Mean':>10} {'SE Mean':>10} {'StDev':>10} {'Variance':>10} {'CoefVar':>8} {'Min':>9} {'Q1':>9} {'Median':>9} {'Q3':>9} {'Max':>9} {'IQR':>9} {'Skew':>7} {'Kurt':>7}",
            f"  {'-'*12} " + (f"{'-'*10} " if has_group else "") + f"{'-'*5} {'-'*4} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*9} {'-'*9} {'-'*9} {'-'*9} {'-'*9} {'-'*9} {'-'*7} {'-'*7}",
        ]

        plots: List[Dict[str, Any]] = []

        for var_name in params.variables:
            if var_name not in df.columns:
                continue

            if has_group:
                groups = df.groupby(params.by_variable)
            else:
                groups = [(None, df)]

            for grp_val, grp_df in groups:
                series = pd.to_numeric(grp_df[var_name], errors="coerce")
                total_n = len(series)
                valid_series = series.dropna().to_numpy(dtype=float)
                n = len(valid_series)
                n_miss = total_n - n

                if n == 0:
                    continue

                mean_val = float(np.mean(valid_series))
                stdev_val = float(np.std(valid_series, ddof=1)) if n > 1 else 0.0
                var_val = float(np.var(valid_series, ddof=1)) if n > 1 else 0.0
                se_mean = float(stdev_val / np.sqrt(n)) if n > 0 else 0.0
                coef_var = float((stdev_val / mean_val) * 100.0) if mean_val != 0 else 0.0

                min_val = float(np.min(valid_series))
                q1_val = float(np.percentile(valid_series, 25))
                med_val = float(np.median(valid_series))
                q3_val = float(np.percentile(valid_series, 75))
                max_val = float(np.max(valid_series))
                iqr_val = float(q3_val - q1_val)

                skew_val = float(stats.skew(valid_series, bias=False)) if n > 2 else 0.0
                kurt_val = float(stats.kurtosis(valid_series, bias=False)) if n > 3 else 0.0

                row = [
                    var_name,
                    *( [str(grp_val)] if has_group else [] ),
                    n,
                    n_miss,
                    round(mean_val, 4),
                    round(se_mean, 4),
                    round(stdev_val, 4),
                    round(var_val, 4),
                    round(coef_var, 2),
                    round(min_val, 4),
                    round(q1_val, 4),
                    round(med_val, 4),
                    round(q3_val, 4),
                    round(max_val, 4),
                    round(iqr_val, 4),
                    round(skew_val, 2),
                    round(kurt_val, 2),
                ]
                rows.append(row)

                by_str = f"{str(grp_val):<10} " if has_group else ""
                text_lines.append(
                    f"  {var_name:<12} {by_str}{n:>5} {n_miss:>4} {mean_val:>10.4f} {se_mean:>10.4f} {stdev_val:>10.4f} {var_val:>10.4f} {coef_var:>8.2f} {min_val:>9.4f} {q1_val:>9.4f} {med_val:>9.4f} {q3_val:>9.4f} {max_val:>9.4f} {iqr_val:>9.4f} {skew_val:>7.2f} {kurt_val:>7.2f}"
                )

        # Generate Histogram Plot
        if params.graph_histogram and len(params.variables) > 0:
            first_var = params.variables[0]
            clean_first = pd.to_numeric(df[first_var], errors="coerce").dropna().to_numpy(dtype=float)
            if len(clean_first) > 2:
                m = float(np.mean(clean_first))
                s = float(np.std(clean_first, ddof=1))
                x_curve = np.linspace(min(clean_first), max(clean_first), 100)
                y_curve = stats.norm.pdf(x_curve, m, s)

                hist_trace = {
                    "type": "histogram",
                    "x": clean_first.tolist(),
                    "name": "Data",
                    "histnorm": "probability density",
                    "marker": {"color": "rgba(30, 64, 175, 0.65)", "line": {"color": "#1e40af", "width": 1}},
                }
                fit_trace = {
                    "type": "scatter",
                    "x": x_curve.tolist(),
                    "y": y_curve.tolist(),
                    "mode": "lines",
                    "name": f"Normal (Mean={m:.3f}, StDev={s:.3f})",
                    "line": {"color": "#dc2626", "width": 2},
                }
                plots.append({
                    "data": [hist_trace, fit_trace],
                    "layout": {
                        "title": {"text": f"<b>Histogram of {first_var} with Normal Curve</b>", "x": 0.5},
                        "xaxis": {"title": {"text": first_var}},
                        "yaxis": {"title": {"text": "Density"}},
                        "margin": {"l": 60, "r": 40, "t": 60, "b": 50},
                    }
                })

        # Generate Boxplot
        if params.graph_boxplot and len(params.variables) > 0:
            box_traces = []
            for v in params.variables:
                s_vals = pd.to_numeric(df[v], errors="coerce").dropna().tolist()
                box_traces.append({
                    "type": "box",
                    "y": s_vals,
                    "name": v,
                    "boxpoints": "outliers",
                    "marker": {"color": "#0284c7"},
                })
            plots.append({
                "data": box_traces,
                "layout": {
                    "title": {"text": "<b>Boxplot of " + ", ".join(params.variables) + "</b>", "x": 0.5},
                    "yaxis": {"title": {"text": "Value"}},
                    "margin": {"l": 60, "r": 40, "t": 60, "b": 50},
                }
            })

        return AnalysisResult(
            title="Descriptive Statistics",
            subtitle=", ".join(params.variables),
            text_output="\n".join(text_lines),
            tables=[TableResult(title="Descriptive Statistics", headers=headers, rows=rows)],
            plotly_figure=plots[0] if plots else None,
            plotly_figures=plots if len(plots) > 1 else None,
        )
