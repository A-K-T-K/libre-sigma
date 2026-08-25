import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class PoissonGoodnessOfFitParams(BaseModel):
    data_mode: str = Field(
        "raw",
        description="Data Format",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Raw occurrence observations in a column", "value": "raw"},
                {"label": "Frequency table (Counts & Frequencies)", "value": "frequency"},
            ]
        }
    )
    observed_col: str = Field(
        ...,
        description="Observed data or frequencies column",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    category_col: Optional[str] = Field(
        None,
        description="Category/Value column (for frequency table)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    hypothesized_mean: Optional[float] = Field(
        None,
        description="Hypothesized Poisson mean (leave empty to estimate from data)",
        json_schema_extra={"ui_type": "number"}
    )


class PoissonGoodnessOfFitPlugin(AnalysisPlugin):
    id = "goodness_of_fit_poisson"
    name = "Poisson Goodness-of-Fit Test"
    menu_path = ["Stat", "Basic Statistics", "Poisson Goodness-of-Fit Test"]
    description = "Performs a Chi-Square goodness-of-fit test to determine whether data follow a Poisson distribution."
    param_schema = PoissonGoodnessOfFitParams

    def execute(self, df: pd.DataFrame, params: PoissonGoodnessOfFitParams) -> AnalysisResult:
        if params.observed_col not in df.columns:
            raise ValueError(f"Column '{params.observed_col}' not found in active worksheet.")

        if params.data_mode == "raw":
            raw_vals = pd.to_numeric(df[params.observed_col], errors="coerce").dropna().to_numpy(dtype=int)
            if len(raw_vals) < 5:
                raise ValueError("Goodness-of-fit test requires at least 5 observations.")
            # Build frequency table from raw counts
            unique_vals, counts = np.unique(raw_vals, return_counts=True)
            obs_map = dict(zip(unique_vals, counts))
            n_total = len(raw_vals)
            lam_est = float(np.mean(raw_vals))
        else:
            # Frequency table
            freqs = pd.to_numeric(df[params.observed_col], errors="coerce").dropna().to_numpy(dtype=int)
            if params.category_col and params.category_col in df.columns:
                cats = pd.to_numeric(df[params.category_col], errors="coerce").dropna().to_numpy(dtype=int)
            else:
                cats = np.arange(len(freqs))
            n_total = int(np.sum(freqs))
            if n_total < 5:
                raise ValueError("Total frequency count must be at least 5.")
            obs_map = dict(zip(cats, freqs))
            lam_est = float(np.sum(cats * freqs) / n_total)

        # Use hypothesized or estimated lambda
        is_estimated = params.hypothesized_mean is None or params.hypothesized_mean <= 0
        lam = float(params.hypothesized_mean) if not is_estimated else lam_est

        # Determine categories (0 up to max observed + 1)
        max_cat = max(obs_map.keys()) if obs_map else 5
        categories = list(range(0, max_cat + 1))

        # Expected counts
        exp_probs = []
        for c in categories:
            if c == categories[-1]:
                # Last category pool: >= max_cat
                p = float(1.0 - stats.poisson.cdf(c - 1, lam)) if c > 0 else 1.0
            else:
                p = float(stats.poisson.pmf(c, lam))
            exp_probs.append(p)

        exp_counts = [p * n_total for p in exp_probs]
        obs_counts = [obs_map.get(c, 0) for c in categories]

        # Combine small expected bins (< 1 or pooled)
        table_rows = []
        chi2_total = 0.0
        for i, c in enumerate(categories):
            cat_label = f"<= {c}" if i == 0 and c > 0 else f">= {c}" if i == len(categories) - 1 else str(c)
            o = int(obs_counts[i])
            e = float(exp_counts[i])
            contrib = float(((o - e) ** 2) / e) if e > 0 else 0.0
            chi2_total += contrib
            table_rows.append([cat_label, o, f"{e:.3f}", f"{contrib:.4f}"])

        # Degrees of Freedom: (Number of bins) - 1 - (1 if estimated lambda else 0)
        k_bins = len(categories)
        df_deg = max(1, k_bins - 1 - (1 if is_estimated else 0))
        p_val = float(1.0 - stats.chi2.cdf(chi2_total, df=df_deg))

        # Tables
        headers = ["Category", "Observed", "Expected", "Contribution to Chi-Square"]
        test_headers = ["Chi-Square Statistic", "DF", "P-Value", "Mean (Lambda)"]
        test_rows = [[f"{chi2_total:.4f}", str(df_deg), f"{p_val:.4f}", f"{lam:.4f}" + (" (Estimated)" if is_estimated else " (Hypothesized)")]]

        text_lines = [
            f"Poisson Goodness-of-Fit Test for {params.observed_col}",
            "",
            f"Mean (Lambda) = {lam:.4f}" + (" (estimated from sample)" if is_estimated else " (hypothesized)"),
            f"Sample size N = {n_total}",
            "",
            f"  {'Category':<12} {'Observed':>10} {'Expected':>12} {'Contribution':>15}",
            f"  {'-'*12} {'-'*10} {'-'*12} {'-'*15}",
        ]
        for r in table_rows:
            text_lines.append(f"  {r[0]:<12} {r[1]:>10} {r[2]:>12} {r[3]:>15}")

        text_lines.extend([
            "",
            f"Chi-Square = {chi2_total:.4f}, DF = {df_deg}, P-Value = {p_val:.4f}",
        ])

        # Plot: Observed vs Expected Comparison
        plot_data = [
            {
                "type": "bar",
                "x": [r[0] for r in table_rows],
                "y": [r[1] for r in table_rows],
                "name": "Observed",
                "marker": {"color": "#2563eb"},
            },
            {
                "type": "bar",
                "x": [r[0] for r in table_rows],
                "y": [float(r[2]) for r in table_rows],
                "name": f"Expected Poisson (mean={lam:.2f})",
                "marker": {"color": "#93c5fd"},
            }
        ]

        layout = {
            "title": {"text": f"<b>Observed vs Expected Counts (Poisson Fit, mean={lam:.2f})</b>", "x": 0.5},
            "barmode": "group",
            "showlegend": True,
            "margin": {"l": 70, "r": 50, "t": 70, "b": 50},
            "height": 400,
            "xaxis": {"title": {"text": "Category"}},
            "yaxis": {"title": {"text": "Count"}, "showgrid": True, "gridcolor": "#ececec"},
        }

        return AnalysisResult(
            title="Poisson Goodness-of-Fit Test",
            subtitle=f"{params.observed_col} (Mean = {lam:.3f})",
            text_output="\n".join(text_lines),
            tables=[
                TableResult(title="Goodness-of-Fit Contribution Table", headers=headers, rows=table_rows),
                TableResult(title="Test Results", headers=test_headers, rows=test_rows)
            ],
            statistics={"chi2_stat": chi2_total, "df": df_deg, "p_value": p_val, "lambda": lam},
            plotly_figure={"data": plot_data, "layout": layout}
        )
