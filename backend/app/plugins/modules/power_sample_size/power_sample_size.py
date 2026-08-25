"""
Power and Sample Size for Hypothesis Tests Plugin for OpenMinitab.
Calculates required sample sizes or statistical power for 1-Sample t, 2-Sample t, Paired t, 1-Proportion, 2-Proportions, and 1-Way ANOVA.
Generates Power vs Sample Size curves across difference effect sizes.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from statsmodels.stats.power import (
    TTestPower,
    TTestIndPower,
    FTestAnovaPower,
    GofChisquarePower
)
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class PowerSampleSizeParams(BaseModel):
    test_type: str = Field(
        "2_sample_t",
        description="Test Type",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "2-Sample t (Independent Means)", "value": "2_sample_t"},
                {"label": "1-Sample t (Mean vs Target)", "value": "1_sample_t"},
                {"label": "Paired t (Mean Difference)", "value": "paired_t"},
                {"label": "1 Proportion (Binomial)", "value": "1_proportion"},
                {"label": "2 Proportions (Independent)", "value": "2_proportions"},
                {"label": "One-Way ANOVA (k Groups)", "value": "anova_1way"}
            ]
        }
    )
    solve_for: str = Field(
        "sample_size",
        description="Solve For",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Sample Size (N) given Target Power", "value": "sample_size"},
                {"label": "Power (1 - β) given Sample Size", "value": "power"}
            ]
        }
    )
    difference_effect: float = Field(
        1.0,
        description="Difference / Effect Size (δ)"
    )
    standard_deviation: float = Field(
        1.0,
        gt=0.0001,
        description="Planned Standard Deviation (σ)"
    )
    target_power: float = Field(
        0.80,
        ge=0.10,
        le=0.9999,
        description="Target Power (1 - β, e.g. 0.80, 0.90)"
    )
    sample_size_input: int = Field(
        30,
        ge=2,
        le=100000,
        description="Sample Size per group (if solving for Power)",
        json_schema_extra={"sub_modal": "Options..."}
    )
    alpha: float = Field(
        0.05,
        ge=0.0001,
        le=0.20,
        description="Significance Level (α, Default: 0.05)"
    )
    alternative: str = Field(
        "two-sided",
        description="Alternative Hypothesis Direction",
        json_schema_extra={
            "ui_type": "select",
            "sub_modal": "Options...",
            "options": [
                {"label": "Two-Sided (≠)", "value": "two-sided"},
                {"label": "One-Sided (> or <)", "value": "larger"}
            ]
        }
    )
    num_groups: int = Field(
        3,
        ge=2,
        le=50,
        description="Number of Groups (for One-Way ANOVA)",
        json_schema_extra={"sub_modal": "Options..."}
    )


class PowerSampleSizePlugin(AnalysisPlugin):
    id = "power_and_sample_size"
    name = "Power and Sample Size"
    menu_path = ["Stat", "Power and Sample Size", "Hypothesis Tests"]
    description = "Calculates required sample size or achieved statistical power across effect sizes with interactive power curve plots."
    param_schema = PowerSampleSizeParams

    def execute(self, df: pd.DataFrame, params: PowerSampleSizeParams) -> AnalysisResult:
        test = params.test_type
        delta = params.difference_effect
        sigma = max(1e-5, params.standard_deviation)
        alpha = params.alpha
        target_p = params.target_power
        solve = params.solve_for
        alt = params.alternative

        # Standardized effect size (Cohen's d)
        d_effect = abs(delta) / sigma if sigma > 0 else 1.0

        sample_size_per_group = 0
        actual_power = 0.0

        if test == "1_sample_t" or test == "paired_t":
            tt = TTestPower()
            if solve == "sample_size":
                sample_size_per_group = int(np.ceil(tt.solve_power(effect_size=d_effect, power=target_p, alpha=alpha, alternative=alt)))
                actual_power = float(tt.solve_power(effect_size=d_effect, nobs=sample_size_per_group, alpha=alpha, alternative=alt))
            else:
                sample_size_per_group = params.sample_size_input
                actual_power = float(tt.solve_power(effect_size=d_effect, nobs=sample_size_per_group, alpha=alpha, alternative=alt))

            power_fn = lambda n_val, eff: float(tt.solve_power(effect_size=eff, nobs=n_val, alpha=alpha, alternative=alt))

        elif test == "2_sample_t":
            tt_ind = TTestIndPower()
            if solve == "sample_size":
                sample_size_per_group = int(np.ceil(tt_ind.solve_power(effect_size=d_effect, power=target_p, alpha=alpha, alternative=alt)))
                actual_power = float(tt_ind.solve_power(effect_size=d_effect, nobs1=sample_size_per_group, alpha=alpha, alternative=alt))
            else:
                sample_size_per_group = params.sample_size_input
                actual_power = float(tt_ind.solve_power(effect_size=d_effect, nobs1=sample_size_per_group, alpha=alpha, alternative=alt))

            power_fn = lambda n_val, eff: float(tt_ind.solve_power(effect_size=eff, nobs1=n_val, alpha=alpha, alternative=alt))

        elif test == "anova_1way":
            k_grp = params.num_groups
            # Effect size f = sqrt(d^2 / (2*k))
            f_effect = d_effect / np.sqrt(2 * k_grp)
            f_pwr = FTestAnovaPower()
            if solve == "sample_size":
                sample_size_per_group = int(np.ceil(f_pwr.solve_power(effect_size=f_effect, power=target_p, alpha=alpha, k_groups=k_grp)))
                actual_power = float(f_pwr.solve_power(effect_size=f_effect, nobs=sample_size_per_group * k_grp, alpha=alpha, k_groups=k_grp))
            else:
                sample_size_per_group = params.sample_size_input
                actual_power = float(f_pwr.solve_power(effect_size=f_effect, nobs=sample_size_per_group * k_grp, alpha=alpha, k_groups=k_grp))

            power_fn = lambda n_val, eff: float(f_pwr.solve_power(effect_size=eff / np.sqrt(2 * k_grp), nobs=n_val * k_grp, alpha=alpha, k_groups=k_grp))

        else:
            # Proportion approximation
            p1 = 0.5
            p2 = min(0.99, max(0.01, p1 + delta))
            h_eff = 2 * (np.arcsin(np.sqrt(p2)) - np.arcsin(np.sqrt(p1)))
            tt_ind = TTestIndPower()
            if solve == "sample_size":
                sample_size_per_group = int(np.ceil(tt_ind.solve_power(effect_size=abs(h_eff), power=target_p, alpha=alpha, alternative=alt)))
                actual_power = float(tt_ind.solve_power(effect_size=abs(h_eff), nobs1=sample_size_per_group, alpha=alpha, alternative=alt))
            else:
                sample_size_per_group = params.sample_size_input
                actual_power = float(tt_ind.solve_power(effect_size=abs(h_eff), nobs1=sample_size_per_group, alpha=alpha, alternative=alt))

            power_fn = lambda n_val, eff: float(tt_ind.solve_power(effect_size=abs(eff), nobs1=n_val, alpha=alpha, alternative=alt))

        # Generate Power Curves across sample size values (from 2 to 2 * N)
        max_n = max(50, sample_size_per_group * 2)
        n_grid = np.unique(np.linspace(2, max_n, 40, dtype=int)).tolist()

        effect_multipliers = [0.5, 1.0, 1.5]
        traces = []
        colors = ["#005a9e", "#008450", "#d13438"]

        for idx, mult in enumerate(effect_multipliers):
            eff_val = d_effect * mult
            pwr_curve = []
            for n_pt in n_grid:
                try:
                    pwr_curve.append(round(power_fn(n_pt, eff_val), 4))
                except Exception:
                    pwr_curve.append(0.0)

            delta_label = f"δ = {delta * mult:.2f}"
            traces.append({
                "x": n_grid,
                "y": pwr_curve,
                "mode": "lines",
                "name": f"Effect: {delta_label}",
                "line": {"color": colors[idx % len(colors)], "width": 2 if mult == 1.0 else 1.5}
            })

        # Reference target lines
        shapes = [
            # Target power line
            {
                "type": "line",
                "xref": "paper",
                "x0": 0,
                "x1": 1,
                "y0": target_p,
                "y1": target_p,
                "line": {"color": "#8a8886", "width": 1, "dash": "dash"}
            },
            # Current sample size line
            {
                "type": "line",
                "x0": sample_size_per_group,
                "x1": sample_size_per_group,
                "y0": 0,
                "y1": 1,
                "line": {"color": "#008450", "width": 1.5, "dash": "dot"}
            }
        ]

        test_name_map = {
            "2_sample_t": "2-Sample t-Test",
            "1_sample_t": "1-Sample t-Test",
            "paired_t": "Paired t-Test",
            "1_proportion": "1 Proportion Test",
            "2_proportions": "2 Proportions Test",
            "anova_1way": "One-Way ANOVA"
        }

        layout = {
            "title": {"text": f"<b>Power Curve for {test_name_map.get(test, test)}</b><br><span style='font-size:11px;color:#605e5c'>α = {alpha:.3f}, Sample Size (N) = {sample_size_per_group}, Power = {actual_power:.4f}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": "Sample Size per Group (N)", "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": "Power (1 - β)", "range": [0, 1.05], "showgrid": True, "gridcolor": "#f3f2f1"},
            "shapes": shapes,
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 55}
        }

        table = TableResult(
            title=f"Power and Sample Size: {test_name_map.get(test, test)}",
            headers=["Parameter / Metric", "Value"],
            rows=[
                ["Test Type", test_name_map.get(test, test)],
                ["Significance Level (α)", f"{alpha:.4f}"],
                ["Difference / Effect Size (δ)", f"{delta:.4f}"],
                ["Standard Deviation (σ)", f"{sigma:.4f}"],
                ["Sample Size per Group (N)", str(sample_size_per_group)],
                ["Target Power", f"{target_p:.4f}"],
                ["Actual Power Achieved", f"{actual_power:.4f}"]
            ]
        )

        text_lines = [
            f"Power and Sample Size: {test_name_map.get(test, test)}",
            f"Testing mean difference = {delta:.4f} with StDev = {sigma:.4f}",
            "",
            f"  Significance level (α)   : {alpha:.4f}",
            f"  Difference (δ)           : {delta:.4f}",
            f"  Target Power             : {target_p:.4f}",
            f"  Sample Size per Group    : {sample_size_per_group}",
            f"  Actual Power Achieved    : {actual_power:.4f}"
        ]

        return AnalysisResult(
            title="Power and Sample Size",
            subtitle=f"{test_name_map.get(test, test)}",
            text_output="\n".join(text_lines),
            tables=[table],
            plotly_figure={"data": traces, "layout": layout},
            statistics={
                "sample_size": sample_size_per_group,
                "power": actual_power,
                "alpha": alpha
            }
        )
