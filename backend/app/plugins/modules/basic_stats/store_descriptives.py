import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.plugins.base import AnalysisPlugin, AnalysisResult, TableResult


class StoreDescriptivesParams(BaseModel):
    variables: List[str] = Field(
        ...,
        description="Variables to compute statistics for",
        json_schema_extra={"ui_type": "column_multi_picker", "data_type": "numeric"}
    )
    store_mean: bool = Field(True, description="Store Mean", json_schema_extra={"ui_type": "checkbox"})
    store_stdev: bool = Field(True, description="Store Standard Deviation", json_schema_extra={"ui_type": "checkbox"})
    store_variance: bool = Field(False, description="Store Variance", json_schema_extra={"ui_type": "checkbox"})
    store_median: bool = Field(True, description="Store Median", json_schema_extra={"ui_type": "checkbox"})
    store_min: bool = Field(False, description="Store Minimum", json_schema_extra={"ui_type": "checkbox"})
    store_max: bool = Field(False, description="Store Maximum", json_schema_extra={"ui_type": "checkbox"})
    store_n: bool = Field(True, description="Store Non-missing Sample Size N", json_schema_extra={"ui_type": "checkbox"})


class StoreDescriptivesPlugin(AnalysisPlugin):
    id = "store_descriptives"
    name = "Store Descriptive Statistics"
    menu_path = ["Stat", "Basic Statistics", "Store Descriptive Statistics"]
    description = "Calculates descriptive statistics and appends new storage columns directly into the active worksheet."
    param_schema = StoreDescriptivesParams

    def execute(self, df: pd.DataFrame, params: StoreDescriptivesParams) -> AnalysisResult:
        if not params.variables:
            raise ValueError("Select at least one numeric variable.")

        stat_types = []
        if params.store_mean: stat_types.append("Mean")
        if params.store_stdev: stat_types.append("StDev")
        if params.store_variance: stat_types.append("Variance")
        if params.store_median: stat_types.append("Median")
        if params.store_min: stat_types.append("Min")
        if params.store_max: stat_types.append("Max")
        if params.store_n: stat_types.append("N")

        if not stat_types:
            raise ValueError("Check at least one statistic to store.")

        new_columns = []
        new_rows_data = []

        summary_rows = []
        headers = ["Variable"] + stat_types

        # Compute stats for each variable
        var_stats: Dict[str, Dict[str, Any]] = {}
        for var_name in params.variables:
            if var_name not in df.columns:
                continue
            series = pd.to_numeric(df[var_name], errors="coerce").dropna().to_numpy(dtype=float)
            n = len(series)
            if n == 0:
                continue

            vals: Dict[str, Any] = {}
            if params.store_mean: vals["Mean"] = round(float(np.mean(series)), 4)
            if params.store_stdev: vals["StDev"] = round(float(np.std(series, ddof=1)) if n > 1 else 0.0, 4)
            if params.store_variance: vals["Variance"] = round(float(np.var(series, ddof=1)) if n > 1 else 0.0, 4)
            if params.store_median: vals["Median"] = round(float(np.median(series)), 4)
            if params.store_min: vals["Min"] = round(float(np.min(series)), 4)
            if params.store_max: vals["Max"] = round(float(np.max(series)), 4)
            if params.store_n: vals["N"] = n

            var_stats[var_name] = vals
            summary_rows.append([var_name] + [vals.get(st, "") for st in stat_types])

        # Prepare new columns for worksheet storage
        for st in stat_types:
            col_name = f"Stored_{st}"
            col_id = f"col_{st.lower()}"
            new_columns.append({"id": col_id, "name": col_name, "type": "numeric"})

        for idx, var_name in enumerate(var_stats.keys()):
            row_dict = {}
            for st in stat_types:
                col_id = f"col_{st.lower()}"
                row_dict[col_id] = var_stats[var_name].get(st)
            new_rows_data.append(row_dict)

        text_lines = [
            "Store Descriptive Statistics",
            "",
            f"Stored statistics for {len(var_stats)} variable(s) into worksheet columns: " + ", ".join([f"Stored_{st}" for st in stat_types]),
            "",
            f"  {'Variable':<15} " + "".join(f"{st:>12}" for st in stat_types),
            f"  {'-'*15} " + "".join(f"{'-'*12}" for _ in stat_types),
        ]
        for r in summary_rows:
            text_lines.append(f"  {r[0]:<15} " + "".join(f"{str(v):>12}" for v in r[1:]))

        return AnalysisResult(
            title="Store Descriptive Statistics",
            subtitle="Columns Appended to Worksheet",
            text_output="\n".join(text_lines),
            tables=[TableResult(title="Stored Descriptive Statistics", headers=headers, rows=summary_rows)],
            action_type="worksheet_append_columns",
            worksheet_data={
                "columns": new_columns,
                "rows": new_rows_data
            }
        )
