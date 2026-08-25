"""
Nonparametric Distribution Analysis (Right Censoring) Plugin.
Computes Kaplan-Meier survival probabilities, MTTF (restricted mean), quartiles,
standard errors via Greenwood's formula, and interactive survival step plots.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from lifelines import KaplanMeierFitter

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class NonparametricDistributionParams(BaseModel):
    variables: str = Field(
        ...,
        description="Variables (Lifetime / Time-to-Failure Column)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    censor_col: Optional[str] = Field(
        None,
        description="Censoring Column (Optional)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    censor_val: Optional[str] = Field(
        "0",
        description="Censoring Value (default: 0)",
        json_schema_extra={"ui_type": "text"}
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%)"
    )


class NonparametricDistributionPlugin(AnalysisPlugin):
    id = "reliability_nonparametric_distribution"
    name = "Nonparametric Distribution Analysis"
    menu_path = [
        "Stat",
        "Reliability/Survival",
        "Distribution Analysis (Right Censoring)",
        "Nonparametric Distribution Analysis"
    ]
    description = "Nonparametric Kaplan-Meier Distribution Analysis for right-censored lifetime data."
    param_schema = NonparametricDistributionParams

    def execute(self, df: pd.DataFrame, params: NonparametricDistributionParams) -> AnalysisResult:
        time_col = params.variables
        if time_col not in df.columns:
            raise ValueError(f"Column '{time_col}' not found in active worksheet.")

        sub_cols = [time_col]
        has_censor = bool(params.censor_col and params.censor_col in df.columns)
        if has_censor and params.censor_col:
            sub_cols.append(params.censor_col)

        sub_df = df[sub_cols].dropna().copy()
        durations = pd.to_numeric(sub_df[time_col], errors="coerce")
        valid_mask = durations.notna()
        durations = durations[valid_mask].to_numpy(dtype=float)
        sub_df = sub_df[valid_mask]

        n_total = len(durations)
        if n_total == 0:
            raise ValueError(f"No valid numeric data found in '{time_col}'.")

        # Determine events: 1 = failed / observed, 0 = right censored
        if has_censor and params.censor_col:
            c_val_str = str(params.censor_val) if params.censor_val is not None else "0"
            censor_series = sub_df[params.censor_col].astype(str)
            # If matches censor_val, it's censored (0), otherwise failed (1)
            events = np.where(censor_series == c_val_str, 0, 1)
        else:
            events = np.ones(n_total, dtype=int)

        n_censored = int(np.sum(events == 0))
        n_uncensored = int(np.sum(events == 1))

        # 1. Censoring Information Table
        censoring_table = TableResult(
            title="Censoring Information",
            headers=["Censoring Information", "Count"],
            rows=[
                ["Uncensored value", n_uncensored],
                ["Right censored value", n_censored],
            ]
        )

        # 2. Kaplan-Meier Estimator via lifelines
        conf = params.confidence_level / 100.0
        alpha = 1.0 - conf
        kmf = KaplanMeierFitter(alpha=alpha)
        kmf.fit(durations, event_observed=events)

        times = kmf.timeline
        survival_probs = kmf.survival_function_["KM_estimate"].values

        # Area under KM curve for MTTF
        mttf = 0.0
        for i in range(1, len(times)):
            dt = times[i] - times[i - 1]
            mttf += survival_probs[i - 1] * dt

        median_time = kmf.median_survival_time_

        # Standard error for MTTF
        se_mttf = float(np.std(durations, ddof=1) / np.sqrt(n_total))
        from scipy import stats
        z_crit = float(stats.norm.ppf(1.0 - alpha / 2.0))
        lower_ci = mttf - z_crit * se_mttf if not np.isnan(se_mttf) else np.nan
        upper_ci = mttf + z_crit * se_mttf if not np.isnan(se_mttf) else np.nan

        # Quartiles from Kaplan-Meier curve with floating point epsilon
        def get_percentile_time(p: float) -> float:
            idx = np.where(survival_probs <= p + 1e-9)[0]
            if len(idx) > 0:
                return float(times[idx[0]])
            return np.nan

        q1 = get_percentile_time(0.75)   # 25% failure = 75% survival
        q3 = get_percentile_time(0.25)   # 75% failure = 25% survival
        iqr = q3 - q1 if (not np.isnan(q3) and not np.isnan(q1)) else np.nan

        chars_table = TableResult(
            title="Characteristics of Variable",
            headers=[
                "Mean(MTTF)",
                "Standard Error",
                f"{params.confidence_level:.1f}% Normal CI Lower",
                f"{params.confidence_level:.1f}% Normal CI Upper",
                "Q1",
                "Median",
                "Q3",
                "IQR"
            ],
            rows=[[
                round(float(mttf), 5),
                round(float(se_mttf), 6) if not np.isnan(se_mttf) else None,
                round(float(lower_ci), 5) if not np.isnan(lower_ci) else None,
                round(float(upper_ci), 5) if not np.isnan(upper_ci) else None,
                round(float(q1), 4) if not np.isnan(q1) else None,
                round(float(median_time), 4) if not np.isnan(median_time) else None,
                round(float(q3), 4) if not np.isnan(q3) else None,
                round(float(iqr), 4) if not np.isnan(iqr) else None,
            ]]
        )

        # 3. Kaplan-Meier Estimates Table
        evt_table = kmf.event_table
        ci_table = kmf.confidence_interval_
        km_vars = kmf._cumulative_sq_.values
        se_table = survival_probs * np.sqrt(km_vars)

        km_rows = []
        for i, t in enumerate(times):
            if t == 0 and len(times) > 1:
                continue
            at_risk = int(evt_table.loc[t, "at_risk"])
            failed = int(evt_table.loc[t, "observed"])
            surv_p = float(survival_probs[i])
            se_p = float(se_table[i])
            ci_low = float(ci_table.iloc[i, 0])
            ci_up = float(ci_table.iloc[i, 1])

            km_rows.append([
                float(t),
                at_risk,
                failed,
                round(surv_p, 6),
                round(se_p, 6),
                round(ci_low, 6),
                round(ci_up, 6)
            ])

        km_table = TableResult(
            title="Kaplan-Meier Estimates",
            headers=[
                "Time",
                "Number at Risk",
                "Number Failed",
                "Survival Probability",
                "Standard Error",
                f"{params.confidence_level:.1f}% Normal CI Lower",
                f"{params.confidence_level:.1f}% Normal CI Upper"
            ],
            rows=km_rows
        )

        # 4. Interactive Plotly Survival Plot
        plot_data = [
            {
                "x": times.tolist(),
                "y": survival_probs.tolist(),
                "type": "scatter",
                "mode": "lines+markers",
                "line": {"shape": "hv", "color": "#008450", "width": 2},
                "marker": {"symbol": "circle", "size": 6},
                "name": "Kaplan-Meier Survival"
            },
            {
                "x": times.tolist(),
                "y": ci_table.iloc[:, 0].tolist(),
                "type": "scatter",
                "mode": "lines",
                "line": {"shape": "hv", "color": "rgba(0,132,80,0.35)", "dash": "dash"},
                "name": f"{params.confidence_level:.1f}% CI Lower"
            },
            {
                "x": times.tolist(),
                "y": ci_table.iloc[:, 1].tolist(),
                "type": "scatter",
                "mode": "lines",
                "line": {"shape": "hv", "color": "rgba(0,132,80,0.35)", "dash": "dash"},
                "fill": "tonexty",
                "fillcolor": "rgba(0,132,80,0.08)",
                "name": f"{params.confidence_level:.1f}% CI Upper"
            }
        ]

        layout = {
            "title": f"Nonparametric Survival Plot for {time_col}",
            "xaxis": {"title": time_col, "gridcolor": "#f0f0f0"},
            "yaxis": {"title": "Survival Probability", "range": [0, 1.05], "gridcolor": "#f0f0f0"},
            "showlegend": True,
            "template": "plotly_white"
        }

        text_lines = [
            f"Distribution Analysis: {time_col}",
            f"Variable: {time_col}",
            "",
            "Nonparametric Estimates",
            f"Mean (MTTF): {mttf:.5f}  SE: {se_mttf:.6f}  {params.confidence_level:.1f}% CI: ({lower_ci:.5f}, {upper_ci:.5f})",
            f"Median: {median_time}  Q1: {q1}  Q3: {q3}  IQR: {iqr}",
        ]

        return AnalysisResult(
            title=f"Distribution Analysis: {time_col}",
            subtitle="Nonparametric Distribution Analysis (Right Censoring)",
            text_output="\n".join(text_lines),
            tables=[censoring_table, chars_table, km_table],
            plotly_figure={"data": plot_data, "layout": layout}
        )
