"""
Test for Equal Variances (Homoscedasticity) Plugin for OpenMinitab.
Performs Bartlett's test, Levene's test, and Brown-Forsythe test with Bonferroni-adjusted standard deviation confidence intervals.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class EqualVariancesParams(BaseModel):
    response_column: str = Field(
        ...,
        description="Response Variable (Continuous Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    factor_column: str = Field(
        ...,
        description="Factor Variable (Categorical Grouping)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%) - Default: 95.0"
    )


class TestEqualVariancesPlugin(AnalysisPlugin):
    id = "test_equal_variances"
    name = "Test for Equal Variances"
    menu_path = ["Stat", "ANOVA", "Test for Equal Variances"]
    description = "Tests for equality of variances across factor levels using Bartlett's, Levene's, and Brown-Forsythe tests with Bonferroni CIs."
    param_schema = EqualVariancesParams

    def execute(self, df: pd.DataFrame, params: EqualVariancesParams) -> AnalysisResult:
        y_col = params.response_column
        f_col = params.factor_column

        if y_col not in df.columns or f_col not in df.columns:
            raise ValueError("Select valid response and factor variables.")

        sub_df = df[[y_col, f_col]].dropna().copy().reset_index(drop=True)
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n_total = len(sub_df)
        if n_total < 4:
            raise ValueError("Test for Equal Variances requires at least 4 observations.")

        groups = sorted(sub_df[f_col].astype(str).unique())
        k = len(groups)
        if k < 2:
            raise ValueError("Factor variable must contain at least 2 distinct levels.")

        grp_data = [sub_df[sub_df[f_col].astype(str) == g][y_col].to_numpy(dtype=float) for g in groups]
        grp_sizes = np.array([len(g) for g in grp_data], dtype=int)
        grp_stds = np.array([np.std(g, ddof=1) if len(g) > 1 else 0.0 for g in grp_data], dtype=float)

        alpha = 1.0 - (params.confidence_level / 100.0)
        bonf_alpha = alpha / k # Bonferroni correction per group

        # -------------------------------------------------------------
        # 1. Bartlett's Test (Normal Data)
        # -------------------------------------------------------------
        pooled_var = float(np.sum((grp_sizes - 1) * (grp_stds ** 2)) / (n_total - k))
        c_denom = 1.0 + (1.0 / (3.0 * (k - 1))) * (np.sum(1.0 / (grp_sizes - 1)) - (1.0 / (n_total - k)))
        numerator_bartlett = (n_total - k) * math.log(max(1e-12, pooled_var)) - np.sum((grp_sizes - 1) * np.log(np.maximum(1e-12, grp_stds ** 2)))
        chi_bartlett = max(0.0, numerator_bartlett / c_denom)
        df_bartlett = k - 1
        p_bartlett = float(1.0 - stats.chi2.cdf(chi_bartlett, df=df_bartlett))

        # -------------------------------------------------------------
        # 2. Levene's Test (Deviations from Mean)
        # -------------------------------------------------------------
        levene_stat, p_levene = stats.levene(*grp_data, center='mean')

        # -------------------------------------------------------------
        # 3. Brown-Forsythe Test (Deviations from Median)
        # -------------------------------------------------------------
        bf_stat, p_bf = stats.levene(*grp_data, center='median')

        # -------------------------------------------------------------
        # Bonferroni-Adjusted Confidence Intervals for Standard Deviations
        # -------------------------------------------------------------
        sd_rows = []
        ci_lowers = []
        ci_uppers = []

        for i, g in enumerate(groups):
            nu_i = grp_sizes[i] - 1
            s_i = grp_stds[i]
            if nu_i >= 1 and s_i > 1e-9:
                chi2_upper = stats.chi2.ppf(1.0 - bonf_alpha / 2.0, df=nu_i)
                chi2_lower = stats.chi2.ppf(bonf_alpha / 2.0, df=nu_i)
                ci_low = s_i * math.sqrt(nu_i / chi2_upper)
                ci_high = s_i * math.sqrt(nu_i / max(1e-9, chi2_lower))
            else:
                ci_low = s_i
                ci_high = s_i

            ci_lowers.append(ci_low)
            ci_uppers.append(ci_high)

            sd_rows.append([
                g,
                str(grp_sizes[i]),
                f"{s_i:.4f}",
                f"{s_i ** 2:.4f}",
                f"({ci_low:.4f}, {ci_high:.4f})"
            ])

        sd_table = TableResult(
            title=f"Descriptive Statistics & {params.confidence_level:.0f}% Bonferroni Confidence Intervals for Standard Deviations",
            headers=[f_col, "N", "StDev", "Variance", "Bonferroni 95% CI for StDev"],
            rows=sd_rows
        )

        test_table = TableResult(
            title="Hypothesis Tests for Equality of Variances",
            headers=["Method", "Test Statistic", "DF / Num DF", "Denom DF", "p-Value"],
            rows=[
                ["Bartlett's Test (Normal Data)", f"{chi_bartlett:.2f}", str(df_bartlett), "---", f"{p_bartlett:.4f}" if p_bartlett >= 0.0001 else "< 0.0001"],
                ["Levene's Test (Any Continuous)", f"{levene_stat:.2f}", str(k - 1), str(n_total - k), f"{p_levene:.4f}" if p_levene >= 0.0001 else "< 0.0001"],
                ["Brown-Forsythe (Skewed Data)", f"{bf_stat:.2f}", str(k - 1), str(n_total - k), f"{p_bf:.4f}" if p_bf >= 0.0001 else "< 0.0001"]
            ]
        )

        # Plotly Standard Deviation Error Bar Plot
        traces = [
            {
                "type": "scatter",
                "mode": "markers",
                "x": groups,
                "y": grp_stds.tolist(),
                "error_y": {
                    "type": "data",
                    "symmetric": False,
                    "array": [h - s for h, s in zip(ci_uppers, grp_stds)],
                    "arrayminus": [s - l for l, s in zip(ci_lowers, grp_stds)],
                    "visible": True,
                    "color": "#0078d4",
                    "thickness": 2,
                    "width": 6
                },
                "name": "Sample StDev (Bonferroni CI)",
                "marker": {"color": "#0078d4", "size": 8}
            },
            {
                "type": "scatter",
                "mode": "lines",
                "x": [-0.5, k - 0.5],
                "y": [math.sqrt(pooled_var), math.sqrt(pooled_var)],
                "name": f"Pooled StDev ({math.sqrt(pooled_var):.3f})",
                "line": {"color": "#008450", "dash": "dash"}
            }
        ]

        plotly_fig = {
            "data": traces,
            "layout": {
                "title": f"Test for Equal Variances for {y_col} by {f_col}",
                "xaxis": {"title": f_col, "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": "Standard Deviation", "showgrid": True, "gridcolor": "#ececec"},
                "annotations": [
                    {
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.95,
                        "y": 0.95,
                        "text": f"<b>Bartlett p-value:</b> {p_bartlett:.4f}<br><b>Levene p-value:</b> {p_levene:.4f}<br><b>Brown-Forsythe p-value:</b> {p_bf:.4f}",
                        "showarrow": False,
                        "bgcolor": "rgba(255,255,255,0.85)",
                        "bordercolor": "#d2d0ce",
                        "borderwidth": 1
                    }
                ]
            }
        }

        return AnalysisResult(
            title=f"Test for Equal Variances: {y_col} by {f_col}",
            subtitle=f"Bartlett p = {p_bartlett:.4f} | Levene p = {p_levene:.4f} | Brown-Forsythe p = {p_bf:.4f}",
            tables=[sd_table, test_table],
            plotly_figure=plotly_fig,
            statistics={
                "bartlett_stat": chi_bartlett,
                "bartlett_p": p_bartlett,
                "levene_stat": float(levene_stat),
                "levene_p": float(p_levene),
                "brown_forsythe_stat": float(bf_stat),
                "brown_forsythe_p": float(p_bf),
                "pooled_stdev": math.sqrt(pooled_var)
            }
        )
