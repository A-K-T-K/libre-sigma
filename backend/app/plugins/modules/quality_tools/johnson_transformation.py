"""
Johnson Transformation Plugin for OpenMinitab Quality Tools.
Transforms non-normal data into standard normal Z-scale using SB, SU, and SL Johnson distribution families.
"""

from typing import Any, Dict, List, Optional, Tuple
import math
import numpy as np
import pandas as pd
from scipy import stats, optimize
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult
from .distribution_id import calculate_anderson_darling


class JohnsonTransformationParams(BaseModel):
    data_column: str = Field(
        ...,
        description="Measurement Variable",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    p_value_to_select: float = Field(
        0.10,
        ge=0.001,
        le=0.50,
        description="P-Value to select best fit (Default: 0.10)"
    )


class JohnsonTransformationPlugin(AnalysisPlugin):
    id = "johnson_transformation"
    name = "Johnson Transformation"
    menu_path = ["Stat", "Quality Tools", "Johnson Transformation"]
    description = "Transforms non-normal continuous data to standard normal distribution using Johnson curves (SB, SU, SL)."
    param_schema = JohnsonTransformationParams

    def execute(self, df: pd.DataFrame, params: JohnsonTransformationParams) -> AnalysisResult:
        data_col = params.data_column
        if data_col not in df.columns:
            raise ValueError(f"Column '{data_col}' not found in active worksheet.")

        raw_series = pd.to_numeric(df[data_col], errors="coerce").dropna()
        if len(raw_series) < 6:
            raise ValueError("Johnson Transformation requires at least 6 observations.")

        x = raw_series.to_numpy(dtype=float)
        n = len(x)
        min_x, max_x = float(np.min(x)), float(np.max(x))
        range_x = max_x - min_x
        if range_x < 1e-9:
            raise ValueError("Data has zero variance; cannot fit Johnson transformation.")

        # Evaluate Original Data Normality
        x_sorted = np.sort(x)
        mu_orig, s_orig = float(np.mean(x_sorted)), float(np.std(x_sorted, ddof=1))
        z_orig = stats.norm.cdf((x_sorted - mu_orig) / s_orig)
        ad_orig = calculate_anderson_darling(z_orig)
        p_orig = float(np.clip(math.exp(1.2937 - 5.709 * ad_orig), 0.0, 1.0)) if ad_orig > 0.6 else 0.5

        # Fit Candidates: SB, SU, SL
        candidates = []

        # 1. Unbounded (SU): Z = gamma + eta * asinh((X - epsilon) / lambda)
        try:
            def su_obj(params_su):
                gamma, eta, eps, lam = params_su
                if eta <= 0 or lam <= 0:
                    return 1e6
                z = gamma + eta * np.arcsinh((x - eps) / lam)
                z_sort = np.sort(z)
                z_cdf = stats.norm.cdf((z_sort - np.mean(z_sort)) / max(1e-6, np.std(z_sort, ddof=1)))
                return calculate_anderson_darling(z_cdf)

            init_su = [0.0, 1.0, float(np.median(x)), float(np.std(x))]
            res_su = optimize.minimize(su_obj, init_su, method="Nelder-Mead", options={"maxiter": 600})
            gamma_su, eta_su, eps_su, lam_su = res_su.x
            z_su = gamma_su + eta_su * np.arcsinh((x_sorted - eps_su) / lam_su)
            ad_su = calculate_anderson_darling(stats.norm.cdf((z_su - np.mean(z_su)) / np.std(z_su, ddof=1)))
            p_su = float(np.clip(math.exp(1.2937 - 5.709 * ad_su), 0.0, 1.0)) if ad_su > 0.6 else 0.6
            formula_su = f"Z = {gamma_su:.4f} + {eta_su:.4f} * asinh((X - {eps_su:.4f}) / {lam_su:.4f})"
            candidates.append({
                "type": "SU (Unbounded)",
                "gamma": gamma_su,
                "eta": eta_su,
                "epsilon": eps_su,
                "lambda": lam_su,
                "ad": ad_su,
                "p_val": p_su,
                "formula": formula_su,
                "z_data": z_su
            })
        except Exception:
            pass

        # 2. Bounded (SB): Z = gamma + eta * ln((X - epsilon) / (lambda + epsilon - X))
        try:
            eps_sb_init = min_x - 0.05 * range_x
            lam_sb_init = 1.1 * range_x

            def sb_obj(params_sb):
                gamma, eta, eps, lam = params_sb
                if eta <= 0 or lam <= 0:
                    return 1e6
                if eps >= min_x or (eps + lam) <= max_x:
                    return 1e6
                ratio = (x - eps) / (lam + eps - x)
                if np.any(ratio <= 0):
                    return 1e6
                z = gamma + eta * np.log(ratio)
                z_sort = np.sort(z)
                z_cdf = stats.norm.cdf((z_sort - np.mean(z_sort)) / max(1e-6, np.std(z_sort, ddof=1)))
                return calculate_anderson_darling(z_cdf)

            init_sb = [0.0, 1.0, eps_sb_init, lam_sb_init]
            res_sb = optimize.minimize(sb_obj, init_sb, method="Nelder-Mead", options={"maxiter": 600})
            gamma_sb, eta_sb, eps_sb, lam_sb = res_sb.x
            ratio_sorted = (x_sorted - eps_sb) / (lam_sb + eps_sb - x_sorted)
            if np.all(ratio_sorted > 0):
                z_sb = gamma_sb + eta_sb * np.log(ratio_sorted)
                ad_sb = calculate_anderson_darling(stats.norm.cdf((z_sb - np.mean(z_sb)) / np.std(z_sb, ddof=1)))
                p_sb = float(np.clip(math.exp(1.2937 - 5.709 * ad_sb), 0.0, 1.0)) if ad_sb > 0.6 else 0.6
                formula_sb = f"Z = {gamma_sb:.4f} + {eta_sb:.4f} * ln((X - {eps_sb:.4f}) / ({lam_sb:.4f} + {eps_sb:.4f} - X))"
                candidates.append({
                    "type": "SB (Bounded)",
                    "gamma": gamma_sb,
                    "eta": eta_sb,
                    "epsilon": eps_sb,
                    "lambda": lam_sb,
                    "ad": ad_sb,
                    "p_val": p_sb,
                    "formula": formula_sb,
                    "z_data": z_sb
                })
        except Exception:
            pass

        # 3. Lognormal (SL): Z = gamma + eta * ln(X - epsilon)
        try:
            eps_sl_init = min_x - 0.05 * range_x

            def sl_obj(params_sl):
                gamma, eta, eps = params_sl
                if eta <= 0 or eps >= min_x:
                    return 1e6
                z = gamma + eta * np.log(x - eps)
                z_sort = np.sort(z)
                z_cdf = stats.norm.cdf((z_sort - np.mean(z_sort)) / max(1e-6, np.std(z_sort, ddof=1)))
                return calculate_anderson_darling(z_cdf)

            init_sl = [0.0, 1.0, eps_sl_init]
            res_sl = optimize.minimize(sl_obj, init_sl, method="Nelder-Mead", options={"maxiter": 600})
            gamma_sl, eta_sl, eps_sl = res_sl.x
            z_sl = gamma_sl + eta_sl * np.log(x_sorted - eps_sl)
            ad_sl = calculate_anderson_darling(stats.norm.cdf((z_sl - np.mean(z_sl)) / np.std(z_sl, ddof=1)))
            p_sl = float(np.clip(math.exp(1.2937 - 5.709 * ad_sl), 0.0, 1.0)) if ad_sl > 0.6 else 0.6
            formula_sl = f"Z = {gamma_sl:.4f} + {eta_sl:.4f} * ln(X - {eps_sl:.4f})"
            candidates.append({
                "type": "SL (Lognormal)",
                "gamma": gamma_sl,
                "eta": eta_sl,
                "epsilon": eps_sl,
                "lambda": 1.0,
                "ad": ad_sl,
                "p_val": p_sl,
                "formula": formula_sl,
                "z_data": z_sl
            })
        except Exception:
            pass

        if not candidates:
            raise ValueError("Could not fit any Johnson distribution family to this data.")

        # Pick best family with lowest AD and p-value >= p_value_to_select
        best = min(candidates, key=lambda c: c["ad"])

        # Construct Tables
        param_table = TableResult(
            title="Johnson Transformation Model Parameters",
            headers=["Parameter", "Optimal Estimate"],
            rows=[
                ["Selected Family", best["type"]],
                ["Shape (Gamma)", f"{best['gamma']:.4f}"],
                ["Shape (Eta)", f"{best['eta']:.4f}"],
                ["Location (Epsilon)", f"{best['epsilon']:.4f}"],
                ["Scale (Lambda)", f"{best['lambda']:.4f}"],
                ["Transformation Function", best["formula"]]
            ]
        )

        comparison_table = TableResult(
            title="Goodness-of-Fit Comparison: Before vs. After Transformation",
            headers=["Data State", "Anderson-Darling (AD)", "p-Value", "Normality Met?"],
            rows=[
                ["Before Transformation", f"{ad_orig:.3f}", f"{p_orig:.4f}" if p_orig >= 0.005 else "< 0.005", "No" if p_orig < 0.05 else "Yes"],
                ["After Transformation (" + best["type"] + ")", f"{best['ad']:.3f}", f"{best['p_val']:.4f}" if best['p_val'] >= 0.005 else "< 0.005", "Yes" if best['p_val'] >= params.p_value_to_select else "No"]
            ]
        )

        # Plotly Dual Probability Plot
        p_emp = (np.arange(1, n + 1) - 0.375) / (n + 0.25)
        y_scores = stats.norm.ppf(p_emp)

        plotly_fig = {
            "data": [
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": x_sorted.tolist(),
                    "y": y_scores.tolist(),
                    "name": f"Original Data (AD = {ad_orig:.3f})",
                    "marker": {"color": "#d13438", "size": 6}
                },
                {
                    "type": "scatter",
                    "mode": "markers",
                    "x": best["z_data"].tolist(),
                    "y": y_scores.tolist(),
                    "name": f"Transformed Z (AD = {best['ad']:.3f})",
                    "marker": {"color": "#008450", "size": 6, "symbol": "diamond"}
                },
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": [-3.0, 3.0],
                    "y": [-3.0, 3.0],
                    "name": "Standard Normal Target (y = x)",
                    "line": {"color": "#004d2c", "width": 1.5, "dash": "dash"}
                }
            ],
            "layout": {
                "title": f"Johnson Transformation Probability Plot: {data_col} -> {best['type']}",
                "xaxis": {"title": "Value (Original & Z-Scale)", "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {
                    "title": "Normal Probability Score",
                    "tickvals": [-2.326, -1.645, 0.0, 1.645, 2.326],
                    "ticktext": ["1%", "5%", "50%", "95%", "99%"],
                    "showgrid": True,
                    "gridcolor": "#ececec"
                },
                "legend": {"orientation": "h", "y": -0.2}
            }
        }

        return AnalysisResult(
            title=f"Johnson Transformation for {data_col}",
            subtitle=f"Optimal Family: {best['type']} (AD = {best['ad']:.3f}, p = {best['p_val']:.3f})",
            tables=[param_table, comparison_table],
            plotly_figure=plotly_fig,
            statistics={
                "selected_family": best["type"],
                "gamma": best["gamma"],
                "eta": best["eta"],
                "epsilon": best["epsilon"],
                "lambda": best["lambda"],
                "ad_before": ad_orig,
                "ad_after": best["ad"],
                "formula": best["formula"]
            }
        )
