"""
1-Sample Wilcoxon Signed Rank Test Plugin for OpenMinitab.
Performs 1-Sample Wilcoxon signed rank test for median (M0), computes Walsh pseudo-median and exact/approximate confidence intervals.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class Wilcoxon1SampleParams(BaseModel):
    variables: List[str] = Field(
        ...,
        description="Variables (Numeric Columns)",
        json_schema_extra={"ui_type": "column_multi_picker", "data_type": "numeric"}
    )
    test_median: float = Field(
        0.0,
        description="Hypothesized Median (M0)"
    )
    alternative: str = Field(
        "two-sided",
        description="Alternative Hypothesis",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "not equal (Median ≠ M0)", "value": "two-sided"},
                {"label": "less than (Median < M0)", "value": "less"},
                {"label": "greater than (Median > M0)", "value": "greater"}
            ]
        }
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%)"
    )
    # Storage Sub-Modal
    store_estimates: bool = Field(
        False,
        description="Store Pseudo-Median Estimates in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_limits: bool = Field(
        False,
        description="Store Confidence Limits in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )


class Wilcoxon1SamplePlugin(AnalysisPlugin):
    id = "nonparam_1sample_wilcoxon"
    name = "1-Sample Wilcoxon"
    menu_path = ["Stat", "Nonparametrics", "1-Sample Wilcoxon"]
    description = "Tests whether the population median equals a hypothesized value (M0) using the Wilcoxon signed rank test."
    param_schema = Wilcoxon1SampleParams

    def execute(self, df: pd.DataFrame, params: Wilcoxon1SampleParams) -> AnalysisResult:
        if not params.variables:
            raise ValueError("Select at least one variable for the 1-Sample Wilcoxon test.")

        m0 = params.test_median
        alt_str = params.alternative
        conf = params.confidence_level
        alpha = 1.0 - conf / 100.0

        summary_rows = []
        text_lines = [
            "Wilcoxon Signed Rank Test",
            "",
            f"Test of median = {m0:.4g} versus median " + ("≠" if alt_str == "two-sided" else "<" if alt_str == "less" else ">") + f" {m0:.4g}",
            "",
            f"  {'Variable':<18} {'N':>6} {'N*':>6} {'Wilcoxon W':>12} {'P-Value':>10} {'Est Median':>12} {'Lower CI':>12} {'Upper CI':>12}",
            f"  {'-'*18} {'-'*6} {'-'*6} {'-'*12} {'-'*10} {'-'*12} {'-'*12} {'-'*12}",
        ]

        traces = []
        storage_estimates = []
        storage_lowers = []
        storage_uppers = []

        for idx, var_name in enumerate(params.variables):
            if var_name not in df.columns:
                continue

            raw = pd.to_numeric(df[var_name], errors="coerce").dropna().to_numpy(dtype=float)
            n_total = len(raw)
            if n_total < 2:
                continue

            diffs = raw - m0
            non_zero_diffs = diffs[diffs != 0]
            n_for_test = len(non_zero_diffs)

            if n_for_test == 0:
                w_stat, p_val = 0.0, 1.0
            else:
                try:
                    res = stats.wilcoxon(non_zero_diffs, alternative=alt_str)
                    w_stat = float(res.statistic)
                    p_val = float(res.pvalue)
                except Exception:
                    w_stat, p_val = 0.0, 1.0

            # Walsh Averages for Pseudo-Median & Hodges-Lehmann CI
            # Walsh averages: (x_i + x_j) / 2 for all i <= j
            walsh_avgs = []
            for i in range(n_total):
                for j in range(i, n_total):
                    walsh_avgs.append((raw[i] + raw[j]) / 2.0)
            walsh_sorted = np.sort(walsh_avgs)
            pseudo_median = float(np.median(walsh_sorted))

            # Approximate confidence limits from Walsh averages
            # Critical rank k for Wilcoxon confidence interval: k = n*(n+1)/4 - z_alpha * sqrt(n*(n+1)*(2n+1)/24)
            n_pairs = len(walsh_sorted)
            z_val = stats.norm.ppf(1.0 - alpha / 2.0)
            sigma_w = np.sqrt(n_total * (n_total + 1) * (2 * n_total + 1) / 24.0)
            mu_w = n_total * (n_total + 1) / 4.0
            k_lower = max(0, int(np.floor(mu_w - z_val * sigma_w)))
            k_upper = min(n_pairs - 1, int(np.ceil(mu_w + z_val * sigma_w)))

            ci_low = float(walsh_sorted[k_lower])
            ci_high = float(walsh_sorted[k_upper])

            summary_rows.append([
                var_name,
                n_total,
                n_for_test,
                round(w_stat, 2),
                round(p_val, 5),
                round(pseudo_median, 4),
                round(ci_low, 4),
                round(ci_high, 4)
            ])

            storage_estimates.append(round(pseudo_median, 4))
            storage_lowers.append(round(ci_low, 4))
            storage_uppers.append(round(ci_high, 4))

            text_lines.append(
                f"  {var_name:<18} {n_total:>6} {n_for_test:>6} {w_stat:>12.2f} {p_val:>10.5f} {pseudo_median:>12.4f} {ci_low:>12.4f} {ci_high:>12.4f}"
            )

            # Trace for plot
            traces.append({
                "x": [var_name],
                "y": [pseudo_median],
                "error_y": {
                    "type": "data",
                    "symmetric": False,
                    "array": [ci_high - pseudo_median],
                    "arrayminus": [pseudo_median - ci_low]
                },
                "mode": "markers",
                "marker": {"size": 10, "color": "#008450"},
                "name": f"{var_name} (Pseudo-Median)"
            })

        # Reference line for H0
        shapes = [{
            "type": "line",
            "xref": "paper",
            "x0": 0,
            "x1": 1,
            "y0": m0,
            "y1": m0,
            "line": {"color": "#d13438", "width": 1.5, "dash": "dash"}
        }]

        layout = {
            "title": {"text": f"<b>1-Sample Wilcoxon Test: Estimated Pseudo-Median & {conf:.0f}% CI</b><br><span style='font-size:11px;color:#605e5c'>Hypothesized Median (M0) = {m0:.4g}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Variable", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Value", "showgrid": True, "gridcolor": "#f3f2f1"},
            "shapes": shapes,
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 50}
        }

        table = TableResult(
            title="Wilcoxon Signed Rank Test Results",
            headers=["Variable", "N", "N for Test", "Wilcoxon W", "P-Value", "Est. Pseudo-Median", f"{conf:.0f}% Lower CI", f"{conf:.0f}% Upper CI"],
            rows=summary_rows
        )

        # Storage
        storage_cols = []
        new_cols_dict: Dict[str, List[Any]] = {}

        if params.store_estimates:
            storage_cols.append({"id": "wilcox_est_median", "name": "Est_Pseudo_Median", "type": "numeric"})
            new_cols_dict["wilcox_est_median"] = storage_estimates

        if params.store_limits:
            storage_cols.append({"id": "wilcox_ci_lower", "name": f"L_{conf:.0f}CI", "type": "numeric"})
            storage_cols.append({"id": "wilcox_ci_upper", "name": f"U_{conf:.0f}CI", "type": "numeric"})
            new_cols_dict["wilcox_ci_lower"] = storage_lowers
            new_cols_dict["wilcox_ci_upper"] = storage_uppers

        action_type = None
        worksheet_data = None
        if storage_cols:
            rows_data = []
            for r_i in range(len(params.variables)):
                r_dict = {}
                for col_spec in storage_cols:
                    c_id = col_spec["id"]
                    val_list = new_cols_dict.get(c_id, [])
                    r_dict[c_id] = val_list[r_i] if r_i < len(val_list) else None
                rows_data.append(r_dict)

            action_type = "worksheet_append_columns"
            worksheet_data = {"columns": storage_cols, "rows": rows_data}

        return AnalysisResult(
            title="1-Sample Wilcoxon Signed Rank Test",
            subtitle=f"Hypothesized Median = {m0:.4g}",
            text_output="\n".join(text_lines),
            tables=[table],
            plotly_figure={"data": traces, "layout": layout},
            action_type=action_type,
            worksheet_data=worksheet_data
        )
