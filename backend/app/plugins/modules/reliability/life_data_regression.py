"""
Regression with Life Data (Accelerated Life Testing / Parametric Survival) Plugin for OpenMinitab.
Fits parametric Accelerated Failure Time (AFT) models to lifetime data with covariates and censoring.
Generates survival regression coefficients table, log-likelihood, and Life-Stress relationship plots.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats
from lifelines import WeibullAFTFitter, LogNormalAFTFitter
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class LifeDataRegressionParams(BaseModel):
    response_time: str = Field(
        ...,
        description="Response / Failure Time Column",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    censor_col: Optional[str] = Field(
        None,
        description="Censoring Indicator (1 = Failure, 0 = Censored)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    predictors: List[str] = Field(
        ...,
        description="Predictors / Accelerating Stresses",
        json_schema_extra={"ui_type": "column_multi_picker", "data_type": "numeric"}
    )
    distribution: str = Field(
        "weibull",
        description="Assumed Distribution",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Weibull AFT Model", "value": "weibull"},
                {"label": "Lognormal AFT Model", "value": "lognormal"}
            ]
        }
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%)"
    )


class LifeDataRegressionPlugin(AnalysisPlugin):
    id = "reliability_life_data_regression"
    name = "Regression with Life Data"
    menu_path = ["Stat", "Reliability/Survival", "Regression with Life Data"]
    description = "Fits parametric Accelerated Failure Time models to analyze the relationship between lifetime and accelerating stresses/covariates."
    param_schema = LifeDataRegressionParams

    def execute(self, df: pd.DataFrame, params: LifeDataRegressionParams) -> AnalysisResult:
        time_col = params.response_time
        preds = params.predictors

        if not preds:
            raise ValueError("Select at least one predictor or stress variable for survival regression.")

        all_cols = [time_col] + preds
        has_censor = bool(params.censor_col and params.censor_col in df.columns)
        if has_censor and params.censor_col:
            all_cols.append(params.censor_col)

        sub_df = df[all_cols].dropna().copy()
        for c in [time_col] + preds:
            sub_df[c] = pd.to_numeric(sub_df[c], errors="coerce")
        sub_df = sub_df.dropna().reset_index(drop=True)

        # Ensure positive lifetimes
        sub_df = sub_df[sub_df[time_col] > 0].reset_index(drop=True)
        n_total = len(sub_df)
        if n_total < 5:
            raise ValueError("Regression with Life Data requires at least 5 valid observations.")

        if not has_censor or not params.censor_col:
            sub_df["_event"] = 1
            event_col = "_event"
        else:
            event_col = params.censor_col
            sub_df[event_col] = pd.to_numeric(sub_df[event_col], errors="coerce").fillna(1).astype(int)


        alpha = 1.0 - params.confidence_level / 100.0

        if params.distribution == "weibull":
            fitter = WeibullAFTFitter(alpha=alpha)
        else:
            fitter = LogNormalAFTFitter(alpha=alpha)

        # Fit AFT model
        fit_df = sub_df[[time_col, event_col] + preds]
        fitter.fit(fit_df, duration_col=time_col, event_col=event_col)

        summary_df = fitter.summary
        log_lik = float(fitter.log_likelihood_)

        coef_rows = []
        for idx_row, s_row in summary_df.iterrows():
            param_name = str(idx_row[1] if isinstance(idx_row, tuple) else idx_row)
            model_part = str(idx_row[0] if isinstance(idx_row, tuple) else "lambda")
            coef_val = float(s_row.get("coef", 0.0))
            se_val = float(s_row.get("se(coef)", 0.0))
            z_val = float(s_row.get("z", 0.0))
            p_val = float(s_row.get("p", 0.0))
            low_ci = float(s_row.get(f"coef lower {params.confidence_level:.0f}%", coef_val - 1.96 * se_val))
            up_ci = float(s_row.get(f"coef upper {params.confidence_level:.0f}%", coef_val + 1.96 * se_val))

            coef_rows.append([
                f"{model_part}_{param_name}",
                round(coef_val, 4),
                round(se_val, 4),
                round(z_val, 2),
                round(p_val, 5),
                round(low_ci, 4),
                round(up_ci, 4)
            ])

        # Life-Stress Plot (Primary predictor vs Lifetime)
        primary_pred = preds[0]
        x_pts = sub_df[primary_pred].to_numpy(dtype=float)
        y_pts = sub_df[time_col].to_numpy(dtype=float)
        events = sub_df[event_col].to_numpy(dtype=int)

        traces = [
            {
                "x": x_pts[events == 1].tolist(),
                "y": y_pts[events == 1].tolist(),
                "mode": "markers",
                "name": "Failures",
                "marker": {"color": "#d13438", "symbol": "circle", "size": 7}
            },
            {
                "x": x_pts[events == 0].tolist(),
                "y": y_pts[events == 0].tolist(),
                "mode": "markers",
                "name": "Censored",
                "marker": {"color": "#005a9e", "symbol": "circle-open", "size": 7}
            }
        ]

        # Predicted median lifetime curve vs primary predictor
        x_grid = np.linspace(min(x_pts), max(x_pts), 50)
        synth_dict = {primary_pred: x_grid}
        for p in preds[1:]:
            synth_dict[p] = np.full(len(x_grid), sub_df[p].mean())
        synth_df = pd.DataFrame(synth_dict)

        try:
            pred_median = fitter.predict_median(synth_df).to_numpy()
            traces.append({
                "x": x_grid.tolist(),
                "y": pred_median.tolist(),
                "mode": "lines",
                "name": "Predicted Median Life",
                "line": {"color": "#008450", "width": 2}
            })
        except Exception:
            pass

        layout = {
            "title": {"text": f"<b>Life-Stress Relationship: {time_col} vs {primary_pred}</b><br><span style='font-size:11px;color:#605e5c'>Model: {params.distribution.capitalize()} AFT (Log-Likelihood = {log_lik:.2f})</span>", "font": {"size": 13, "color": "#201f1e"}},
            "xaxis": {"title": primary_pred, "showgrid": True, "gridcolor": "#f3f2f1"},
            "yaxis": {"title": f"Lifetime ({time_col})", "type": "log", "showgrid": True, "gridcolor": "#f3f2f1"},
            "legend": {"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            "plot_bgcolor": "#ffffff",
            "paper_bgcolor": "#ffffff",
            "margin": {"l": 60, "r": 30, "t": 60, "b": 55}
        }

        table = TableResult(
            title=f"Regression with Life Data: {time_col}",
            headers=["Parameter", "Coef", "SE Coef", "Z", "P-Value", f"Lower {params.confidence_level:.0f}% CI", f"Upper {params.confidence_level:.0f}% CI"],
            rows=coef_rows
        )

        model_summary_table = TableResult(
            title="Model Summary",
            headers=["Criterion", "Value"],
            rows=[
                ["Distribution", params.distribution.capitalize()],
                ["Log-Likelihood", f"{log_lik:.4f}"],
                ["AIC", f"{-2 * log_lik + 2 * len(coef_rows):.2f}"],
                ["Total Observations", str(n_total)],
                ["Failures / Censored", f"{int(np.sum(events == 1))} / {int(np.sum(events == 0))}"]
            ]
        )

        text_lines = [
            f"Regression with Life Data: {time_col}",
            f"Distribution: {params.distribution.capitalize()}",
            f"Log-Likelihood: {log_lik:.4f}",
            "",
            f"  {'Parameter':<22} {'Coef':>10} {'SE Coef':>10} {'Z':>8} {'P-Value':>10}",
            f"  {'-'*22} {'-'*10} {'-'*10} {'-'*8} {'-'*10}",
        ]
        for r in coef_rows:
            text_lines.append(f"  {r[0]:<22} {r[1]:>10.4f} {r[2]:>10.4f} {r[3]:>8.2f} {r[4]:>10.5f}")

        return AnalysisResult(
            title="Regression with Life Data",
            subtitle=f"{time_col} ({params.distribution.capitalize()} AFT)",
            text_output="\n".join(text_lines),
            tables=[table, model_summary_table],
            plotly_figure={"data": traces, "layout": layout}
        )
