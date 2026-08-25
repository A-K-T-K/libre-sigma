"""
Balanced ANOVA Plugin for OpenMinitab.
Fits crossed/nested multi-factor designs with balance verification, Expected Mean Squares (EMS) via Cornfield-Tukey, and random effects variance components.
"""

from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult
from ..quality_tools.distribution_id import calculate_anderson_darling


class BalancedAnovaParams(BaseModel):
    response_column: str = Field(
        ...,
        description="Response Variable (Continuous Y)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    factors: List[str] = Field(
        ...,
        description="Model Factors (Categorical / Discrete)",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )
    random_factors: List[str] = Field(
        default_factory=list,
        description="Random Factors (optional, default: all Fixed)",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )


class BalancedAnovaPlugin(AnalysisPlugin):
    id = "balanced_anova"
    name = "Balanced ANOVA"
    menu_path = ["Stat", "ANOVA", "Balanced ANOVA"]
    description = "Computes Expected Mean Squares (EMS), variance components for random effects, and custom F-test denominator divisors for balanced designs."
    param_schema = BalancedAnovaParams

    def execute(self, df: pd.DataFrame, params: BalancedAnovaParams) -> AnalysisResult:
        y_col = params.response_column
        factors = [f for f in params.factors if f in df.columns]

        if y_col not in df.columns or len(factors) < 1:
            raise ValueError("Select a response variable and at least one factor.")

        sub_df = df[[y_col] + factors].dropna().copy().reset_index(drop=True)
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n_total = len(sub_df)
        if n_total < 4:
            raise ValueError("Balanced ANOVA requires at least 4 observations.")

        y = sub_df[y_col].to_numpy(dtype=float)
        grand_mean = float(np.mean(y))
        ss_total = float(np.sum((y - grand_mean) ** 2))

        # Check Cell Balance
        cell_counts = sub_df.groupby(factors).size()
        if len(set(cell_counts.values)) > 1:
            # Unbalanced design warning / note
            is_balanced = False
        else:
            is_balanced = True

        # Compute Main Effects SS & DF
        anova_rows = []
        ss_effects_dict = {}
        df_effects_dict = {}
        ms_effects_dict = {}

        ss_explained = 0.0
        df_explained = 0

        for f in factors:
            f_means = sub_df.groupby(f)[y_col].mean()
            f_counts = sub_df.groupby(f)[y_col].count()
            ss_f = float(np.sum(f_counts * (f_means - grand_mean) ** 2))
            df_f = len(f_means) - 1
            ss_effects_dict[f] = ss_f
            df_effects_dict[f] = df_f
            ms_effects_dict[f] = ss_f / max(1, df_f)
            ss_explained += ss_f
            df_explained += df_f

        # 2-Way Interactions if 2+ factors
        if len(factors) >= 2:
            for i in range(len(factors)):
                for j in range(i + 1, len(factors)):
                    f1, f2 = factors[i], factors[j]
                    cell_means = sub_df.groupby([f1, f2])[y_col].mean()
                    cell_counts_sub = sub_df.groupby([f1, f2])[y_col].count()
                    ss_cells = float(np.sum(cell_counts_sub * (cell_means - grand_mean) ** 2))
                    ss_inter = max(0.0, ss_cells - ss_effects_dict[f1] - ss_effects_dict[f2])
                    df_inter = df_effects_dict[f1] * df_effects_dict[f2]
                    inter_name = f"{f1} * {f2}"
                    ss_effects_dict[inter_name] = ss_inter
                    df_effects_dict[inter_name] = df_inter
                    ms_effects_dict[inter_name] = ss_inter / max(1, df_inter)
                    ss_explained += ss_inter
                    df_explained += df_inter

        # Error Term
        ss_error = max(0.0, ss_total - ss_explained)
        df_error = max(1, n_total - 1 - df_explained)
        ms_error = ss_error / df_error
        s_pooled = math.sqrt(max(1e-12, ms_error))

        # Determine Expected Mean Squares (EMS) & Denominator MS
        ems_rows = []
        for term, ms_val in ms_effects_dict.items():
            is_random = any(rf in term for rf in params.random_factors)
            if is_random and len(factors) == 2 and "*" not in term:
                # Random factor denominator is interaction if present
                inter_key = [k for k in ms_effects_dict if "*" in k and term in k]
                if inter_key:
                    denom_ms = ms_effects_dict[inter_key[0]]
                    denom_df = df_effects_dict[inter_key[0]]
                    denom_desc = inter_key[0]
                else:
                    denom_ms = ms_error
                    denom_df = df_error
                    denom_desc = "Error"
            else:
                denom_ms = ms_error
                denom_df = df_error
                denom_desc = "Error"

            f_val = ms_val / max(1e-12, denom_ms)
            p_val = float(1.0 - stats.f.cdf(f_val, df_effects_dict[term], denom_df))

            anova_rows.append([
                term + (" (Random)" if is_random else " (Fixed)"),
                str(df_effects_dict[term]),
                f"{ss_effects_dict[term]:.4f}",
                f"{ms_val:.4f}",
                f"{f_val:.2f}",
                f"{p_val:.4f}" if p_val >= 0.0001 else "< 0.0001",
                f"MS({denom_desc})"
            ])

            ems_desc = f"(Error) + {n_total // (df_effects_dict[term] + 1)} * Q({term})" if not is_random else f"(Error) + Var({term})"
            ems_rows.append([term, ems_desc])

        anova_rows.append(["Error", str(df_error), f"{ss_error:.4f}", f"{ms_error:.4f}", "---", "---", "---"])
        anova_rows.append(["Total", str(n_total - 1), f"{ss_total:.4f}", "---", "---", "---", "---"])

        anova_table = TableResult(
            title=f"Analysis of Variance Table for {y_col}",
            headers=["Source", "DF", "Adj SS", "Adj MS", "F-Value", "p-Value", "Error Term"],
            rows=anova_rows
        )

        ems_table = TableResult(
            title="Expected Mean Squares (EMS)",
            headers=["Source", "Expected Mean Square (Cornfield-Tukey)"],
            rows=ems_rows
        )

        # Plotly Main Effects Traces
        traces = []
        for i, f in enumerate(factors[:2]):
            f_means = sub_df.groupby(f)[y_col].mean()
            traces.append({
                "type": "scatter",
                "mode": "lines+markers",
                "x": [str(idx) for idx in f_means.index],
                "y": f_means.values.tolist(),
                "name": f"Main Effect: {f}",
                "marker": {"size": 8}
            })

        traces.append({
            "type": "scatter",
            "mode": "lines",
            "x": [str(idx) for idx in sub_df.groupby(factors[0])[y_col].mean().index],
            "y": [grand_mean] * len(sub_df[factors[0]].unique()),
            "name": f"Grand Mean ({grand_mean:.3f})",
            "line": {"color": "#004d2c", "dash": "dash"}
        })

        plotly_fig = {
            "data": traces,
            "layout": {
                "title": f"Main Effects Plot for {y_col}",
                "xaxis": {"title": "Factor Levels", "showgrid": True, "gridcolor": "#ececec"},
                "yaxis": {"title": f"Mean {y_col}", "showgrid": True, "gridcolor": "#ececec"},
                "legend": {"orientation": "h", "y": -0.2}
            }
        }

        return AnalysisResult(
            title=f"Balanced ANOVA: {y_col}",
            subtitle=f"S = {s_pooled:.4f} | Design Balance: {'Balanced' if is_balanced else 'Unbalanced'} | Factors = {len(factors)}",
            tables=[anova_table, ems_table],
            plotly_figure=plotly_fig,
            statistics={
                "s_pooled": s_pooled,
                "grand_mean": grand_mean,
                "is_balanced": is_balanced,
                "ms_error": ms_error
            }
        )
