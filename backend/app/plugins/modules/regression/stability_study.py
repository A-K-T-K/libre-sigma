"""
Stability Study (Shelf-Life Analysis) Plugin for OpenMinitab Regression.
Follows ICH Q1E guidelines for pharmaceutical and stability testing with sequential ANCOVA poolability tests and 95% confidence shelf-life estimation.
"""

from typing import Any, Dict, List, Optional, Tuple
import math
import numpy as np
import pandas as pd
from scipy import stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class StabilityStudyParams(BaseModel):
    response_y: str = Field(
        ...,
        description="Response Variable (e.g. Assay % / Potency)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    time_column: str = Field(
        ...,
        description="Time Variable (e.g. Month / Day)",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    batch_column: str = Field(
        ...,
        description="Batch / Lot Variable (Categorical)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    lsl: Optional[float] = Field(None, description="Lower Specification Limit (LSL, e.g. 90.0%)")
    usl: Optional[float] = Field(None, description="Upper Specification Limit (USL, e.g. 110.0%)")
    alpha_pool: float = Field(0.25, ge=0.01, le=0.50, description="Significance Level to Pool Batches (Default: 0.25, ICH Q1E standard)")


class StabilityStudyPlugin(AnalysisPlugin):
    id = "stability_study"
    name = "Stability Study (Shelf-Life Analysis)"
    menu_path = ["Stat", "Regression", "Stability Study"]
    description = "Evaluates pharmaceutical and product shelf-life using ICH Q1E sequential ANCOVA poolability testing and 95% one-sided confidence limits."
    param_schema = StabilityStudyParams

    def execute(self, df: pd.DataFrame, params: StabilityStudyParams) -> AnalysisResult:
        y_col, time_col, batch_col = params.response_y, params.time_column, params.batch_column
        lsl, usl = params.lsl, params.usl

        if lsl is None and usl is None:
            raise ValueError("Specify at least one specification limit (LSL or USL) to compute Shelf Life.")

        for c in [y_col, time_col, batch_col]:
            if c not in df.columns:
                raise ValueError(f"Column '{c}' not found in active worksheet.")

        sub_df = df[[y_col, time_col, batch_col]].dropna().copy()
        sub_df[y_col] = pd.to_numeric(sub_df[y_col], errors="coerce")
        sub_df[time_col] = pd.to_numeric(sub_df[time_col], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        if len(sub_df) < 6:
            raise ValueError("Stability Study requires at least 6 observations.")

        batches = sorted(sub_df[batch_col].unique())
        k_batches = len(batches)
        if k_batches < 2:
            raise ValueError("Stability Study requires at least 2 distinct batches to test poolability.")

        n = len(sub_df)
        y = sub_df[y_col].to_numpy(dtype=float)
        time_vals = sub_df[time_col].to_numpy(dtype=float)

        # Build Full ANCOVA Matrix (Separate Intercepts & Separate Slopes)
        # Model 1: Full (k intercepts, k slopes -> 2k params)
        X_full_cols = []
        for b in batches:
            mask = (sub_df[batch_col] == b).astype(float).to_numpy()
            X_full_cols.append(mask)              # Batch intercept
            X_full_cols.append(mask * time_vals)  # Batch slope

        X_full = np.column_stack(X_full_cols)
        beta_full = np.linalg.pinv(X_full.T @ X_full) @ (X_full.T @ y)
        ss_res_full = float(np.sum((y - X_full @ beta_full) ** 2))
        df_res_full = n - 2 * k_batches

        # Model 2: Common Slope, Separate Intercepts (k intercepts, 1 slope -> k + 1 params)
        X_cs_cols = []
        for b in batches:
            mask = (sub_df[batch_col] == b).astype(float).to_numpy()
            X_cs_cols.append(mask)
        X_cs_cols.append(time_vals) # Common slope
        X_cs = np.column_stack(X_cs_cols)
        beta_cs = np.linalg.pinv(X_cs.T @ X_cs) @ (X_cs.T @ y)
        ss_res_cs = float(np.sum((y - X_cs @ beta_cs) ** 2))
        df_res_cs = n - (k_batches + 1)

        # Model 3: Common Intercept, Common Slope (1 intercept, 1 slope -> 2 params)
        X_pooled = np.column_stack([np.ones(n, dtype=float), time_vals])
        beta_pooled = np.linalg.pinv(X_pooled.T @ X_pooled) @ (X_pooled.T @ y)
        ss_res_pooled = float(np.sum((y - X_pooled @ beta_pooled) ** 2))
        df_res_pooled = n - 2

        # Step 1: Test for Equal Slopes (Interaction: Time * Batch)
        ss_diff_slopes = max(0.0, ss_res_cs - ss_res_full)
        df_diff_slopes = k_batches - 1
        ms_diff_slopes = ss_diff_slopes / max(1, df_diff_slopes)
        ms_res_full = ss_res_full / max(1, df_res_full)
        f_slopes = ms_diff_slopes / max(1e-12, ms_res_full)
        p_slopes = float(1.0 - stats.f.cdf(f_slopes, df_diff_slopes, df_res_full))

        slopes_poolable = p_slopes > params.alpha_pool

        # Step 2: Test for Equal Intercepts (Batch main effect)
        if slopes_poolable:
            ss_diff_intercepts = max(0.0, ss_res_pooled - ss_res_cs)
            df_diff_intercepts = k_batches - 1
            ms_diff_intercepts = ss_diff_intercepts / max(1, df_diff_intercepts)
            ms_res_cs = ss_res_cs / max(1, df_res_cs)
            f_intercepts = ms_diff_intercepts / max(1e-12, ms_res_cs)
            p_intercepts = float(1.0 - stats.f.cdf(f_intercepts, df_diff_intercepts, df_res_cs))
            intercepts_poolable = p_intercepts > params.alpha_pool
        else:
            f_intercepts, p_intercepts = 0.0, 0.0
            intercepts_poolable = False

        # Select Final Model
        if slopes_poolable and intercepts_poolable:
            selected_model_name = "Common Intercept and Common Slope (Fully Pooled)"
            final_X = X_pooled
            final_beta = beta_pooled
            final_ss_res = ss_res_pooled
            final_df_res = df_res_pooled
        elif slopes_poolable and not intercepts_poolable:
            selected_model_name = "Separate Intercepts and Common Slope"
            final_X = X_cs
            final_beta = beta_cs
            final_ss_res = ss_res_cs
            final_df_res = df_res_cs
        else:
            selected_model_name = "Separate Intercepts and Separate Slopes (Unpooled)"
            final_X = X_full
            final_beta = beta_full
            final_ss_res = ss_res_full
            final_df_res = df_res_full

        final_s = math.sqrt(final_ss_res / max(1, final_df_res))

        # Calculate Shelf Life & 95% One-Sided Confidence Limits
        # Fine time grid from 0 to 60 (or 2x max observed time)
        max_t = max(24.0, float(np.max(time_vals)) * 1.5)
        t_grid = np.linspace(0.0, max_t, 300)
        t_crit = stats.t.ppf(0.95, df=final_df_res) # 95% one-sided

        shelf_lives = []
        traces = []

        # Color palette for batches
        colors = ["#0078d4", "#008450", "#d13438", "#881798", "#ca5010", "#038387", "#e3008c"]

        for i, b in enumerate(batches):
            b_df = sub_df[sub_df[batch_col] == b]
            b_t = b_df[time_col].to_numpy(dtype=float)
            b_y = b_df[y_col].to_numpy(dtype=float)
            col_b = colors[i % len(colors)]

            # Plot raw batch points
            traces.append({
                "type": "scatter",
                "mode": "markers",
                "x": b_t.tolist(),
                "y": b_y.tolist(),
                "name": f"Batch {b}",
                "marker": {"color": col_b, "size": 6}
            })

            # Evaluate batch predicted line and one-sided lower/upper 95% CI
            if selected_model_name.startswith("Common Intercept and Common Slope"):
                b0 = final_beta[0]
                b1 = final_beta[1]
                X_eval = np.column_stack([np.ones(len(t_grid)), t_grid])
                xtx_inv = np.linalg.pinv(final_X.T @ final_X)
                se_fit = final_s * np.sqrt(np.sum((X_eval @ xtx_inv) * X_eval, axis=1))
            elif selected_model_name.startswith("Separate Intercepts and Common Slope"):
                b0 = final_beta[i]
                b1 = final_beta[-1]
                eval_cols = [np.zeros(len(t_grid)) for _ in range(k_batches)]
                eval_cols[i] = np.ones(len(t_grid))
                eval_cols.append(t_grid)
                X_eval = np.column_stack(eval_cols)
                xtx_inv = np.linalg.pinv(final_X.T @ final_X)
                se_fit = final_s * np.sqrt(np.sum((X_eval @ xtx_inv) * X_eval, axis=1))
            else: # Separate intercepts & separate slopes
                b0 = final_beta[2 * i]
                b1 = final_beta[2 * i + 1]
                eval_cols = [np.zeros(len(t_grid)) for _ in range(2 * k_batches)]
                eval_cols[2 * i] = np.ones(len(t_grid))
                eval_cols[2 * i + 1] = t_grid
                X_eval = np.column_stack(eval_cols)
                xtx_inv = np.linalg.pinv(final_X.T @ final_X)
                se_fit = final_s * np.sqrt(np.sum((X_eval @ xtx_inv) * X_eval, axis=1))

            y_fit = b0 + b1 * t_grid
            lower_95_ci = y_fit - t_crit * se_fit
            upper_95_ci = y_fit + t_crit * se_fit

            # Plot fitted line
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "x": t_grid.tolist(),
                "y": y_fit.tolist(),
                "name": f"Fit Batch {b}",
                "line": {"color": col_b, "width": 1.5}
            })

            # Check intersection for Shelf Life
            batch_shelf_life = max_t
            if lsl is not None:
                # Find earliest time lower 95% CI drops below LSL
                crossings = t_grid[lower_95_ci < lsl]
                if len(crossings) > 0:
                    batch_shelf_life = float(crossings[0])
            elif usl is not None:
                crossings = t_grid[upper_95_ci > usl]
                if len(crossings) > 0:
                    batch_shelf_life = float(crossings[0])

            shelf_lives.append(batch_shelf_life)

            # Plot lower 95% confidence curve
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "x": t_grid.tolist(),
                "y": lower_95_ci.tolist() if lsl is not None else upper_95_ci.tolist(),
                "name": f"95% CI Limit (Batch {b})",
                "line": {"color": col_b, "dash": "dot", "width": 1.5}
            })

        overall_shelf_life = float(min(shelf_lives))

        # Build Session Log Tables
        ancova_table = TableResult(
            title="ANCOVA Poolability Tests (ICH Q1E Guidelines, Alpha = 0.25)",
            headers=["Test Condition", "DF", "F-Statistic", "p-Value", "Poolability Decision"],
            rows=[
                [
                    "Equality of Slopes (Time * Batch)",
                    f"{df_diff_slopes}, {df_res_full}",
                    f"{f_slopes:.2f}",
                    f"{p_slopes:.4f}" if p_slopes >= 0.0001 else "< 0.0001",
                    "Poolable (Common Slope)" if slopes_poolable else "Not Poolable (Separate Slopes)"
                ],
                [
                    "Equality of Intercepts (Batch)",
                    f"{df_diff_intercepts}, {df_res_cs}" if slopes_poolable else "---",
                    f"{f_intercepts:.2f}" if slopes_poolable else "---",
                    f"{p_intercepts:.4f}" if slopes_poolable else "---",
                    "Poolable (Common Intercept)" if intercepts_poolable else "Separate Intercepts"
                ]
            ]
        )

        shelf_life_table = TableResult(
            title="Estimated Product Shelf-Life",
            headers=["Selected Stability Model", "Specification Threshold", "Earliest Batch Shelf-Life", "Overall Estimated Shelf-Life"],
            rows=[[
                selected_model_name,
                f"LSL = {lsl:.2f}%" if lsl is not None else f"USL = {usl:.2f}%",
                f"{overall_shelf_life:.2f} time units",
                f"<b>{overall_shelf_life:.1f} Months</b>"
            ]]
        )

        # Plot Specs and Shelf Life Line
        shapes = []
        if lsl is not None:
            shapes.append({"type": "line", "x0": 0, "y0": lsl, "x1": max_t, "y1": lsl, "line": {"color": "#d13438", "width": 2, "dash": "solid"}})
        if usl is not None:
            shapes.append({"type": "line", "x0": 0, "y0": usl, "x1": max_t, "y1": usl, "line": {"color": "#d13438", "width": 2, "dash": "solid"}})

        # Shelf Life vertical line
        shapes.append({"type": "line", "x0": overall_shelf_life, "y0": lsl or 0, "x1": overall_shelf_life, "y1": (lsl or 100) + 15, "line": {"color": "#008450", "width": 2.5, "dash": "dash"}})

        plotly_fig = {
            "data": traces,
            "layout": {
                "title": f"Stability Study & Shelf-Life Report for {y_col} (ICH Q1E)",
                "xaxis": {"title": f"{time_col} (Time)", "showgrid": True, "gridcolor": "#ececec", "range": [0, max_t]},
                "yaxis": {"title": y_col, "showgrid": True, "gridcolor": "#ececec"},
                "shapes": shapes,
                "legend": {"orientation": "h", "y": -0.2},
                "annotations": [
                    {
                        "x": overall_shelf_life,
                        "y": (lsl or 100) + 10,
                        "text": f"<b>Estimated Shelf-Life: {overall_shelf_life:.1f}</b>",
                        "showarrow": True,
                        "arrowhead": 2,
                        "bgcolor": "#008450",
                        "font": {"color": "white", "size": 11}
                    }
                ]
            }
        }

        return AnalysisResult(
            title=f"Stability Study for {y_col}",
            subtitle=f"Estimated Shelf-Life = {overall_shelf_life:.1f} units | Model: {selected_model_name}",
            tables=[ancova_table, shelf_life_table],
            plotly_figure=plotly_fig,
            statistics={
                "shelf_life": overall_shelf_life,
                "selected_model": selected_model_name,
                "p_slopes": p_slopes,
                "p_intercepts": p_intercepts,
                "num_batches": k_batches
            }
        )
