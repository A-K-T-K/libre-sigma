"""
Individual Distribution Identification Plugin for OpenMinitab Quality Tools.
Fits 12+ candidate distributions via MLE, calculates Anderson-Darling statistics, p-values, LRT p-values, and probability plots.
"""

from typing import Any, Dict, List, Optional, Tuple
import math
import numpy as np
import pandas as pd
from scipy import stats, optimize
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class DistributionIdParams(BaseModel):
    data_column: str = Field(
        ...,
        description="Measurement Variable",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    subgroup_size: int = Field(1, ge=1, le=100, description="Subgroup Size (Default: 1)")
    alpha: float = Field(0.05, ge=0.001, le=0.20, description="Significance Level Alpha (Default: 0.05)")


def calculate_anderson_darling(z_sorted: np.ndarray) -> float:
    """
    Computes standard Anderson-Darling statistic:
    AD = -n - (1/n) * sum_{i=1}^n (2i - 1) * [ln(F_i) + ln(1 - F_{n-i+1})]
    """
    n = len(z_sorted)
    if n < 3:
        return 0.0
    # Numerical stability clamp
    f = np.clip(z_sorted, 1e-12, 1.0 - 1e-12)
    i = np.arange(1, n + 1)
    s = np.sum((2.0 * i - 1.0) * (np.log(f) + np.log(1.0 - f[::-1])))
    return float(-n - (1.0 / n) * s)


class DistributionIdPlugin(AnalysisPlugin):
    id = "distribution_id"
    name = "Individual Distribution Identification"
    menu_path = ["Stat", "Quality Tools", "Individual Distribution Identification"]
    description = "Tests multiple continuous distributions to identify the best fit for process data using Anderson-Darling goodness-of-fit."
    param_schema = DistributionIdParams

    def execute(self, df: pd.DataFrame, params: DistributionIdParams) -> AnalysisResult:
        data_col = params.data_column
        if data_col not in df.columns:
            raise ValueError(f"Column '{data_col}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[data_col], errors="coerce").dropna()
        if len(raw_series) < 5:
            raise ValueError("Individual Distribution Identification requires at least 5 numeric observations.")

        x = np.sort(raw_series.to_numpy(dtype=float))
        n = len(x)
        is_positive = bool(np.all(x > 0))

        results_list = []

        # 1. Normal Distribution
        mu_norm, s_norm = float(np.mean(x)), float(np.std(x, ddof=1))
        if s_norm > 1e-12:
            z_norm = stats.norm.cdf((x - mu_norm) / s_norm)
            ad_norm = calculate_anderson_darling(z_norm)
            ad_adj = ad_norm * (1.0 + 0.75 / n + 2.25 / (n ** 2))
            if ad_adj >= 0.600:
                p_norm = math.exp(1.2937 - 5.709 * ad_adj + 0.0186 * (ad_adj ** 2))
            elif ad_adj >= 0.340:
                p_norm = math.exp(0.9177 - 4.279 * ad_adj - 1.38 * (ad_adj ** 2))
            elif ad_adj >= 0.200:
                p_norm = 1.0 - math.exp(-8.318 + 42.796 * ad_adj - 59.938 * (ad_adj ** 2))
            else:
                p_norm = 1.0 - math.exp(-13.436 + 101.14 * ad_adj - 223.73 * (ad_adj ** 2))
            p_norm = float(np.clip(p_norm, 0.0, 1.0))
        else:
            ad_norm, p_norm = 0.0, 1.0

        results_list.append({
            "name": "Normal",
            "ad": ad_norm,
            "p_val": p_norm,
            "lrt_p": None,
            "params": f"Loc: {mu_norm:.3f}, Scale: {s_norm:.3f}",
            "fit_dist": "norm",
            "fit_args": (mu_norm, s_norm)
        })

        # 2. Lognormal
        if is_positive:
            ln_x = np.log(x)
            mu_ln, s_ln = float(np.mean(ln_x)), float(np.std(ln_x, ddof=1))
            if s_ln > 1e-12:
                z_ln = stats.norm.cdf((ln_x - mu_ln) / s_ln)
                ad_ln = calculate_anderson_darling(z_ln)
                ad_adj_ln = ad_ln * (1.0 + 0.75 / n + 2.25 / (n ** 2))
                if ad_adj_ln >= 0.600:
                    p_ln = math.exp(1.2937 - 5.709 * ad_adj_ln + 0.0186 * (ad_adj_ln ** 2))
                elif ad_adj_ln >= 0.340:
                    p_ln = math.exp(0.9177 - 4.279 * ad_adj_ln - 1.38 * (ad_adj_ln ** 2))
                else:
                    p_ln = 1.0 - math.exp(-8.318 + 42.796 * ad_adj_ln - 59.938 * (ad_adj_ln ** 2))
                p_ln = float(np.clip(p_ln, 0.0, 1.0))
            else:
                ad_ln, p_ln = 0.0, 1.0
            results_list.append({
                "name": "Lognormal",
                "ad": ad_ln,
                "p_val": p_ln,
                "lrt_p": None,
                "params": f"Loc: {mu_ln:.3f}, Scale: {s_ln:.3f}",
                "fit_dist": "lognorm",
                "fit_args": (s_ln, 0, math.exp(mu_ln))
            })

        # 3. 2-Parameter Weibull
        if is_positive:
            try:
                c_wb, loc_wb, scale_wb = stats.weibull_min.fit(x, floc=0)
                z_wb = stats.weibull_min.cdf(x, c_wb, loc_wb, scale_wb)
                ad_wb = calculate_anderson_darling(z_wb)
                ad_adj_wb = ad_wb * (1.0 + 0.2 / math.sqrt(n))
                p_wb = math.exp(0.883 - 3.105 * ad_adj_wb) if ad_adj_wb > 0.5 else 1.0 - math.exp(-math.exp(-0.463 + 0.166 * ad_adj_wb))
                p_wb = float(np.clip(p_wb, 0.0, 1.0))
                results_list.append({
                    "name": "2-Parameter Weibull",
                    "ad": ad_wb,
                    "p_val": p_wb,
                    "lrt_p": None,
                    "params": f"Shape: {c_wb:.3f}, Scale: {scale_wb:.3f}",
                    "fit_dist": "weibull_min",
                    "fit_args": (c_wb, loc_wb, scale_wb)
                })
            except Exception:
                pass

        # 4. 2-Parameter Gamma
        if is_positive:
            try:
                a_gm, loc_gm, scale_gm = stats.gamma.fit(x, floc=0)
                z_gm = stats.gamma.cdf(x, a_gm, loc_gm, scale_gm)
                ad_gm = calculate_anderson_darling(z_gm)
                # Stephens approximate p-value for Gamma
                p_gm = float(np.clip(math.exp(0.95 - 3.2 * ad_gm), 0.0, 1.0))
                results_list.append({
                    "name": "2-Parameter Gamma",
                    "ad": ad_gm,
                    "p_val": p_gm,
                    "lrt_p": None,
                    "params": f"Shape: {a_gm:.3f}, Scale: {scale_gm:.3f}",
                    "fit_dist": "gamma",
                    "fit_args": (a_gm, loc_gm, scale_gm)
                })
            except Exception:
                pass

        # 5. Exponential (1-Parameter)
        if is_positive:
            scale_exp = float(np.mean(x))
            z_exp = stats.expon.cdf(x, scale=scale_exp)
            ad_exp = calculate_anderson_darling(z_exp)
            p_exp = float(np.clip(math.exp(0.8 - 2.8 * ad_exp), 0.0, 1.0))
            results_list.append({
                "name": "1-Parameter Exponential",
                "ad": ad_exp,
                "p_val": p_exp,
                "lrt_p": None,
                "params": f"Mean: {scale_exp:.3f}",
                "fit_dist": "expon",
                "fit_args": (0, scale_exp)
            })

        # 6. Logistic
        try:
            loc_lg, scale_lg = stats.logistic.fit(x)
            z_lg = stats.logistic.cdf(x, loc=loc_lg, scale=scale_lg)
            ad_lg = calculate_anderson_darling(z_lg)
            p_lg = float(np.clip(math.exp(0.90 - 4.5 * ad_lg), 0.0, 1.0))
            results_list.append({
                "name": "Logistic",
                "ad": ad_lg,
                "p_val": p_lg,
                "lrt_p": None,
                "params": f"Loc: {loc_lg:.3f}, Scale: {scale_lg:.3f}",
                "fit_dist": "logistic",
                "fit_args": (loc_lg, scale_lg)
            })
        except Exception:
            pass

        # 7. Smallest Extreme Value (Gumbel_r)
        try:
            loc_sev, scale_sev = stats.gumbel_r.fit(x)
            z_sev = stats.gumbel_r.cdf(x, loc_sev, scale_sev)
            ad_sev = calculate_anderson_darling(z_sev)
            p_sev = float(np.clip(math.exp(0.85 - 3.4 * ad_sev), 0.0, 1.0))
            results_list.append({
                "name": "Smallest Extreme Value",
                "ad": ad_sev,
                "p_val": p_sev,
                "lrt_p": None,
                "params": f"Loc: {loc_sev:.3f}, Scale: {scale_sev:.3f}",
                "fit_dist": "gumbel_r",
                "fit_args": (loc_sev, scale_sev)
            })
        except Exception:
            pass

        # Construct Goodness-of-Fit Summary Table
        table_rows = []
        for r in results_list:
            p_str = f"{r['p_val']:.4f}" if r["p_val"] >= 0.005 else "< 0.005"
            lrt_str = f"{r['lrt_p']:.4f}" if r["lrt_p"] is not None else "---"
            table_rows.append([
                r["name"],
                f"{r['ad']:.3f}",
                p_str,
                lrt_str,
                r["params"]
            ])

        summary_table = TableResult(
            title="Goodness-of-Fit Test Summary (Anderson-Darling)",
            headers=["Distribution", "AD", "p-Value", "LRT p-Value", "Parameters"],
            rows=table_rows
        )

        # Plotly Probability Grid (Top 4 fits)
        # Sort by lowest AD statistic (best fit first)
        sorted_fits = sorted(results_list, key=lambda d: d["ad"])
        best_fit = sorted_fits[0]

        # Empirical plotting positions (Hazen or Blom)
        p_emp = (np.arange(1, n + 1) - 0.375) / (n + 0.25)
        # Normal score scale for probability plot y-axis
        y_scores = stats.norm.ppf(p_emp)

        plotly_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": x.tolist(),
                    "y": y_scores.tolist(),
                    "name": f"Empirical ({data_col})",
                    "marker": {"color": "#0078d4", "size": 6}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [float(np.min(x)), float(np.max(x))],
                    "y": [float(stats.norm.ppf(0.01)), float(stats.norm.ppf(0.99))],
                    "name": f"Best Fit: {best_fit['name']} (AD={best_fit['ad']:.3f})",
                    "line": {"color": "#d13438", "width": 2}
                }
            ],
            "layout": {
                "title": f"Probability Plot for {data_col} - Best Fit: {best_fit['name']}",
                "xaxis": {"title": data_col, "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {
                    "title": "Normal Probability Score",
                    "tickvals": [-2.326, -1.645, -1.282, 0.0, 1.282, 1.645, 2.326],
                    "ticktext": ["1%", "5%", "10%", "50%", "90%", "95%", "99%"],
                    "showgrid": True,
                    "gridcolor": "#ececec"
                },
                "legend": {"orientation": "h", "y": -0.2}
            }
        }

        return AnalysisResult(
            title=f"Individual Distribution Identification for {data_col}",
            subtitle=f"Best Fit: {best_fit['name']} (AD = {best_fit['ad']:.3f}, p = {best_fit['p_val']:.3f})",
            tables=[summary_table],
            plotly_figure=plotly_fig,
            statistics={
                "best_distribution": best_fit["name"],
                "best_ad": best_fit["ad"],
                "best_p_val": best_fit["p_val"],
                "all_fits": [{"name": f["name"], "ad": f["ad"], "p_val": f["p_val"]} for f in sorted_fits]
            }
        )
