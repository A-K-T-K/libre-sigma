import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class TwoSamplePoissonRateParams(BaseModel):
    data_mode: str = Field(
        "raw",
        description="Data Format",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Both samples are in separate columns", "value": "raw"},
                {"label": "Summarized data (Occurrences & Total size for each sample)", "value": "summarized"},
            ]
        }
    )
    sample1_col: Optional[str] = Field(None, description="Sample 1 Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    sample2_col: Optional[str] = Field(None, description="Sample 2 Column", json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"})
    sample1_occurrences: Optional[int] = Field(None, description="Sample 1 Occurrences (X1)", json_schema_extra={"ui_type": "number"})
    sample1_size: Optional[float] = Field(1.0, description="Sample 1 Total Size (T1)", json_schema_extra={"ui_type": "number"})
    sample2_occurrences: Optional[int] = Field(None, description="Sample 2 Occurrences (X2)", json_schema_extra={"ui_type": "number"})
    sample2_size: Optional[float] = Field(1.0, description="Sample 2 Total Size (T2)", json_schema_extra={"ui_type": "number"})
    hypothesized_ratio: float = Field(1.0, description="Hypothesized rate ratio (lambda1 / lambda2)", json_schema_extra={"ui_type": "number"})
    alternative: str = Field(
        "two_sided",
        description="Alternative Hypothesis",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "ratio != hypothesized ratio (two-sided)", "value": "two_sided"},
                {"label": "ratio < hypothesized ratio (less than)", "value": "less"},
                {"label": "ratio > hypothesized ratio (greater than)", "value": "greater"},
            ]
        }
    )
    confidence_level: float = Field(95.0, description="Confidence level (%)", json_schema_extra={"ui_type": "number"})


class TwoSamplePoissonRatePlugin(AnalysisPlugin):
    id = "two_sample_poisson_rate"
    name = "2-Sample Poisson Rate"
    menu_path = ["Stat", "Basic Statistics", "2-Sample Poisson Rate"]
    description = "Compares two Poisson rates using exact conditional binomial test and normal approximation test for rate ratios."
    param_schema = TwoSamplePoissonRateParams

    def execute(self, df: pd.DataFrame, params: TwoSamplePoissonRateParams) -> AnalysisResult:
        if params.data_mode == "raw":
            if not params.sample1_col or not params.sample2_col:
                raise ValueError("Select both Sample 1 and Sample 2 count columns.")
            c1 = pd.to_numeric(df[params.sample1_col], errors="coerce").dropna().to_numpy(dtype=float)
            c2 = pd.to_numeric(df[params.sample2_col], errors="coerce").dropna().to_numpy(dtype=float)
            x1, t1 = int(np.sum(c1)), float(len(c1))
            x2, t2 = int(np.sum(c2)), float(len(c2))
        else:
            if None in (params.sample1_occurrences, params.sample1_size, params.sample2_occurrences, params.sample2_size):
                raise ValueError("Please provide Occurrences and Size for both samples.")
            x1, t1 = int(params.sample1_occurrences), float(params.sample1_size)
            x2, t2 = int(params.sample2_occurrences), float(params.sample2_size)

        if x1 < 0 or t1 <= 0 or x2 < 0 or t2 <= 0:
            raise ValueError("Occurrences must be >= 0 and Sizes must be > 0.")

        r1 = float(x1 / t1)
        r2 = float(x2 / t2)
        rate_ratio = (r1 / r2) if r2 > 0 else np.nan
        rate_diff = r1 - r2

        rho0 = float(params.hypothesized_ratio)
        if rho0 <= 0:
            raise ValueError("Hypothesized ratio must be strictly greater than 0.")

        conf = params.confidence_level / 100.0
        alpha = 1.0 - conf

        # Exact Test using conditional Binomial: X1 | (X1 + X2) ~ Binomial(n = X1 + X2, pi = (T1*rho0)/(T1*rho0 + T2))
        n_tot = x1 + x2
        pi_0 = (t1 * rho0) / (t1 * rho0 + t2)
        alt_map = {"two_sided": "two-sided", "less": "less", "greater": "greater"}
        if n_tot > 0:
            binom_res = stats.binomtest(x1, n_tot, p=pi_0, alternative=alt_map.get(params.alternative, "two-sided"))
            p_val_exact = float(binom_res.pvalue)
            ci_pi = binom_res.proportion_ci(confidence_level=conf)
            # Convert pi CI to rate ratio CI: rho = (pi * T2) / ((1 - pi) * T1)
            ci_low = float((ci_pi.low * t2) / ((1.0 - ci_pi.low) * t1)) if ci_pi.low < 1.0 else np.inf
            ci_high = float((ci_pi.high * t2) / ((1.0 - ci_pi.high) * t1)) if ci_pi.high < 1.0 else np.inf
        else:
            p_val_exact = 1.0
            ci_low, ci_high = 0.0, np.inf

        # Normal approximation test
        if x1 > 0 and x2 > 0:
            se_log_ratio = np.sqrt(1.0 / x1 + 1.0 / x2)
            z_stat = (np.log(rate_ratio) - np.log(rho0)) / se_log_ratio
            if params.alternative == "two_sided":
                p_val_norm = 2.0 * (1.0 - stats.norm.cdf(abs(z_stat)))
                alt_sym = "≠"
            elif params.alternative == "less":
                p_val_norm = stats.norm.cdf(z_stat)
                alt_sym = "<"
            else:
                p_val_norm = 1.0 - stats.norm.cdf(z_stat)
                alt_sym = ">"
        else:
            z_stat = 0.0
            p_val_norm = p_val_exact
            alt_sym = "≠"

        ci_str = f"({ci_low:.4f}, {ci_high:.4f})"

        # Tables
        desc_headers = ["Sample", "Total Occurrences (X)", "Total Sample Size (T)", "Rate per Unit"]
        desc_rows = [
            ["Sample 1", x1, f"{t1:.1f}", f"{r1:.4f}"],
            ["Sample 2", x2, f"{t2:.1f}", f"{r2:.4f}"],
        ]

        est_headers = ["Rate Ratio (Rate1 / Rate2)", f"{params.confidence_level}% Exact CI for Ratio", "Rate Difference (Rate1 - Rate2)"]
        est_rows = [[f"{rate_ratio:.4f}" if not np.isnan(rate_ratio) else "—", ci_str, f"{rate_diff:.4f}"]]

        test_headers = ["Method", "Null hypothesis", "Alternative hypothesis", "Z-Value", "P-Value"]
        test_rows = [
            ["Exact (Conditional Binomial)", f"H₀: Rate1 / Rate2 = {rho0}", f"H₁: Rate1 / Rate2 {alt_sym} {rho0}", "—", f"{p_val_exact:.4f}"],
            ["Normal approximation", f"H₀: Rate1 / Rate2 = {rho0}", f"H₁: Rate1 / Rate2 {alt_sym} {rho0}", f"{z_stat:.2f}", f"{p_val_norm:.4f}"],
        ]

        text_lines = [
            "Test and CI for Two-Sample Poisson Rates",
            "",
            "Descriptive Statistics",
            f"  {'Sample':<12} {'X':>6} {'T':>8} {'Rate':>10}",
            f"  {'-'*12} {'-'*6} {'-'*8} {'-'*10}",
            f"  {'Sample 1':<12} {x1:>6} {t1:>8.1f} {r1:>10.4f}",
            f"  {'Sample 2':<12} {x2:>6} {t2:>8.1f} {r2:>10.4f}",
            "",
            f"Estimation for Rate Ratio: {rate_ratio:.4f}" if not np.isnan(rate_ratio) else "Estimation for Rate Ratio: —",
            f"{params.confidence_level}% Exact CI for Ratio: {ci_str}",
            f"Rate Difference (Rate1 - Rate2): {rate_diff:.4f}",
            "",
            "Test",
            f"  Null hypothesis:         H₀: Rate1 / Rate2 = {rho0}",
            f"  Alternative hypothesis:  H₁: Rate1 / Rate2 {alt_sym} {rho0}",
            f"  Method                 Z-Value  P-Value",
            f"  Exact (Conditional)       —     {p_val_exact:.4f}",
            f"  Normal approximation   {z_stat:>7.2f}  {p_val_norm:.4f}",
        ]

        # Plot: Comparative Rates
        plot_data = [
            {
                "type": "bar",
                "x": ["Sample 1", "Sample 2"],
                "y": [r1, r2],
                "marker": {"color": ["#6366f1", "#14b8a6"]},
            }
        ]

        layout = {
            "title": {"text": "<b>Comparison of Poisson Rates</b>", "x": 0.5},
            "showlegend": False,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 400,
            "yaxis": {"title": {"text": "Rate per Unit"}, "showgrid": True, "gridcolor": "#ececec"},
        }

        return AnalysisResult(
            title="2-Sample Poisson Rate",
            subtitle=f"Sample 1 ({r1:.3f}) vs Sample 2 ({r2:.3f})",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title="Descriptive Statistics", headers=desc_headers, rows=desc_rows),
                TableResult(title="Estimation for Rate Ratio", headers=est_headers, rows=est_rows),
                TableResult(title="Hypothesis Test Results", headers=test_headers, rows=test_rows)
            ],
            statistics={"rate_ratio": rate_ratio, "rate_diff": rate_diff, "p_val_exact": p_val_exact, "p_val_norm": p_val_norm, "ci": [ci_low, ci_high]},
            plotly_figure={"data": plot_data, "layout": layout}
        )
