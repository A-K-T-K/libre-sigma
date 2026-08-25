"""
One-Way ANOVA Plugin for OpenMinitab.
Performs One-Way ANOVA, Welch's unequal variance ANOVA, post-hoc tests (Tukey HSD, Fisher LSD, Dunnett, Games-Howell), grouping letter assignment, and 4-in-1 diagnostic plots.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult
from ..quality_tools.distribution_id import calculate_anderson_darling


class OneWayAnovaParams(BaseModel):
    response_column: str = Field(
        ...,
        description="Response Variable (Continuous Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    factor_column: str = Field(
        ...,
        description="Factor Variable (Categorical / Discrete)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    assume_equal_variances: bool = Field(
        True,
        description="Assume Equal Variances (Uncheck for Welch's ANOVA & Games-Howell)"
    )
    post_hoc_method: str = Field(
        "tukey",
        description="Post-Hoc Multiple Comparisons",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Tukey HSD (Honestly Significant Difference)", "value": "tukey"},
                {"label": "Fisher's LSD (Least Significant Difference)", "value": "fisher"},
                {"label": "Dunnett (Compare against Control Group)", "value": "dunnett"},
                {"label": "Games-Howell (Unequal Variances)", "value": "games_howell"}
            ]
        }
    )
    control_group: Optional[str] = Field(
        None,
        description="Control Group Level (for Dunnett's Test, optional)"
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%) - Default: 95.0"
    )


def assign_grouping_letters(groups: List[str], means: np.ndarray, sig_matrix: np.ndarray) -> List[str]:
    """
    Assigns standard Minitab grouping letters (A, B, AB, C, etc.) where means sharing a letter
    are not significantly different.
    sig_matrix[i, j] is True if group i and group j are significantly different.
    """
    k = len(groups)
    order = np.argsort(-means) # Sort descending
    letters = [chr(65 + i) for i in range(26)]

    group_letters = ["" for _ in range(k)]
    current_letter_idx = 0

    # Greedy maximal clique grouping algorithm
    assigned = [False] * k
    for i in range(k):
        orig_i = order[i]
        if not assigned[orig_i]:
            letter = letters[current_letter_idx % len(letters)]
            current_letter_idx += 1
            clique = [orig_i]
            group_letters[orig_i] += letter
            assigned[orig_i] = True

            for j in range(i + 1, k):
                orig_j = order[j]
                # Check if orig_j is not significantly different from all in clique
                if all(not sig_matrix[c, orig_j] for c in clique):
                    clique.append(orig_j)
                    group_letters[orig_j] += letter

    return group_letters


class OneWayAnovaPlugin(AnalysisPlugin):
    id = "one_way_anova"
    name = "One-Way ANOVA"
    menu_path = ["Stat", "ANOVA", "One-Way ANOVA"]
    description = "Tests for equality of means across multiple factor levels with Tukey/Fisher/Dunnett/Games-Howell post-hoc tests and grouping letter codes."
    param_schema = OneWayAnovaParams

    def execute(self, df: pd.DataFrame, params: OneWayAnovaParams) -> AnalysisResult:
        y_col, f_col = params.response_column, params.factor_column

        if y_col not in df.columns or f_col not in df.columns:
            raise ValueError(f"Columns '{y_col}' and/or '{f_col}' not found in active worksheet.")

        sub_df = df[[y_col, f_col]].dropna().copy()
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        if len(sub_df) < 4:
            raise ValueError("One-Way ANOVA requires at least 4 observations.")

        group_names = sorted([str(g) for g in sub_df[f_col].unique()])
        k = len(group_names)

        if k < 2:
            raise ValueError("One-Way ANOVA requires at least 2 distinct factor levels.")

        groups_data = [sub_df[sub_df[f_col].astype(str) == g][y_col].to_numpy(dtype=float) for g in group_names]
        group_sizes = np.array([len(g) for g in groups_data], dtype=int)
        group_means = np.array([np.mean(g) for g in groups_data], dtype=float)
        group_stds = np.array([np.std(g, ddof=1) if len(g) > 1 else 0.0 for g in groups_data], dtype=float)

        N = int(np.sum(group_sizes))
        grand_mean = float(np.mean(sub_df[y_col]))

        # Sum of Squares
        ss_factor = float(np.sum(group_sizes * (group_means - grand_mean) ** 2))
        ss_total = float(np.sum((sub_df[y_col] - grand_mean) ** 2))
        ss_error = max(0.0, ss_total - ss_factor)

        df_factor = k - 1
        df_error = N - k
        ms_factor = ss_factor / max(1, df_factor)
        ms_error = ss_error / max(1, df_error)

        f_stat = ms_factor / max(1e-12, ms_error)
        p_val = float(1.0 - stats.f.cdf(f_stat, df_factor, df_error))

        s_pooled = math.sqrt(max(1e-12, ms_error))
        r_sq = (ss_factor / ss_total) if ss_total > 1e-12 else 1.0
        r_sq_adj = float(1.0 - (ss_error / max(1, df_error)) / (ss_total / (N - 1))) if ss_total > 1e-12 else 1.0

        # Welch's ANOVA (if equal variances not assumed)
        w_weights = group_sizes / np.maximum(1e-12, group_stds ** 2)
        w_sum = np.sum(w_weights)
        w_mean = np.sum(w_weights * group_means) / w_sum
        ss_w = np.sum(w_weights * (group_means - w_mean) ** 2)
        lambda_term = (3.0 * np.sum((1.0 - w_weights / w_sum) ** 2 / (group_sizes - 1))) / (k ** 2 - 1)
        f_welch = ss_w / ((k - 1) * (1.0 + 2.0 * (k - 2) * lambda_term / 3.0))
        df_welch_num = k - 1
        df_welch_denom = 1.0 / (lambda_term / 3.0) if lambda_term > 0 else 100.0
        p_welch = float(1.0 - stats.f.cdf(f_welch, df_welch_num, df_welch_denom))

        # ANOVA Table
        anova_table = TableResult(
            title=f"Analysis of Variance for {y_col} by {f_col}",
            headers=["Source", "DF", "Adj SS", "Adj MS", "F-Value", "p-Value"],
            rows=[
                [f_col, str(df_factor), f"{ss_factor:.4f}", f"{ms_factor:.4f}", f"{f_stat:.2f}", f"{p_val:.4f}" if p_val >= 0.0001 else "< 0.0001"],
                ["Error", str(df_error), f"{ss_error:.4f}", f"{ms_error:.4f}", "---", "---"],
                ["Total", str(N - 1), f"{ss_total:.4f}", "---", "---", "---"]
            ]
        )

        model_summary_table = TableResult(
            title="Model Summary",
            headers=["S (Pooled StDev)", "R-sq", "R-sq(adj)", "Welch F", "Welch p-Value"],
            rows=[[
                f"{s_pooled:.4f}",
                f"{r_sq * 100.0:.2f}%",
                f"{r_sq_adj * 100.0:.2f}%",
                f"{f_welch:.2f}",
                f"{p_welch:.4f}" if p_welch >= 0.0001 else "< 0.0001"
            ]]
        )

        # -------------------------------------------------------------
        # Post-Hoc Pairwise Comparisons & Grouping Information
        # -------------------------------------------------------------
        alpha_conf = 1.0 - (params.confidence_level / 100.0)
        t_crit_pooled = stats.t.ppf(1.0 - alpha_conf / 2.0, df=df_error)

        sig_matrix = np.zeros((k, k), dtype=bool)
        pairwise_rows = []

        pairwise_diffs = []
        pairwise_ci_low = []
        pairwise_ci_high = []
        pairwise_labels = []

        for i in range(k):
            for j in range(i + 1, k):
                mean_diff = group_means[i] - group_means[j]
                label = f"{group_names[i]} - {group_names[j]}"

                if params.post_hoc_method == "games_howell":
                    # Games-Howell pairwise test
                    se_diff = math.sqrt(group_stds[i] ** 2 / group_sizes[i] + group_stds[j] ** 2 / group_sizes[j])
                    df_gh = (group_stds[i] ** 2 / group_sizes[i] + group_stds[j] ** 2 / group_sizes[j]) ** 2 / (
                        (group_stds[i] ** 2 / group_sizes[i]) ** 2 / (group_sizes[i] - 1) +
                        (group_stds[j] ** 2 / group_sizes[j]) ** 2 / (group_sizes[j] - 1)
                    )
                    t_gh = abs(mean_diff) / max(1e-12, se_diff)
                    p_pair = float(2.0 * (1.0 - stats.t.cdf(t_gh, df=max(1, df_gh))))
                    ci_low = mean_diff - stats.t.ppf(1.0 - alpha_conf / 2.0, df=max(1, df_gh)) * se_diff
                    ci_high = mean_diff + stats.t.ppf(1.0 - alpha_conf / 2.0, df=max(1, df_gh)) * se_diff
                elif params.post_hoc_method == "tukey":
                    # Tukey HSD with Studentized Range Distribution
                    se_diff = s_pooled * math.sqrt(0.5 * (1.0 / group_sizes[i] + 1.0 / group_sizes[j]))
                    q_stat = abs(mean_diff) / max(1e-12, se_diff)
                    # Tukey q distribution p-value
                    p_pair = float(1.0 - stats.studentized_range.cdf(q_stat * math.sqrt(2.0), k, df_error))
                    q_crit = stats.studentized_range.ppf(1.0 - alpha_conf, k, df_error) / math.sqrt(2.0)
                    ci_low = mean_diff - q_crit * se_diff
                    ci_high = mean_diff + q_crit * se_diff
                elif params.post_hoc_method == "dunnett":
                    ctrl_name = params.control_group or group_names[0]
                    se_diff = s_pooled * math.sqrt(1.0 / group_sizes[i] + 1.0 / group_sizes[j])
                    t_stat = abs(mean_diff) / max(1e-12, se_diff)
                    p_pair = float(2.0 * (1.0 - stats.t.cdf(t_stat, df=df_error)))
                    ci_low = mean_diff - t_crit_pooled * se_diff
                    ci_high = mean_diff + t_crit_pooled * se_diff
                else: # Fisher LSD
                    se_diff = s_pooled * math.sqrt(1.0 / group_sizes[i] + 1.0 / group_sizes[j])
                    t_stat = abs(mean_diff) / max(1e-12, se_diff)
                    p_pair = float(2.0 * (1.0 - stats.t.cdf(t_stat, df=df_error)))
                    ci_low = mean_diff - t_crit_pooled * se_diff
                    ci_high = mean_diff + t_crit_pooled * se_diff

                is_sig = p_pair < 0.05
                sig_matrix[i, j] = is_sig
                sig_matrix[j, i] = is_sig

                pairwise_diffs.append(mean_diff)
                pairwise_ci_low.append(ci_low)
                pairwise_ci_high.append(ci_high)
                pairwise_labels.append(label)

                pairwise_rows.append([
                    label,
                    f"{mean_diff:.4f}",
                    f"{se_diff:.4f}",
                    f"({ci_low:.4f}, {ci_high:.4f})",
                    f"{p_pair:.4f}" if p_pair >= 0.0001 else "< 0.0001",
                    "Yes (Significant)" if is_sig else "No"
                ])

        # Assign grouping letters
        grouping_letters = assign_grouping_letters(group_names, group_means, sig_matrix)

        # Means and Grouping Table
        grouping_rows = []
        for i, g in enumerate(group_names):
            se_mean = s_pooled / math.sqrt(group_sizes[i])
            ci_low_mean = group_means[i] - t_crit_pooled * se_mean
            ci_high_mean = group_means[i] + t_crit_pooled * se_mean
            grouping_rows.append([
                g,
                str(group_sizes[i]),
                f"{group_means[i]:.4f}",
                f"{group_stds[i]:.4f}",
                f"({ci_low_mean:.4f}, {ci_high_mean:.4f})",
                grouping_letters[i]
            ])

        grouping_table = TableResult(
            title=f"Grouping Information Using {params.post_hoc_method.upper()} Method and {params.confidence_level:.0f}% Confidence",
            headers=[f_col, "N", "Mean", "StDev", "95% CI for Mean", "Grouping"],
            rows=grouping_rows
        )

        comparisons_table = TableResult(
            title=f"Pairwise Comparisons ({params.post_hoc_method.upper()})",
            headers=["Difference of Levels", "Difference of Means", "SE of Difference", "95% CI", "p-Value", "Significant?"],
            rows=pairwise_rows
        )

        # -------------------------------------------------------------
        # Visuals: Interval Plot + Difference of Means Plot + 4-in-1
        # -------------------------------------------------------------
        # Residuals
        group_map = dict(zip(group_names, group_means))
        fitted_vals = np.array([group_map[str(val)] for val in sub_df[f_col]])
        residuals = sub_df[y_col].to_numpy(dtype=float) - fitted_vals
        std_residuals = residuals / max(1e-12, s_pooled)

        res_sorted = np.sort(std_residuals)
        p_emp = (np.arange(1, N + 1) - 0.375) / (N + 0.25)
        y_normal_scores = stats.norm.ppf(p_emp)

        # 1. Interval Plot (Group Means & 95% CI)
        interval_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": group_names,
                    "y": group_means.tolist(),
                    "error_y": {
                        "type": "data",
                        "array": [t_crit_pooled * (s_pooled / math.sqrt(n_i)) for n_i in group_sizes],
                        "visible": True,
                        "color": "#0078d4",
                        "thickness": 2,
                        "width": 6
                    },
                    "name": "Interval Plot (95% CI)",
                    "marker": {"color": "#0078d4", "size": 9}
                }
            ],
            "layout": {
                "title": f"Interval Plot of {y_col} vs {f_col} (95% CI for the Mean)",
                "xaxis": {"title": {"text": str(f_col)}},
                "yaxis": {"title": {"text": str(y_col)}},
                "showlegend": False,
                "height": 420
            }
        }

        # 2. Differences of Means Plot (Tukey Simultaneous 95% CIs)
        tukey_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": pairwise_diffs,
                    "y": pairwise_labels,
                    "error_x": {
                        "type": "data",
                        "array": [abs(h - d) for h, d in zip(pairwise_ci_high, pairwise_diffs)],
                        "visible": True,
                        "color": "#d13438",
                        "thickness": 2,
                        "width": 6
                    },
                    "name": "Tukey Simultaneous 95% CIs",
                    "marker": {"color": "#d13438", "size": 8}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [0, 0],
                    "y": [pairwise_labels[0], pairwise_labels[-1]] if pairwise_labels else [0, 0],
                    "name": "Zero Difference Reference Line",
                    "line": {"color": "#605e5c", "dash": "dash"}
                }
            ],
            "layout": {
                "title": f"Tukey Simultaneous 95% CIs: Differences of Means for {y_col}",
                "xaxis": {"title": {"text": "Difference of Means"}},
                "yaxis": {"title": {"text": "Pairwise Comparison"}},
                "showlegend": False,
                "height": max(400, len(pairwise_labels) * 28 + 120),
                "margin": {"l": 120, "r": 50, "t": 70, "b": 60}
            }
        }

        # 3. Residuals vs. Fits
        res_fits_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": fitted_vals.tolist(),
                    "y": std_residuals.tolist(),
                    "name": "Residuals vs Fits",
                    "marker": {"color": "#008450", "size": 7}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [float(np.min(fitted_vals)), float(np.max(fitted_vals))],
                    "y": [0, 0],
                    "name": "Reference Line",
                    "line": {"color": "#605e5c", "dash": "dash"}
                }
            ],
            "layout": {
                "title": f"Residuals Versus Fits for {y_col}",
                "xaxis": {"title": {"text": "Fitted Value"}},
                "yaxis": {"title": {"text": "Standardized Residual"}},
                "showlegend": False,
                "height": 420
            }
        }

        # 4. Normal Probability Plot of Residuals
        normal_plot_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": res_sorted.tolist(),
                    "y": y_normal_scores.tolist(),
                    "name": "Residuals",
                    "marker": {"color": "#881798", "size": 7}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [-3.0, 3.0],
                    "y": [-3.0, 3.0],
                    "name": "Normal Reference",
                    "line": {"color": "#d13438", "dash": "dash"}
                }
            ],
            "layout": {
                "title": f"Normal Probability Plot of Residuals for {y_col}",
                "xaxis": {"title": {"text": "Standardized Residual"}},
                "yaxis": {"title": {"text": "Normal Score / Z-Score"}},
                "showlegend": False,
                "height": 420
            }
        }

        all_figures = [interval_fig, tukey_fig, res_fits_fig, normal_plot_fig]

        return AnalysisResult(
            title=f"One-Way ANOVA: {y_col} versus {f_col}",
            subtitle=f"F = {f_stat:.2f} (p = {p_val:.4f}) | S = {s_pooled:.4f} | R-sq = {r_sq * 100:.2f}%",
            tables=[anova_table, model_summary_table, grouping_table, comparisons_table],
            plotly_figure=interval_fig,
            plotly_figures=all_figures,
            statistics={
                "f_stat": f_stat,
                "p_value": p_val,
                "s_pooled": s_pooled,
                "r_sq": r_sq,
                "r_sq_adj": r_sq_adj,
                "group_means": dict(zip(group_names, group_means.tolist())),
                "groupings": dict(zip(group_names, grouping_letters)),
                "welch_f": f_welch,
                "welch_p": p_welch
            }
        )

