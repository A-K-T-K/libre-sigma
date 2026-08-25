"""
Lag Plugin for OpenMinitab Time Series.
Calculates backward lags (positive k) or forward leads (negative k) and appends the shifted series directly into the active worksheet.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


class LagParams(BaseModel):
    variable: str = Field(
        ...,
        description="Series / Variable",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    lag_length: int = Field(
        1,
        ge=-100,
        le=100,
        description="Lag Length (Positive for Lag, Negative for Lead)"
    )
    store_column_name: str = Field(
        "Lag_1",
        description="Store Lag in (Column Name)"
    )


class LagPlugin(AnalysisPlugin):
    id = "ts_lag"
    name = "Lag"
    menu_path = ["Stat", "Time Series", "Lag"]
    description = "Shifts a time series backward by k periods (Lag) or forward by k periods (Lead) and writes into the worksheet."
    param_schema = LagParams

    def execute(self, df: pd.DataFrame, params: LagParams) -> AnalysisResult:
        var_name = params.variable
        if var_name not in df.columns:
            raise ValueError(f"Column '{var_name}' not found in active worksheet.")

        raw_series = df[var_name]
        n = len(raw_series)
        k = params.lag_length

        if abs(k) >= n:
            raise ValueError(f"Lag length (|{k}|) cannot be greater than or equal to sample size ({n}).")

        # Shift series (in pandas, shift(1) means lag 1; shift(-1) means lead 1)
        shifted_series = raw_series.shift(periods=k)

        col_name = params.store_column_name.strip() or (f"Lag_{var_name}_{k}" if k > 0 else f"Lead_{var_name}_{abs(k)}")
        col_id = f"lag_{var_name.lower()}_{k}"

        # Clean numeric summary if possible
        num_shifted = pd.to_numeric(shifted_series, errors="coerce").dropna()
        mean_v = float(np.mean(num_shifted)) if len(num_shifted) > 0 else None
        stdev_v = float(np.std(num_shifted, ddof=1)) if len(num_shifted) > 1 else None

        table = TableResult(
            title=f"Lagged Series Summary ({col_name})",
            headers=["Variable", "Shift (k)", "Type", "Non-missing N", "Mean", "StDev"],
            rows=[
                [
                    var_name,
                    k,
                    "Lag (Backward)" if k > 0 else "Lead (Forward)" if k < 0 else "No shift",
                    len(num_shifted),
                    round(mean_v, 4) if mean_v is not None else "N/A",
                    round(stdev_v, 4) if stdev_v is not None else "N/A"
                ]
            ]
        )

        text_lines = [
            f"Lag for {var_name}",
            f"Shift: {k} ({'Backward Lag' if k > 0 else 'Forward Lead'})",
            f"Output Column: {col_name}",
            "",
            f"Appended column '{col_name}' directly into active worksheet."
        ]

        # Prepare storage
        is_num = pd.to_numeric(raw_series, errors="coerce").notna().sum() > (len(raw_series) * 0.5)
        col_type = "numeric" if is_num else "text"

        storage_cols = [{"id": col_id, "name": col_name, "type": col_type}]
        rows_data = []
        for v in shifted_series:
            rows_data.append({col_id: None if pd.isna(v) else v})

        return AnalysisResult(
            title="Lag",
            subtitle=f"{'Lag' if k >= 0 else 'Lead'} {k} of {var_name}",
            text_output="\n".join(text_lines),
            tables=[table],
            action_type="worksheet_append_columns",
            worksheet_data={"columns": storage_cols, "rows": rows_data}
        )
