"""
Chi-Square Goodness-of-Fit Test (One Variable) Plugin for OpenMinitab.
Tests whether observed frequency distributions of a discrete variable match specified theoretical (equal or custom) proportions.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class ChiSquareGOFParams(BaseModel):
    observed_counts: str = Field(
        ...,
        description="Observed Counts or Raw Categorical Column",
        json_schema_extra={"ui_type": "column_picker"}
    )
    category_labels: Optional[str] = Field(
        None,
        description="Category Names / Labels (Optional Column)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    proportion_mode: str = Field(
        "equal",
        description="Expected Proportions",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Equal Proportions (1/k for all categories)", "value": "equal"},
                {"label": "User-Specified Proportions", "value": "user"}
            ]
        }
    )
    custom_proportions: Optional[str] = Field(
        None,
        description="Custom Proportions (comma-separated, e.g. 0.25, 0.25, 0.50)",
        json_schema_extra={"sub_modal": "Options..."}
    )


class ChiSquareGOFPlugin(AnalysisPlugin):
    id = "tables_chisq_gof"
    name = "Chi-Square Goodness-of-Fit (One Variable)"
    menu_path = ["Stat", "Tables", "Chi-Square Goodness-of-Fit Test (One Variable)"]
    description = "Tests whether the observed frequencies of a single categorical variable follow a specified distribution."
    param_schema = ChiSquareGOFParams

    def execute(self, df: pd.DataFrame, params: ChiSquareGOFParams) -> AnalysisResult:
        obs_col = params.observed_counts
        if obs_col not in df.columns:
            raise ValueError(f"Column '{obs_col}' not found in active worksheet.")

        raw_series = df[obs_col].dropna()
        if len(raw_series) < 2:
            raise ValueError("Chi-Square Goodness-of-Fit test requires at least 2 observations.")

        # Check if the column is already numeric counts or raw categorical observations
        num_obs = pd.to_numeric(raw_series, errors="coerce")
        is_already_counts = num_obs.notna().all() and (params.category_labels is not None and params.category_labels in df.columns)

        if is_already_counts and params.category_labels:
            cat_names = df[params.category_labels].dropna().astype(str).tolist()
            obs_counts = num_obs.tolist()
            if len(cat_names) != len(obs_counts):
                min_len = min(len(cat_names), len(obs_counts))
                cat_names = cat_names[:min_len]
                obs_counts = obs_counts[:min_len]
        else:
            val_counts = raw_series.value_counts(sort=False)
            cat_names = [str(k) for k in val_counts.index]
            obs_counts = [float(v) for v in val_counts.values]

        k = len(cat_names)
        if k < 2:
            raise ValueError("Chi-Square Goodness-of-Fit test requires at least 2 categories.")

        total_n = float(np.sum(obs_counts))

        # Expected frequencies
        if params.proportion_mode == "user" and params.custom_proportions:
            try:
                user_props = [float(x.strip()) for x in params.custom_proportions.split(",")]
                if len(user_props) != k:
                    raise ValueError(f"Number of custom proportions ({len(user_props)}) must match number of categories ({k}).")
                user_props = np.array(user_props, dtype=float)
                prop_sum = np.sum(user_props)
                if prop_sum <= 0:
                    raise ValueError("Proportions must sum to a positive value.")
                expected_props = user_props / prop_sum
            except Exception as e:
                raise ValueError(f"Invalid custom proportions: {e}")
        else:
            expected_props = np.full(k, 1.0 / k, dtype=float)

        expected_counts = expected_props * total_n

        # Chi-Square test
        chisq_res = stats.chisquare(obs_counts, f_exp=expected_counts)
        chi2_stat = float(chisq_res.statistic)
        p_val = float(chisq_res.pvalue)
        df_deg = k - 1

        # Contribution per cell: (O - E)^2 / E
        contributions = ((np.array(obs_counts) - expected_counts) ** 2) / np.where(expected_counts > 0, expected_counts, 1e-6)

        table_rows = []
        for i in range(k):
            table_rows.append([
                cat_names[i],
                int(obs_counts[i]),
                round(float(expected_props[i]), 4),
                round(float(expected_counts[i]), 2),
                round(float(contributions[i]), 4)
            ])

        # Plotly chart comparing Observed vs Expected
        traces = [
            {
                "x": cat_names,
                "y": obs_counts,
                "type": "bar",
                "name": "Observed",
                "marker": {"color": "#008450"}
            },
            {
                "x": cat_names,
                "y": expected_counts.tolist(),
                "type": "bar",
                "name": "Expected",
                "marker": {"color": "#005a9e"}
            }
        ]

        layout = {
            "title": {"text": f"<b>Chi-Square Goodness-of-Fit: Observed vs. Expected ({obs_col})</b><br><span style='font-size:11px;color:#605e5c'>Chi-Square = {chi2_stat:.3f}, DF = {df_deg}, p-value = {p_val:.5f}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Category", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Count", "showgrid": True, "gridcolor": "#f3f2f1"},
            "barmode": "group",
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 55}
        }

        table = TableResult(
            title=f"Chi-Square Goodness-of-Fit Test for {obs_col}",
            headers=["Category", "Observed", "Test Proportion", "Expected", "Contribution to Chi-Sq"],
            rows=table_rows
        )

        test_table = TableResult(
            title="Chi-Square Test Summary",
            headers=["Total N", "Degrees of Freedom (DF)", "Chi-Square", "P-Value"],
            rows=[[int(total_n), df_deg, round(chi2_stat, 3), round(p_val, 5)]]
        )

        text_lines = [
            f"Chi-Square Goodness-of-Fit Test for {obs_col}",
            "",
            f"  {'Category':<16} {'Observed':>10} {'Test Prop':>12} {'Expected':>12} {'Contribution':>14}",
            f"  {'-'*16} {'-'*10} {'-'*12} {'-'*12} {'-'*14}",
        ]
        for r in table_rows:
            text_lines.append(f"  {r[0]:<16} {r[1]:>10} {r[2]:>12.4f} {r[3]:>12.2f} {r[4]:>14.4f}")

        text_lines += [
            "",
            f"N = {int(total_n)}   DF = {df_deg}   Chi-Square = {chi2_stat:.3f}   P-Value = {p_val:.5f}"
        ]

        return AnalysisResult(
            title="Chi-Square Goodness-of-Fit Test",
            subtitle=f"{obs_col}",
            text_output="\n".join(text_lines),
            tables=[table, test_table],
            plotly_figure={"data": traces, "layout": layout}
        )
