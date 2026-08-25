from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from scipy import stats

from ..base import AnalysisPlugin, AnalysisResult, TableResult


class AnalyzeTaguchiParams(BaseModel):
    response_col: str = Field(
        ...,
        description="Response Variable (e.g. Response_1)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    factor_cols: List[str] = Field(
        ...,
        description="Taguchi Control Factors (Select 2 or more)",
        json_schema_extra={"ui_type": "column_multi_picker"}
    )
    sn_ratio_type: str = Field(
        "larger",
        description="Signal-to-Noise Ratio Objective",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Larger is better", "value": "larger"},
                {"label": "Smaller is better", "value": "smaller"},
                {"label": "Nominal is best", "value": "nominal"}
            ]
        }
    )
    nominal_target: Optional[float] = Field(
        None,
        description="Nominal Target Value (T)",
        json_schema_extra={"ui_type": "number"}
    )


class AnalyzeTaguchiDesignPlugin(AnalysisPlugin):
    id = "doe_analyze_taguchi"
    name = "Analyze Taguchi Design"
    menu_path = ["Stat", "DOE", "Taguchi", "Analyze Taguchi Design"]
    description = "Computes Taguchi Response Tables for S/N Ratios and Means, ANOVA models, and Main Effects Plots."
    param_schema = AnalyzeTaguchiParams

    def execute(self, df: pd.DataFrame, params: AnalyzeTaguchiParams) -> AnalysisResult:
        if params.response_col not in df.columns:
            raise ValueError(f"Response column '{params.response_col}' not found in active worksheet.")

        valid_factors = [f for f in params.factor_cols if f in df.columns]
        if len(valid_factors) < 2:
            raise ValueError("Taguchi analysis requires at least 2 control factors present in the worksheet.")

        # Clean sub-dataframe: Only response MUST be strictly numeric, factors can be text, numbers, or categories
        work_cols = [params.response_col] + valid_factors
        sub_df = df[work_cols].copy()
        
        # Convert response to numeric
        sub_df[params.response_col] = pd.to_numeric(sub_df[params.response_col], errors="coerce")
        
        # Clean factor columns without coercing strings to NaN
        for f in valid_factors:
            sub_df[f] = sub_df[f].astype(str).str.strip()
            # Mark empty, 'nan', 'None' as NaN so they are dropped
            sub_df.loc[sub_df[f].isin(["", "nan", "None", "null", "undefined", "NaN"]), f] = np.nan

        clean_df = sub_df.dropna().copy()
        n_runs = len(clean_df)

        if n_runs < 4:
            raise ValueError(f"Found only {n_runs} complete rows. Enter your experimental response values before running analysis.")

        y_vals = clean_df[params.response_col].to_numpy(dtype=float)

        # Compute Signal-to-Noise (SN) ratio per row
        sn_vals = np.zeros(n_runs)
        for i in range(n_runs):
            val = y_vals[i]
            if params.sn_ratio_type == "larger":
                sn_vals[i] = -10.0 * np.log10(1.0 / (val ** 2)) if val != 0 else 0.0
            elif params.sn_ratio_type == "smaller":
                sn_vals[i] = -10.0 * np.log10(val ** 2) if val != 0 else 0.0
            else:  # nominal
                if params.nominal_target is not None:
                    diff = val - float(params.nominal_target)
                    sn_vals[i] = -10.0 * np.log10(diff ** 2) if diff != 0 else 30.0
                else:
                    sn_vals[i] = 10.0 * np.log10(abs(val)) if val != 0 else 0.0

        clean_df["_SN_RATIO"] = sn_vals
        overall_mean_y = float(np.mean(y_vals))
        overall_mean_sn = float(np.mean(sn_vals))

        def sort_levels_key(val: Any):
            s = str(val).strip()
            try:
                return (0, float(s))
            except ValueError:
                return (1, s)

        # 1. Response Tables for S/N Ratios & Means
        max_levels_found = 2
        factor_level_stats_sn = {}
        factor_level_stats_mean = {}

        for f in valid_factors:
            levels = sorted(clean_df[f].unique(), key=sort_levels_key)
            if len(levels) > max_levels_found:
                max_levels_found = len(levels)

            sn_by_level = {}
            mean_by_level = {}
            for lvl in levels:
                lvl_mask = (clean_df[f] == lvl)
                sn_by_level[lvl] = float(np.mean(clean_df.loc[lvl_mask, "_SN_RATIO"]))
                mean_by_level[lvl] = float(np.mean(clean_df.loc[lvl_mask, params.response_col]))

            factor_level_stats_sn[f] = sn_by_level
            factor_level_stats_mean[f] = mean_by_level

        # Calculate Deltas and Ranks
        sn_deltas = {}
        mean_deltas = {}
        for f in valid_factors:
            sn_lvl_vals = list(factor_level_stats_sn[f].values())
            mean_lvl_vals = list(factor_level_stats_mean[f].values())
            sn_deltas[f] = max(sn_lvl_vals) - min(sn_lvl_vals)
            mean_deltas[f] = max(mean_lvl_vals) - min(mean_lvl_vals)

        # Ranks: highest delta gets Rank 1
        sorted_sn_factors = sorted(valid_factors, key=lambda x: sn_deltas[x], reverse=True)
        sn_ranks = {f: sorted_sn_factors.index(f) + 1 for f in valid_factors}

        sorted_mean_factors = sorted(valid_factors, key=lambda x: mean_deltas[x], reverse=True)
        mean_ranks = {f: sorted_mean_factors.index(f) + 1 for f in valid_factors}

        # Format Response Table Headers & Rows
        resp_table_sn_headers = ["Level"] + valid_factors
        resp_table_mean_headers = ["Level"] + valid_factors

        resp_table_sn_rows = []
        resp_table_mean_rows = []

        # Find all unique level indices across factors
        all_unique_levels = []
        for f in valid_factors:
            for l in factor_level_stats_sn[f].keys():
                if l not in all_unique_levels:
                    all_unique_levels.append(l)
        all_unique_levels = sorted(all_unique_levels, key=sort_levels_key)

        for lvl in all_unique_levels:
            sn_row = [str(lvl)]
            mean_row = [str(lvl)]
            for f in valid_factors:
                sn_val = factor_level_stats_sn[f].get(lvl)
                mean_val = factor_level_stats_mean[f].get(lvl)
                sn_row.append(f"{sn_val:.3f}" if sn_val is not None else "—")
                mean_row.append(f"{mean_val:.3f}" if mean_val is not None else "—")
            resp_table_sn_rows.append(sn_row)
            resp_table_mean_rows.append(mean_row)

        # Append Delta and Rank rows
        resp_table_sn_rows.append(["Delta"] + [f"{sn_deltas[f]:.3f}" for f in valid_factors])
        resp_table_sn_rows.append(["Rank"] + [str(sn_ranks[f]) for f in valid_factors])

        resp_table_mean_rows.append(["Delta"] + [f"{mean_deltas[f]:.3f}" for f in valid_factors])
        resp_table_mean_rows.append(["Rank"] + [str(mean_ranks[f]) for f in valid_factors])

        # 2. ANOVA for Means & S/N Ratios
        df_total = n_runs - 1

        # A) ANOVA for Means (Response variable)
        ss_total_y = float(np.sum((y_vals - overall_mean_y) ** 2))
        anova_rows_y = []
        ss_factors_sum_y = 0.0
        df_factors_sum = 0

        for f in valid_factors:
            levels = sorted(clean_df[f].unique(), key=sort_levels_key)
            df_f = len(levels) - 1
            ss_f = 0.0
            for lvl in levels:
                grp_y = clean_df.loc[clean_df[f] == lvl, params.response_col].to_numpy()
                ss_f += len(grp_y) * (np.mean(grp_y) - overall_mean_y) ** 2

            ss_factors_sum_y += ss_f
            df_factors_sum += df_f
            ms_f = ss_f / df_f if df_f > 0 else 0.0
            anova_rows_y.append({"source": f, "df": df_f, "ss": ss_f, "ms": ms_f})

        ss_resid_y = max(0.0, ss_total_y - ss_factors_sum_y)
        df_resid = max(1, df_total - df_factors_sum)
        ms_resid_y = ss_resid_y / df_resid if df_resid > 0 else 0.0

        final_anova_mean_rows = []
        for r in anova_rows_y:
            f_stat = r["ms"] / ms_resid_y if ms_resid_y > 0 else 0.0
            p_val = float(1.0 - stats.f.cdf(f_stat, r["df"], df_resid)) if ms_resid_y > 0 else 0.0
            final_anova_mean_rows.append([
                r["source"],
                int(r["df"]),
                f"{r['ss']:.4f}",
                f"{r['ms']:.4f}",
                f"{f_stat:.2f}" if ms_resid_y > 0 else "—",
                f"{p_val:.4f}" if ms_resid_y > 0 and p_val >= 0.0001 else ("< 0.0001" if ms_resid_y > 0 else "—")
            ])

        final_anova_mean_rows.append(["Residual Error", int(df_resid), f"{ss_resid_y:.4f}", f"{ms_resid_y:.4f}", "—", "—"])
        final_anova_mean_rows.append(["Total", int(df_total), f"{ss_total_y:.4f}", "—", "—", "—"])

        # B) ANOVA for S/N Ratios
        ss_total_sn = float(np.sum((sn_vals - overall_mean_sn) ** 2))
        anova_rows_sn = []
        ss_factors_sum_sn = 0.0

        for f in valid_factors:
            levels = sorted(clean_df[f].unique(), key=sort_levels_key)
            df_f = len(levels) - 1
            ss_f = 0.0
            for lvl in levels:
                grp_sn = clean_df.loc[clean_df[f] == lvl, "_SN_RATIO"].to_numpy()
                ss_f += len(grp_sn) * (np.mean(grp_sn) - overall_mean_sn) ** 2

            ss_factors_sum_sn += ss_f
            ms_f = ss_f / df_f if df_f > 0 else 0.0
            anova_rows_sn.append({"source": f, "df": df_f, "ss": ss_f, "ms": ms_f})

        ss_resid_sn = max(0.0, ss_total_sn - ss_factors_sum_sn)
        ms_resid_sn = ss_resid_sn / df_resid if df_resid > 0 else 0.0

        final_anova_sn_rows = []
        for r in anova_rows_sn:
            f_stat = r["ms"] / ms_resid_sn if ms_resid_sn > 0 else 0.0
            p_val = float(1.0 - stats.f.cdf(f_stat, r["df"], df_resid)) if ms_resid_sn > 0 else 0.0
            final_anova_sn_rows.append([
                r["source"],
                int(r["df"]),
                f"{r['ss']:.4f}",
                f"{r['ms']:.4f}",
                f"{f_stat:.2f}" if ms_resid_sn > 0 else "—",
                f"{p_val:.4f}" if ms_resid_sn > 0 and p_val >= 0.0001 else ("< 0.0001" if ms_resid_sn > 0 else "—")
            ])

        final_anova_sn_rows.append(["Residual Error", int(df_resid), f"{ss_resid_sn:.4f}", f"{ms_resid_sn:.4f}", "—", "—"])
        final_anova_sn_rows.append(["Total", int(df_total), f"{ss_total_sn:.4f}", "—", "—", "—"])

        # Tables for Result
        sn_title_desc = f"Larger is better" if params.sn_ratio_type == "larger" else f"Smaller is better" if params.sn_ratio_type == "smaller" else f"Nominal is best" + (f" (Target = {params.nominal_target})" if params.nominal_target is not None else "")
        sn_table_obj = TableResult(
            title=f"Response Table for Signal to Noise Ratios ({sn_title_desc})",
            headers=resp_table_sn_headers,
            rows=resp_table_sn_rows,
            notes=[f"Objective: {sn_title_desc}", "Rank: 1 indicates highest Delta (most influential factor)"]
        )

        mean_table_obj = TableResult(
            title="Response Table for Means",
            headers=resp_table_mean_headers,
            rows=resp_table_mean_rows,
            notes=["Means for each factor level", "Rank: 1 indicates highest Delta (most influential factor)"]
        )

        anova_sn_table_obj = TableResult(
            title=f"Analysis of Variance for Signal to Noise Ratios ({sn_title_desc})",
            headers=["Source", "DF", "Seq SS", "Adj MS", "F-Value", "p-Value"],
            rows=final_anova_sn_rows,
        )

        anova_mean_table_obj = TableResult(
            title="Analysis of Variance for Means",
            headers=["Source", "DF", "Seq SS", "Adj MS", "F-Value", "p-Value"],
            rows=final_anova_mean_rows,
        )

        # Minitab Standard DOE Session Output text
        text_lines = [
            f"Taguchi Analysis: {params.response_col} versus {', '.join(valid_factors)}",
            "",
            f"Linear Model Analysis: S/N Ratios ({sn_title_desc}) and Means",
            f"S/N Ratio Objective    : {sn_title_desc}",
            f"Overall Mean (Y)       : {overall_mean_y:.4f}",
            f"Overall Mean (S/N)     : {overall_mean_sn:.4f} dB",
            f"Total Runs             : {n_runs}",
            f"Top Factor (S/N Ratio) : {sorted_sn_factors[0]} (Delta = {sn_deltas[sorted_sn_factors[0]]:.3f}, Rank 1)",
            f"Top Factor (Means)     : {sorted_mean_factors[0]} (Delta = {mean_deltas[sorted_mean_factors[0]]:.3f}, Rank 1)",
            "",
            "Model Factor Ranking Summary:",
            f"  {'Factor':<8} {'Rank (S/N)':<12} {'Delta (S/N)':<14} {'Rank (Mean)':<12} {'Delta (Mean)':<14}",
            f"  {'-'*8} {'-'*12} {'-'*14} {'-'*12} {'-'*14}",
        ]
        for f in valid_factors:
            text_lines.append(
                f"  {f:<8} {sn_ranks.get(f, '-'):<12} {sn_deltas.get(f, 0.0):<14.3f} {mean_ranks.get(f, '-'):<12} {mean_deltas.get(f, 0.0):<14.3f}"
            )

        # 3. Build Multi-Panel Main Effects Figures
        def create_multi_panel_plot(
            title_text: str,
            subtitle_text: str,
            y_axis_title: str,
            factor_dict: Dict[str, Dict[Any, float]],
            grand_mean: float
        ) -> Dict[str, Any]:
            k_f = len(valid_factors)
            all_vals = [m for f in valid_factors for m in factor_dict[f].values()]
            y_min = min(all_vals) if all_vals else 0
            y_max = max(all_vals) if all_vals else 1
            y_span = max(0.2, y_max - y_min)
            y_pad = y_span * 0.18
            y_range = [round(y_min - y_pad, 3), round(y_max + y_pad, 3)]

            plot_data = []
            annotations = []
            shapes = [
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "paper", "y0": 1.0, "y1": 1.0, "line": {"color": "#888888", "width": 1}},
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "paper", "y0": 0.0, "y1": 0.0, "line": {"color": "#888888", "width": 1}},
                {"type": "line", "xref": "paper", "x0": 0, "x1": 0, "yref": "paper", "y0": 0.0, "y1": 1.0, "line": {"color": "#888888", "width": 1}},
                {"type": "line", "xref": "paper", "x0": 1.0, "x1": 1.0, "yref": "paper", "y0": 0.0, "y1": 1.0, "line": {"color": "#888888", "width": 1}},
                {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "y", "y0": float(grand_mean), "y1": float(grand_mean), "line": {"color": "#888888", "width": 1.5, "dash": "dash"}}
            ]

            layout = {
                "title": {
                    "text": f"<b>{title_text}</b><br><span style='font-size:11px;color:#64748b;'>{subtitle_text}</span>",
                    "x": 0.5,
                    "xanchor": "center",
                    "y": 0.98,
                    "yanchor": "top",
                },
                "paper_bgcolor": "#ffffff",
                "plot_bgcolor": "#ffffff",
                "showlegend": False,
                "margin": {"l": 75, "r": 40, "t": 75, "b": 50},
                "height": 420,
                "yaxis": {
                    "title": {"text": f"<b>{y_axis_title}</b>", "font": {"size": 12, "color": "#111827"}},
                    "range": y_range,
                    "showgrid": True,
                    "gridcolor": "#ececec",
                    "gridwidth": 1,
                    "showline": True,
                    "linecolor": "#201f1e",
                    "linewidth": 1.25,
                    "mirror": True,
                    "zeroline": False,
                    "ticks": "inside",
                    "tickcolor": "#201f1e",
                    "ticklen": 4,
                }
            }

            for i, f in enumerate(valid_factors):
                levels = sorted(factor_dict[f].keys(), key=sort_levels_key)
                pts = [factor_dict[f][l] for l in levels]
                level_labels = [str(l) for l in levels]

                x_axis_name = "xaxis" if i == 0 else f"xaxis{i + 1}"
                x_axis_ref = "x" if i == 0 else f"x{i + 1}"

                d_start = i / k_f
                d_end = (i + 1) / k_f

                plot_data.append({
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": level_labels,
                    "y": pts,
                    "xaxis": x_axis_ref,
                    "yaxis": "y",
                    "name": f,
                    "line": {"color": "#008450", "width": 2},
                    "marker": {"color": "#008450", "size": 7, "symbol": "circle"},
                    "hoverinfo": "x+y+name",
                    "showlegend": False,
                })

                layout[x_axis_name] = {
                    "domain": [d_start, d_end],
                    "anchor": "y",
                    "showgrid": True,
                    "gridcolor": "#ececec",
                    "gridwidth": 1,
                    "showline": True,
                    "linecolor": "#201f1e",
                    "linewidth": 1.25,
                    "mirror": True if i == 0 or i == k_f - 1 else "ticks",
                    "zeroline": False,
                    "ticks": "inside",
                    "tickcolor": "#201f1e",
                    "ticklen": 4,
                    "tickmode": "array",
                    "tickvals": level_labels,
                    "ticktext": level_labels,
                }

                annotations.append({
                    "xref": "paper",
                    "yref": "paper",
                    "x": (d_start + d_end) / 2.0,
                    "y": 1.0,
                    "xanchor": "center",
                    "yanchor": "bottom",
                    "text": f"<b>&nbsp;{f}&nbsp;</b>",
                    "showarrow": False,
                    "bordercolor": "#201f1e",
                    "borderwidth": 1,
                    "borderpad": 3,
                    "bgcolor": "#ffffff",
                    "font": {"size": 11, "color": "#111827"}
                })

                if i > 0:
                    shapes.append({
                        "type": "line",
                        "xref": "paper",
                        "x0": d_start,
                        "x1": d_start,
                        "yref": "paper",
                        "y0": 0,
                        "y1": 1.0,
                        "line": {"color": "#201f1e", "width": 1}
                    })

            layout["annotations"] = annotations
            layout["shapes"] = shapes
            return {"data": plot_data, "layout": layout}

        # 1. Means Multi-panel Plot
        means_fig = create_multi_panel_plot(
            title_text="Main Effects Plot for Means",
            subtitle_text="Data Means",
            y_axis_title="Mean of Means",
            factor_dict=factor_level_stats_mean,
            grand_mean=overall_mean_y
        )

        # 2. S/N Ratio Multi-panel Plot
        sn_fig = create_multi_panel_plot(
            title_text="Main Effects Plot for SN ratios",
            subtitle_text=f"Signal-to-Noise: {sn_title_desc}",
            y_axis_title="Mean of SN Ratios (dB)",
            factor_dict=factor_level_stats_sn,
            grand_mean=overall_mean_sn
        )

        return AnalysisResult(
            title="Taguchi Analysis",
            subtitle=f"{params.response_col} vs {', '.join(valid_factors)}",
            text_output="\n".join(text_lines),
            tables=[sn_table_obj, mean_table_obj, anova_sn_table_obj, anova_mean_table_obj],
            statistics={
                "sn_deltas": sn_deltas,
                "mean_deltas": mean_deltas,
                "sn_ranks": sn_ranks,
                "mean_ranks": mean_ranks,
                "overall_mean_y": overall_mean_y,
                "overall_mean_sn": overall_mean_sn
            },
            plotly_figure=means_fig,
            plotly_figures=[means_fig, sn_fig]
        )
