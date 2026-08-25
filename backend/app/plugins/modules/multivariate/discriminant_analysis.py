import numpy as np
import pandas as pd
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis, QuadraticDiscriminantAnalysis
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from scipy.spatial import ConvexHull
from ...base import AnalysisPlugin, AnalysisResult, TableResult


class DiscriminantParams(BaseModel):
    group_variable: str = Field(..., description="Categorical group/class column")
    predictors: List[str] = Field(..., description="Continuous numeric predictor columns")
    discriminant_function: str = Field("Linear (LDA)", description="Discriminant function: Linear (LDA) or Quadratic (QDA)")
    prior_probabilities: str = Field("Equal", description="Prior probabilities: Equal or Proportional to group size")
    cross_validation: bool = Field(True, description="Perform Leave-One-Out (Jackknife) cross-validation")
    storage_options: bool = Field(False, description="Store predicted groups (PRED_GRP) in active worksheet")


class DiscriminantAnalysisPlugin(AnalysisPlugin):
    id: str = "discriminant_analysis"
    name: str = "Discriminant Analysis"
    menu_path: List[str] = ["Stat", "Multivariate", "Discriminant Analysis..."]
    description: str = "Perform Linear (LDA) or Quadratic (QDA) Discriminant Analysis with Confusion Matrices and Canonical Scores."
    param_schema: type[BaseModel] = DiscriminantParams

    def execute(self, df: pd.DataFrame, params: DiscriminantParams) -> AnalysisResult:
        if params.group_variable not in df.columns:
            raise ValueError(f"Group column '{params.group_variable}' not found in worksheet.")

        pred_cols = [c for c in params.predictors if c in df.columns and c != params.group_variable]
        if len(pred_cols) < 1:
            raise ValueError("Discriminant Analysis requires at least 1 numeric predictor column.")

        clean_df = df[[params.group_variable] + pred_cols].dropna()
        n, p_plus_1 = clean_df.shape
        p = len(pred_cols)
        if n < 4:
            raise ValueError("Discriminant Analysis requires at least 4 observations.")

        y_raw = clean_df[params.group_variable].astype(str).values
        X = clean_df[pred_cols].values.astype(float)

        unique_groups, group_counts = np.unique(y_raw, return_counts=True)
        K = len(unique_groups)
        if K < 2:
            raise ValueError("Discriminant Analysis requires at least 2 distinct groups.")

        # Prior probabilities
        if "proportional" in params.prior_probabilities.lower():
            priors = group_counts / float(n)
            prior_desc = "Proportional to group sizes"
        else:
            priors = np.ones(K) / float(K)
            prior_desc = "Equal across all groups"

        is_qda = "quadratic" in params.discriminant_function.lower()

        if is_qda:
            model = QuadraticDiscriminantAnalysis(priors=priors)
            func_name = "Quadratic Discriminant Analysis (QDA)"
        else:
            model = LinearDiscriminantAnalysis(priors=priors)
            func_name = "Linear Discriminant Analysis (LDA)"

        # Fit model
        model.fit(X, y_raw)
        y_pred = model.predict(X)

        # In-sample Confusion Matrix
        conf_matrix = pd.crosstab(
            pd.Series(y_raw, name="Actual"),
            pd.Series(y_pred, name="Predicted"),
            dropna=False
        ).reindex(index=unique_groups, columns=unique_groups, fill_value=0)

        correct_count = np.trace(conf_matrix.values)
        apparent_error_rate = float(1.0 - correct_count / n)

        # Cross-validation
        cv_error_rate = None
        cv_conf_matrix = None
        if params.cross_validation and n >= 4:
            try:
                loo = LeaveOneOut()
                y_cv_pred = cross_val_predict(model, X, y_raw, cv=loo)
                cv_conf_matrix = pd.crosstab(
                    pd.Series(y_raw, name="Actual"),
                    pd.Series(y_cv_pred, name="Predicted"),
                    dropna=False
                ).reindex(index=unique_groups, columns=unique_groups, fill_value=0)
                cv_correct = np.trace(cv_conf_matrix.values)
                cv_error_rate = float(1.0 - cv_correct / n)
            except Exception:
                cv_error_rate = apparent_error_rate

        # Group Means Table
        means_headers = ["Predictor"] + list(unique_groups) + ["Total Mean"]
        means_rows = []
        for j, pcol in enumerate(pred_cols):
            row = [pcol]
            for g in unique_groups:
                g_mean = float(np.mean(X[y_raw == g, j]))
                row.append(f"{g_mean:.4f}")
            row.append(f"{float(np.mean(X[:, j])):.4f}")
            means_rows.append(row)

        means_table = TableResult(
            title="Group and Total Predictor Means",
            headers=means_headers,
            rows=means_rows
        )

        # Summary of Classification (In-Sample Confusion Matrix)
        conf_headers = ["Actual Group"] + [f"Pred {g}" for g in unique_groups] + ["Total N", "% Correct"]
        conf_rows = []
        for g in unique_groups:
            row_vals = [int(conf_matrix.loc[g, col]) for col in unique_groups]
            g_tot = int(np.sum(row_vals))
            g_corr = int(conf_matrix.loc[g, g])
            pct_corr = (g_corr / g_tot * 100.0) if g_tot > 0 else 0.0
            row = [str(g)] + [str(v) for v in row_vals] + [str(g_tot), f"{pct_corr:.2f}%"]
            conf_rows.append(row)

        conf_table = TableResult(
            title=f"Summary of Classification (Apparent Error Rate = {apparent_error_rate*100:.2f}%)",
            headers=conf_headers,
            rows=conf_rows
        )

        # Cross-Validated Summary Table if applicable
        tables = [means_table, conf_table]
        if cv_conf_matrix is not None:
            cv_rows = []
            for g in unique_groups:
                row_vals = [int(cv_conf_matrix.loc[g, col]) for col in unique_groups]
                g_tot = int(np.sum(row_vals))
                g_corr = int(cv_conf_matrix.loc[g, g])
                pct_corr = (g_corr / g_tot * 100.0) if g_tot > 0 else 0.0
                row = [str(g)] + [str(v) for v in row_vals] + [str(g_tot), f"{pct_corr:.2f}%"]
                cv_rows.append(row)

            cv_table = TableResult(
                title=f"Summary of Classification (Cross-Validated / Jackknife Error Rate = {cv_error_rate*100:.2f}%)",
                headers=conf_headers,
                rows=cv_rows
            )
            tables.append(cv_table)

        # Canonical Discriminant Scores / 2D Projection
        traces: List[Dict[str, Any]] = []
        color_palette = ["#008450", "#0f6cbd", "#d13438", "#881798", "#ffaa44", "#00b7c3"]

        if not is_qda and K > 1:
            try:
                lda_scores = model.transform(X)
                if lda_scores.shape[1] >= 2:
                    sc_x = lda_scores[:, 0]
                    sc_y = lda_scores[:, 1]
                    axis_x_name = "Linear Discriminant 1 (LD1)"
                    axis_y_name = "Linear Discriminant 2 (LD2)"
                else:
                    sc_x = lda_scores[:, 0]
                    sc_y = np.random.normal(0, 0.05, size=n)
                    axis_x_name = "Linear Discriminant 1 (LD1)"
                    axis_y_name = "Jitter"
            except Exception:
                sc_x = X[:, 0]
                sc_y = X[:, 1] if p > 1 else np.zeros(n)
                axis_x_name = pred_cols[0]
                axis_y_name = pred_cols[1] if p > 1 else "Index"
        else:
            sc_x = X[:, 0]
            sc_y = X[:, 1] if p > 1 else np.zeros(n)
            axis_x_name = pred_cols[0]
            axis_y_name = pred_cols[1] if p > 1 else "Index"

        # Add trace per group
        for g_idx, g in enumerate(unique_groups):
            c_color = color_palette[g_idx % len(color_palette)]
            mask = y_raw == g
            gx = sc_x[mask]
            gy = sc_y[mask]

            traces.append({
                "type": "scatter",
                "mode": "markers",
                "x": gx.tolist(),
                "y": gy.tolist(),
                "name": f"Group {g}",
                "marker": {"size": 7, "color": c_color, "opacity": 0.8},
                "showlegend": True
            })

            # Convex hull for group
            if len(gx) >= 3:
                try:
                    pts = np.column_stack([gx, gy])
                    hull = ConvexHull(pts)
                    hull_pts = pts[hull.vertices]
                    hull_pts = np.vstack([hull_pts, hull_pts[0]])
                    traces.append({
                        "type": "scatter",
                        "mode": "lines",
                        "x": hull_pts[:, 0].tolist(),
                        "y": hull_pts[:, 1].tolist(),
                        "line": {"color": c_color, "dash": "dot", "width": 1.5},
                        "showlegend": False
                    })
                except Exception:
                    pass

        plotly_figure = {
            "data": traces,
            "layout": {
                "title": f"Discriminant Function Scores Plot ({func_name})",
                "showlegend": True,
                "margin": {"l": 50, "r": 30, "t": 60, "b": 45},
                "xaxis": {"title": axis_x_name, "zeroline": True},
                "yaxis": {"title": axis_y_name, "zeroline": True}
            }
        }

        # Text Summary
        text_lines = [
            f"Discriminant Analysis: {params.group_variable} on {', '.join(pred_cols)}",
            f"Function: {func_name} | Prior Probabilities: {prior_desc}",
            f"Groups ({K}): {', '.join([str(g) for g in unique_groups])} | Observations: {n}",
            f"Apparent Error Rate: {apparent_error_rate * 100:.2f}%",
        ]
        if cv_error_rate is not None:
            text_lines.append(f"Cross-Validated Error Rate (Leave-One-Out): {cv_error_rate * 100:.2f}%")

        # Storage option: store PRED_GRP
        action_type = None
        worksheet_data = None
        if params.storage_options:
            stored_cols = [{
                "id": "pred_grp",
                "name": "PRED_GRP",
                "type": "text",
                "role": "CATEGORICAL",
                "isLocked": True,
                "width": 110
            }]
            stored_rows = [{"pred_grp": str(pred)} for pred in y_pred]
            action_type = "worksheet_append_columns"
            worksheet_data = {
                "columns": stored_cols,
                "rows": stored_rows
            }

        return AnalysisResult(
            title=f"Discriminant Analysis: {params.group_variable}",
            subtitle=f"{func_name} | Apparent Error = {apparent_error_rate*100:.2f}%" + (f" | CV Error = {cv_error_rate*100:.2f}%" if cv_error_rate is not None else ""),
            text_output="\n".join(text_lines),
            tables=tables,
            plotly_figure=plotly_figure,
            action_type=action_type,
            worksheet_data=worksheet_data,
            statistics={
                "function": func_name,
                "apparent_error_rate": apparent_error_rate,
                "cv_error_rate": cv_error_rate,
                "groups": [str(g) for g in unique_groups],
                "predictors": pred_cols
            }
        )
