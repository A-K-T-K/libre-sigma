"""
Acceptance Sampling Plugin for OpenMinitab Quality Tools.
Designs acceptance sampling plans (Attributes and Variables) and generates OC, AOQ, and ATI operating curves.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats, optimize
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class AcceptanceSamplingParams(BaseModel):
    measurement_type: str = Field(
        "attributes",
        description="Sampling Type",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Attributes (Pass / Fail Defectives)", "value": "attributes"},
                {"label": "Variables (Continuous Measurement)", "value": "variables"}
            ]
        }
    )
    aql: float = Field(1.0, ge=0.01, le=20.0, description="Acceptable Quality Level AQL (%)")
    rql: float = Field(5.0, ge=0.05, le=50.0, description="Rejectable Quality Level RQL / LTPD (%)")
    alpha_risk: float = Field(0.05, ge=0.001, le=0.20, description="Producer's Risk Alpha (Default: 0.05)")
    beta_risk: float = Field(0.10, ge=0.001, le=0.30, description="Consumer's Risk Beta (Default: 0.10)")
    lot_size: int = Field(10000, ge=10, le=10000000, description="Lot Size (N)")


class AcceptanceSamplingPlugin(AnalysisPlugin):
    id = "acceptance_sampling"
    name = "Acceptance Sampling by Attributes / Variables"
    menu_path = ["Stat", "Quality Tools", "Acceptance Sampling"]
    description = "Designs single sampling plans and computes Operating Characteristic (OC), AOQ, and ATI performance curves."
    param_schema = AcceptanceSamplingParams

    def execute(self, df: pd.DataFrame, params: AcceptanceSamplingParams) -> AnalysisResult:
        p_aql = params.aql / 100.0
        p_rql = params.rql / 100.0
        alpha = params.alpha_risk
        beta = params.beta_risk
        N = params.lot_size

        if p_aql >= p_rql:
            raise ValueError("AQL must be strictly less than RQL / LTPD.")

        is_attr = params.measurement_type == "attributes"

        if is_attr:
            # Solve for minimal n and integer c using Poisson approximation / Binomial
            best_n, best_c = None, None
            for c_try in range(0, 50):
                # Using chi-square relation for Poisson
                chi_alpha = stats.chi2.ppf(1.0 - alpha, 2 * (c_try + 1))
                chi_beta = stats.chi2.ppf(beta, 2 * (c_try + 1))
                
                n_alpha = math.ceil(chi_alpha / (2.0 * p_aql))
                n_beta = math.ceil(chi_beta / (2.0 * p_rql))
                
                if n_alpha <= n_beta or abs(n_alpha - n_beta) <= 3:
                    best_n = max(n_alpha, n_beta)
                    best_c = c_try
                    break

            if best_n is None:
                best_n, best_c = 125, 3

            # Exact Binomial Pa
            p_grid = np.linspace(0.0001, min(0.20, p_rql * 2.5), 150)
            pa_curve = np.array([stats.binom.cdf(best_c, best_n, p) for p in p_grid], dtype=float)
            aoq_curve = pa_curve * p_grid * ((N - best_n) / N) * 100.0
            ati_curve = best_n + (1.0 - pa_curve) * (N - best_n)

            aoql = float(np.max(aoq_curve))
            pa_at_aql = float(stats.binom.cdf(best_c, best_n, p_aql))
            pa_at_rql = float(stats.binom.cdf(best_c, best_n, p_rql))

            plan_desc = f"Sample Size (n) = {best_n}, Acceptance Number (c) = {best_c}"
        else:
            # Variables Sampling Plan (Normal distribution with known/unknown sigma)
            z_alpha = stats.norm.ppf(1.0 - alpha)
            z_beta = stats.norm.ppf(1.0 - beta)
            z_aql = stats.norm.ppf(1.0 - p_aql)
            z_rql = stats.norm.ppf(1.0 - p_rql)

            k_val = float((z_alpha * z_rql + z_beta * z_aql) / (z_alpha + z_beta))
            n_val = int(math.ceil(((z_alpha + z_beta) / (z_aql - z_rql)) ** 2))
            best_n, best_c = n_val, k_val

            p_grid = np.linspace(0.0001, min(0.20, p_rql * 2.5), 150)
            z_p = stats.norm.ppf(1.0 - p_grid)
            pa_curve = np.array([stats.norm.cdf((z_p_val - k_val) * math.sqrt(best_n)) for z_p_val in z_p], dtype=float)
            aoq_curve = pa_curve * p_grid * ((N - best_n) / N) * 100.0
            ati_curve = best_n + (1.0 - pa_curve) * (N - best_n)

            aoql = float(np.max(aoq_curve))
            pa_at_aql = float(stats.norm.cdf((z_aql - k_val) * math.sqrt(best_n)))
            pa_at_rql = float(stats.norm.cdf((z_rql - k_val) * math.sqrt(best_n)))

            plan_desc = f"Sample Size (n) = {best_n}, Critical Distance (k) = {k_val:.3f}"

        # Build Session Log Tables
        plan_table = TableResult(
            title="Generated Acceptance Sampling Plan",
            headers=["Parameter", "Specification Value"],
            rows=[
                ["Measurement Type", params.measurement_type.capitalize()],
                ["Acceptable Quality Level (AQL)", f"{params.aql:.2f}% (Producer's Risk Alpha = {alpha:.2f})"],
                ["Rejectable Quality Level (RQL / LTPD)", f"{params.rql:.2f}% (Consumer's Risk Beta = {beta:.2f})"],
                ["Lot Size (N)", f"{N:,}"],
                ["Calculated Sample Size (n)", str(best_n)],
                ["Acceptance Limit", f"c = {best_c}" if is_attr else f"k = {best_c:.3f}"],
                ["Actual Probability of Acceptance at AQL", f"{pa_at_aql * 100.0:.2f}%"],
                ["Actual Probability of Acceptance at RQL", f"{pa_at_rql * 100.0:.2f}%"],
                ["Average Outgoing Quality Limit (AOQL)", f"{aoql:.3f}%"]
            ]
        )

        # Plotly 3-Panel Operating Curves
        p_pct = (p_grid * 100.0).tolist()

        plotly_fig = {
            "data": [
                # Panel 1: OC Curve
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": p_pct,
                    "y": pa_curve.tolist(),
                    "name": "OC Curve (Pa)",
                    "line": {"color": "#0078d4", "width": 2.5},
                    "xaxis": "x1",
                    "yaxis": "y1"
                },

                # Panel 2: AOQ Curve
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": p_pct,
                    "y": aoq_curve.tolist(),
                    "name": "AOQ Curve (%)",
                    "line": {"color": "#008450", "width": 2.5},
                    "xaxis": "x2",
                    "yaxis": "y2"
                },

                # Panel 3: ATI Curve
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": p_pct,
                    "y": ati_curve.tolist(),
                    "name": "ATI Curve (Units)",
                    "line": {"color": "#ca5010", "width": 2.5},
                    "xaxis": "x3",
                    "yaxis": "y3"
                }
            ],
            "layout": {
                "title": f"Acceptance Sampling Operating Characteristic Curves ({plan_desc})",
                "grid": {"rows": 1, "columns": 3, "pattern": "independent"},
                "showlegend": False,
                "margin": {"l": 40, "r": 30, "t": 60, "b": 40}
            }
        }

        return AnalysisResult(
            title=f"Acceptance Sampling Plan ({params.measurement_type.capitalize()})",
            subtitle=f"{plan_desc} | AOQL = {aoql:.3f}%",
            tables=[plan_table],
            plotly_figure=plotly_fig,
            statistics={
                "sample_size_n": best_n,
                "accept_limit": best_c,
                "aoql": aoql,
                "pa_aql": pa_at_aql,
                "pa_rql": pa_at_rql
            }
        )
