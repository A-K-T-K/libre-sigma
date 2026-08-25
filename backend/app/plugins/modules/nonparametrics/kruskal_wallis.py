"""
Kruskal-Wallis Test Plugin for OpenMinitab.
Performs Nonparametric One-Way ANOVA across k independent groups.
Computes Median, Average Rank, Z-value per factor level, H-statistic (unadjusted and adjusted for ties), and supports rank storage.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class KruskalWallisParams(BaseModel):
    response: str = Field(
        ...,
        description="Response Variable (Continuous Numeric)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    factor: str = Field(
        ...,
        description="Factor Variable (Grouping / Categorical)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    # Storage Sub-Modal
    store_ranks: bool = Field(
        False,
        description="Store Group Ranks in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )
    store_residuals: bool = Field(
        False,
        description="Store Score Residuals in Worksheet",
        json_schema_extra={"sub_modal": "Storage..."}
    )


class KruskalWallisPlugin(AnalysisPlugin):
    id = "nonparam_kruskal_wallis"
    name = "Kruskal-Wallis"
    menu_path = ["Stat", "Nonparametrics", "Kruskal-Wallis"]
    description = "Nonparametric alternative to One-Way ANOVA for comparing medians across two or more independent groups."
    param_schema = KruskalWallisParams

    def execute(self, df: pd.DataFrame, params: KruskalWallisParams) -> AnalysisResult:
        resp_col, factor_col = params.response, params.factor
        if resp_col not in df.columns or factor_col not in df.columns:
            raise ValueError(f"Columns '{resp_col}' and/or '{factor_col}' not found in active worksheet.")

        sub_df = df[[factor_col, resp_col]].dropna().copy()
        sub_df[resp_col] = pd.to_numeric(sub_df[resp_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        n_total = len(sub_df)
        if n_total < 3:
            raise ValueError("Kruskal-Wallis test requires at least 3 valid observations.")

        groups = sub_df[factor_col].unique()
        k = len(groups)
        if k < 2:
            raise ValueError(f"Factor '{factor_col}' must contain at least 2 distinct levels.")

        # Compute overall ranks (scipy rankdata handles fractional average ties)
        all_vals = sub_df[resp_col].to_numpy(dtype=float)
        ranks = stats.rankdata(all_vals)
        sub_df["_rank"] = ranks

        group_arrays = [sub_df[sub_df[factor_col] == g][resp_col].to_numpy(dtype=float) for g in groups]

        # Kruskal-Wallis H-test
        kw_res = stats.kruskal(*group_arrays)
        h_adjusted = float(kw_res.statistic)
        p_adjusted = float(kw_res.pvalue)

        # Unadjusted H
        # H_unadj = (12 / (N*(N+1))) * sum(n_i * (R_bar_i - R_bar_overall)^2)
        overall_avg_rank = (n_total + 1) / 2.0
        sum_sq_diff = 0.0

        group_stats = []
        traces = []

        for g in groups:
            grp_data = sub_df[sub_df[factor_col] == g]
            grp_y = grp_data[resp_col].to_numpy()
            grp_ranks = grp_data["_rank"].to_numpy()

            n_i = len(grp_y)
            med_i = float(np.median(grp_y))
            avg_rank_i = float(np.mean(grp_ranks))
            sum_sq_diff += n_i * ((avg_rank_i - overall_avg_rank) ** 2)

            # Z-value for group: (R_bar_i - overall_avg_rank) / sqrt((N*(N+1)/12) * ( (N - n_i) / (n_i*(N - 1)) ))
            se_rank_i = np.sqrt(((n_total * (n_total + 1)) / 12.0) * ((n_total - n_i) / max(1, n_i * (n_total - 1))))
            z_i = (avg_rank_i - overall_avg_rank) / se_rank_i if se_rank_i > 0 else 0.0

            group_stats.append([str(g), n_i, round(med_i, 4), round(avg_rank_i, 2), round(z_i, 2)])

            traces.append({
                "y": grp_y.tolist(),
                "type": "box",
                "name": f"{g} (N={n_i})",
                "boxpoints": "all",
                "jitter": 0.25,
                "pointpos": -1.8
            })

        h_unadjusted = (12.0 / (n_total * (n_total + 1))) * sum_sq_diff
        df_deg = k - 1
        p_unadjusted = float(1.0 - stats.chi2.cdf(h_unadjusted, df_deg))

        layout = {
            "title": {"text": f"<b>Kruskal-Wallis Test on {resp_col} by {factor_col}</b><br><span style='font-size:11px;color:#605e5c'>H = {h_adjusted:.3f} (adj), DF = {df_deg}, p-value = {p_adjusted:.5f}</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": factor_col, "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": resp_col, "showgrid": True, "gridcolor": "#f3f2f1"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 50}
        }

        # Tables
        group_table = TableResult(
            title=f"Kruskal-Wallis Test: {resp_col} versus {factor_col}",
            headers=[factor_col, "N", "Median", "Ave Rank", "Z-Value"],
            rows=group_stats
        )

        test_table = TableResult(
            title="Test Statistics",
            headers=["Criterion", "DF", "H", "P-Value"],
            rows=[
                ["Not Adjusted for Ties", df_deg, round(h_unadjusted, 3), round(p_unadjusted, 5)],
                ["Adjusted for Ties", df_deg, round(h_adjusted, 3), round(p_adjusted, 5)]
            ]
        )

        text_lines = [
            f"Kruskal-Wallis Test: {resp_col} versus {factor_col}",
            "",
            f"  {factor_col:<18} {'N':>6} {'Median':>12} {'Ave Rank':>10} {'Z-Value':>10}",
            f"  {'-'*18} {'-'*6} {'-'*12} {'-'*10} {'-'*10}",
        ]
        for r in group_stats:
            text_lines.append(f"  {r[0]:<18} {r[1]:>6} {r[2]:>12.4f} {r[3]:>10.2f} {r[4]:>10.2f}")
        text_lines += [
            f"  {'Overall':<18} {n_total:>6} {'':<12} {overall_avg_rank:>10.2f}",
            "",
            f"H = {h_unadjusted:.2f}  DF = {df_deg}  P = {p_unadjusted:.4f}",
            f"H = {h_adjusted:.2f}  DF = {df_deg}  P = {p_adjusted:.4f} (adjusted for ties)"
        ]

        # Storage
        storage_cols = []
        new_cols_dict: Dict[str, List[Any]] = {}

        if params.store_ranks:
            col_id = f"rank_{resp_col.lower()}"
            storage_cols.append({"id": col_id, "name": f"RANK_{resp_col}", "type": "numeric"})
            new_cols_dict[col_id] = ranks.tolist()

        if params.store_residuals:
            # Score residual = rank_i - mean_rank_group
            resids = []
            for idx, r_row in sub_df.iterrows():
                g_val = r_row[factor_col]
                grp_sub = sub_df[sub_df[factor_col] == g_val]
                resids.append(round(float(r_row["_rank"] - np.mean(grp_sub["_rank"])), 4))
            col_id = f"rank_res_{resp_col.lower()}"
            storage_cols.append({"id": col_id, "name": f"RES_RANK_{resp_col}", "type": "numeric"})
            new_cols_dict[col_id] = resids

        action_type = None
        worksheet_data = None
        if storage_cols:
            rows_data = []
            for r_i in range(len(sub_df)):
                r_dict = {}
                for col_spec in storage_cols:
                    c_id = col_spec["id"]
                    val_list = new_cols_dict.get(c_id, [])
                    r_dict[c_id] = val_list[r_i] if r_i < len(val_list) else None
                rows_data.append(r_dict)

            action_type = "worksheet_append_columns"
            worksheet_data = {"columns": storage_cols, "rows": rows_data}

        return AnalysisResult(
            title="Kruskal-Wallis Test",
            subtitle=f"{resp_col} by {factor_col}",
            text_output="\n".join(text_lines),
            tables=[group_table, test_table],
            plotly_figure={"data": traces, "layout": layout},
            action_type=action_type,
            worksheet_data=worksheet_data
        )
