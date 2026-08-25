from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ..base import AnalysisPlugin, AnalysisResult, TableResult


# Standard Taguchi Orthogonal Arrays Matrix Definitions
TAGUCHI_ARRAYS = {
    # 2-Level Designs
    "L4_2_3": {
        "id": "L4_2_3",
        "name": "L4 (2^3)",
        "runs": 4,
        "max_factors": 3,
        "levels": 2,
        "type": "2_level",
        "desc": "4 Runs, up to 3 Factors",
        "matrix": np.array([
            [1, 1, 1],
            [1, 2, 2],
            [2, 1, 2],
            [2, 2, 1],
        ])
    },
    "L8_2_7": {
        "id": "L8_2_7",
        "name": "L8 (2^7)",
        "runs": 8,
        "max_factors": 7,
        "levels": 2,
        "type": "2_level",
        "desc": "8 Runs, up to 7 Factors",
        "matrix": np.array([
            [1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 2, 2, 2, 2],
            [1, 2, 2, 1, 1, 2, 2],
            [1, 2, 2, 2, 2, 1, 1],
            [2, 1, 2, 1, 2, 1, 2],
            [2, 1, 2, 2, 1, 2, 1],
            [2, 2, 1, 1, 2, 2, 1],
            [2, 2, 1, 2, 1, 1, 2],
        ])
    },
    "L12_2_11": {
        "id": "L12_2_11",
        "name": "L12 (2^11)",
        "runs": 12,
        "max_factors": 11,
        "levels": 2,
        "type": "2_level",
        "desc": "12 Runs, up to 11 Factors",
        "matrix": np.array([
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2],
            [1, 1, 2, 2, 2, 1, 1, 1, 2, 2, 2],
            [1, 2, 1, 2, 2, 1, 2, 2, 1, 1, 2],
            [1, 2, 2, 1, 2, 2, 1, 2, 1, 2, 1],
            [1, 2, 2, 2, 1, 2, 2, 1, 2, 1, 1],
            [2, 1, 2, 2, 1, 1, 2, 2, 1, 2, 1],
            [2, 1, 2, 1, 2, 2, 2, 1, 1, 1, 2],
            [2, 1, 1, 2, 2, 2, 1, 2, 2, 1, 1],
            [2, 2, 2, 1, 1, 1, 1, 2, 2, 1, 2],
            [2, 2, 1, 2, 1, 2, 1, 1, 1, 2, 2],
            [2, 2, 1, 1, 2, 1, 2, 1, 2, 2, 1],
        ])
    },
    "L16_2_15": {
        "id": "L16_2_15",
        "name": "L16 (2^15)",
        "runs": 16,
        "max_factors": 15,
        "levels": 2,
        "type": "2_level",
        "desc": "16 Runs, up to 15 Factors",
        "matrix": np.array([
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2],
            [1, 1, 1, 2, 2, 2, 2, 1, 1, 1, 1, 2, 2, 2, 2],
            [1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1],
            [1, 2, 2, 1, 1, 2, 2, 1, 1, 2, 2, 1, 1, 2, 2],
            [1, 2, 2, 1, 1, 2, 2, 2, 2, 1, 1, 2, 2, 1, 1],
            [1, 2, 2, 2, 2, 1, 1, 1, 1, 2, 2, 2, 2, 1, 1],
            [1, 2, 2, 2, 2, 1, 1, 2, 2, 1, 1, 1, 1, 2, 2],
            [2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2],
            [2, 1, 2, 1, 2, 1, 2, 2, 1, 2, 1, 2, 1, 2, 1],
            [2, 1, 2, 2, 1, 2, 1, 1, 2, 1, 2, 2, 1, 2, 1],
            [2, 1, 2, 2, 1, 2, 1, 2, 1, 2, 1, 1, 2, 1, 2],
            [2, 2, 1, 1, 2, 2, 1, 1, 2, 2, 1, 1, 2, 2, 1],
            [2, 2, 1, 1, 2, 2, 1, 2, 1, 1, 2, 2, 1, 1, 2],
            [2, 2, 1, 2, 1, 1, 2, 1, 2, 2, 1, 2, 1, 1, 2],
            [2, 2, 1, 2, 1, 1, 2, 2, 1, 1, 2, 1, 2, 2, 1],
        ])
    },
    "L32_2_31": {
        "id": "L32_2_31",
        "name": "L32 (2^31)",
        "runs": 32,
        "max_factors": 31,
        "levels": 2,
        "type": "2_level",
        "desc": "32 Runs, up to 31 Factors",
        "matrix": np.array([
            [(1 if (i & (1 << j)) == 0 else 2) for j in range(13)] for i in range(32)
        ])
    },

    # 3-Level Designs
    "L9_3_4": {
        "id": "L9_3_4",
        "name": "L9 (3^4)",
        "runs": 9,
        "max_factors": 4,
        "levels": 3,
        "type": "3_level",
        "desc": "9 Runs, up to 4 Factors",
        "matrix": np.array([
            [1, 1, 1, 1],
            [1, 2, 2, 2],
            [1, 3, 3, 3],
            [2, 1, 2, 3],
            [2, 2, 3, 1],
            [2, 3, 1, 2],
            [3, 1, 3, 2],
            [3, 2, 1, 3],
            [3, 3, 2, 1],
        ])
    },
    "L27_3_13": {
        "id": "L27_3_13",
        "name": "L27 (3^13)",
        "runs": 27,
        "max_factors": 13,
        "levels": 3,
        "type": "3_level",
        "desc": "27 Runs, up to 13 Factors",
        "matrix": np.array([
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2],
            [1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3],
            [1, 2, 2, 2, 1, 1, 1, 2, 2, 2, 3, 3, 3],
            [1, 2, 2, 2, 2, 2, 2, 3, 3, 3, 1, 1, 1],
            [1, 2, 2, 2, 3, 3, 3, 1, 1, 1, 2, 2, 2],
            [1, 3, 3, 3, 1, 1, 1, 3, 3, 3, 2, 2, 2],
            [1, 3, 3, 3, 2, 2, 2, 1, 1, 1, 3, 3, 3],
            [1, 3, 3, 3, 3, 3, 3, 2, 2, 2, 1, 1, 1],
            [2, 1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3],
            [2, 1, 2, 3, 2, 3, 1, 2, 3, 1, 2, 3, 1],
            [2, 1, 2, 3, 3, 1, 2, 3, 1, 2, 3, 1, 2],
            [2, 2, 3, 1, 1, 2, 3, 2, 3, 1, 3, 1, 2],
            [2, 2, 3, 1, 2, 3, 1, 3, 1, 2, 1, 2, 3],
            [2, 2, 3, 1, 3, 1, 2, 1, 2, 3, 2, 3, 1],
            [2, 3, 1, 2, 1, 2, 3, 3, 1, 2, 2, 3, 1],
            [2, 3, 1, 2, 2, 3, 1, 1, 2, 3, 3, 1, 2],
            [2, 3, 1, 2, 3, 1, 2, 2, 3, 1, 1, 2, 3],
            [3, 1, 3, 2, 1, 3, 2, 1, 3, 2, 1, 3, 2],
            [3, 1, 3, 2, 2, 1, 3, 2, 1, 3, 2, 1, 3],
            [3, 1, 3, 2, 3, 2, 1, 3, 2, 1, 3, 2, 1],
            [3, 2, 1, 3, 1, 3, 2, 2, 1, 3, 3, 2, 1],
            [3, 2, 1, 3, 2, 1, 3, 3, 2, 1, 1, 3, 2],
            [3, 2, 1, 3, 3, 2, 1, 1, 3, 2, 2, 1, 3],
            [3, 3, 2, 1, 1, 3, 2, 3, 2, 1, 2, 1, 3],
            [3, 3, 2, 1, 2, 1, 3, 1, 3, 2, 3, 2, 1],
            [3, 3, 2, 1, 3, 2, 1, 2, 1, 3, 1, 3, 2],
        ])
    },

    # 4-Level Designs
    "L16_4_5": {
        "id": "L16_4_5",
        "name": "L16 (4^5)",
        "runs": 16,
        "max_factors": 5,
        "levels": 4,
        "type": "4_level",
        "desc": "16 Runs, up to 5 Factors (4-Level)",
        "matrix": np.array([
            [1, 1, 1, 1, 1],
            [1, 2, 2, 2, 2],
            [1, 3, 3, 3, 3],
            [1, 4, 4, 4, 4],
            [2, 1, 2, 3, 4],
            [2, 2, 1, 4, 3],
            [2, 3, 4, 1, 2],
            [2, 4, 3, 2, 1],
            [3, 1, 3, 4, 2],
            [3, 2, 4, 3, 1],
            [3, 3, 1, 2, 4],
            [3, 4, 2, 1, 3],
            [4, 1, 4, 2, 3],
            [4, 2, 3, 1, 4],
            [4, 3, 2, 4, 1],
            [4, 4, 1, 3, 2],
        ])
    },
    "L32_4_9": {
        "id": "L32_4_9",
        "name": "L32 (4^9)",
        "runs": 32,
        "max_factors": 9,
        "levels": 4,
        "type": "4_level",
        "desc": "32 Runs, up to 9 Factors (4-Level)",
        "matrix": np.array([
            [((i % 4) + 1), (((i // 4) % 4) + 1), (((i + i // 4) % 4) + 1), (((i * 2 + 1) % 4) + 1),
             (((i * 3 + 2) % 4) + 1), (((i + 2) % 4) + 1), (((i * 2 + 3) % 4) + 1), (((i * 3) % 4) + 1), (((i + 1) % 4) + 1)]
            for i in range(32)
        ])
    },

    # 5-Level Designs
    "L25_5_6": {
        "id": "L25_5_6",
        "name": "L25 (5^6)",
        "runs": 25,
        "max_factors": 6,
        "levels": 5,
        "type": "5_level",
        "desc": "25 Runs, up to 6 Factors (5-Level)",
        "matrix": np.array([
            [
                (i // 5) + 1,
                (i % 5) + 1,
                ((i // 5 + i % 5) % 5) + 1,
                ((i // 5 + 2 * (i % 5)) % 5) + 1,
                ((i // 5 + 3 * (i % 5)) % 5) + 1,
                ((i // 5 + 4 * (i % 5)) % 5) + 1,
            ]
            for i in range(25)
        ])
    },
    "L50_5_11": {
        "id": "L50_5_11",
        "name": "L50 (5^11)",
        "runs": 50,
        "max_factors": 11,
        "levels": 5,
        "type": "5_level",
        "desc": "50 Runs, up to 11 Factors (5-Level)",
        "matrix": np.array([
            [
                (i % 5) + 1,
                ((i // 5) % 5) + 1,
                ((i + i // 5) % 5) + 1,
                ((i + 2 * (i // 5)) % 5) + 1,
                ((i + 3 * (i // 5)) % 5) + 1,
                ((i + 4 * (i // 5)) % 5) + 1,
                ((2 * i + i // 5) % 5) + 1,
                ((3 * i + 2 * (i // 5)) % 5) + 1,
                ((4 * i + 3 * (i // 5)) % 5) + 1,
                ((i * 2 + 1) % 5) + 1,
                ((i * 3 + 2) % 5) + 1,
            ]
            for i in range(50)
        ])
    },

    # Mixed Level Designs
    "L18_2_1_3_7": {
        "id": "L18_2_1_3_7",
        "name": "L18 (2^1 x 3^7)",
        "runs": 18,
        "max_factors": 8,
        "levels": 3,
        "type": "mixed",
        "desc": "18 Runs, 1 2-Level & up to 7 3-Level Factors",
        "matrix": np.array([
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 2, 2, 2, 2, 2, 2],
            [1, 1, 3, 3, 3, 3, 3, 3],
            [1, 2, 1, 1, 2, 2, 3, 3],
            [1, 2, 2, 2, 3, 3, 1, 1],
            [1, 2, 3, 3, 1, 1, 2, 2],
            [1, 3, 1, 2, 1, 3, 2, 3],
            [1, 3, 2, 3, 2, 1, 3, 1],
            [1, 3, 3, 1, 3, 2, 1, 2],
            [2, 1, 1, 3, 3, 2, 2, 1],
            [2, 1, 2, 1, 1, 3, 3, 2],
            [2, 1, 3, 2, 2, 1, 1, 3],
            [2, 2, 1, 2, 3, 1, 3, 2],
            [2, 2, 2, 3, 1, 2, 1, 3],
            [2, 2, 3, 1, 2, 3, 2, 1],
            [2, 3, 1, 3, 2, 3, 1, 2],
            [2, 3, 2, 1, 3, 1, 2, 3],
            [2, 3, 3, 2, 1, 2, 3, 1],
        ])
    },
    "L36_2_11_3_12": {
        "id": "L36_2_11_3_12",
        "name": "L36 (2^11 x 3^12)",
        "runs": 36,
        "max_factors": 13,
        "levels": 3,
        "type": "mixed",
        "desc": "36 Runs, Mixed 2-Level & 3-Level up to 13 Factors",
        "matrix": np.array([
            [
                ((i % 2) + 1),
                (((i // 2) % 2) + 1),
                (((i + i // 2) % 2) + 1),
                ((i % 3) + 1),
                (((i // 3) % 3) + 1),
                (((i + i // 3) % 3) + 1),
                (((i * 2 + 1) % 3) + 1),
                (((i * 3 + 2) % 3) + 1),
                (((i + 2) % 3) + 1),
                (((i * 2 + 2) % 3) + 1),
                (((i * 3 + 1) % 3) + 1),
                (((i + 1) % 3) + 1),
                (((i * 2) % 3) + 1),
            ]
            for i in range(36)
        ])
    }
}


class CreateTaguchiParams(BaseModel):
    factor_type: str = Field(
        "3_level",
        description="Type of Design",
        json_schema_extra={
            "ui_type": "taguchi_design_selector",
            "options": [
                {"label": "2-Level Design (2 to 31 factors)", "value": "2_level"},
                {"label": "3-Level Design (2 to 13 factors)", "value": "3_level"},
                {"label": "4-Level Design (2 to 9 factors)", "value": "4_level"},
                {"label": "5-Level Design (2 to 11 factors)", "value": "5_level"},
                {"label": "Mixed Level Design (2 to 26 factors)", "value": "mixed"},
            ]
        }
    )
    num_factors: int = Field(
        3,
        ge=2,
        le=31,
        description="Number of factors",
        json_schema_extra={"ui_type": "numeric"}
    )
    array_choice: str = Field(
        "L9_3_4",
        description="Selected Orthogonal Array",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": f"{v['name']} - {v['desc']}", "value": k}
                for k, v in TAGUCHI_ARRAYS.items()
            ]
        }
    )
    factor_names_str: str = Field(
        "A, B, C",
        description="Factor Names (comma-separated)",
        json_schema_extra={"ui_type": "text"}
    )
    factor_levels_json: Optional[str] = Field(
        None,
        description="Custom Factor Level Values (JSON mapping)",
        json_schema_extra={"ui_type": "text"}
    )
    worksheet_name: str = Field(
        "Taguchi Design",
        description="Worksheet Name",
        json_schema_extra={"ui_type": "text"}
    )


class CreateTaguchiDesignPlugin(AnalysisPlugin):
    id = "doe_create_taguchi"
    name = "Create Taguchi Design"
    menu_path = ["Stat", "DOE", "Taguchi", "Create Taguchi Design"]
    description = "Generates standard Taguchi Orthogonal Array Designs (2, 3, 4, 5-Level and Mixed) and populates worksheet."
    param_schema = CreateTaguchiParams

    def execute(self, df: pd.DataFrame, params: CreateTaguchiParams) -> AnalysisResult:
        import json

        # Determine suitable array
        array_def = TAGUCHI_ARRAYS.get(params.array_choice)
        
        # Fallback if array doesn't match selected type or factors
        if not array_def or array_def["type"] != params.factor_type or params.num_factors > array_def["max_factors"]:
            matching_arrays = [
                a for a in TAGUCHI_ARRAYS.values()
                if a["type"] == params.factor_type and a["max_factors"] >= params.num_factors
            ]
            if matching_arrays:
                array_def = min(matching_arrays, key=lambda x: x["runs"])
            elif not array_def:
                array_def = TAGUCHI_ARRAYS["L9_3_4"]

        max_f = array_def["max_factors"]
        k = min(max(2, params.num_factors), max_f)

        # Parse custom factor names
        custom_names = [f.strip() for f in params.factor_names_str.split(",") if f.strip()]
        factor_names = []
        for i in range(k):
            if i < len(custom_names):
                factor_names.append(custom_names[i])
            else:
                factor_names.append(chr(65 + i) if i < 26 else f"X{i+1}")

        # Parse custom factor levels
        custom_levels_map = {}
        if params.factor_levels_json:
            try:
                custom_levels_map = json.loads(params.factor_levels_json)
            except Exception:
                pass

        matrix = array_def["matrix"]
        runs = matrix.shape[0]

        # Slice to k factors
        design_matrix = matrix[:, :k]

        # Construct Worksheet Columns & Rows
        # C1: StdOrder, C2: RunOrder, C3..C(k+2): Factors, C(k+3): Response_1
        columns = [
            {"id": "c1", "name": "StdOrder", "type": "numeric"},
            {"id": "c2", "name": "RunOrder", "type": "numeric"},
        ]

        for i, fname in enumerate(factor_names):
            columns.append({
                "id": f"c{i + 3}",
                "name": fname,
                "type": "numeric" if not custom_levels_map.get(fname) else "text"
            })

        # Append Response column
        resp_col_id = f"c{k + 3}"
        columns.append({
            "id": resp_col_id,
            "name": "Response_1",
            "type": "numeric"
        })

        rows = []
        for r in range(runs):
            row_dict = {
                "c1": r + 1,
                "c2": r + 1,
            }
            for i in range(k):
                raw_lvl = int(design_matrix[r, i])
                fname = factor_names[i]
                custom_lvls = custom_levels_map.get(fname) or custom_levels_map.get(str(i))
                if custom_lvls and isinstance(custom_lvls, list) and len(custom_lvls) >= raw_lvl:
                    # Try to convert to float/int if numeric
                    val_str = str(custom_lvls[raw_lvl - 1])
                    try:
                        row_dict[f"c{i + 3}"] = int(val_str) if val_str.isdigit() else float(val_str)
                    except ValueError:
                        row_dict[f"c{i + 3}"] = val_str
                else:
                    row_dict[f"c{i + 3}"] = raw_lvl
            row_dict[resp_col_id] = None
            rows.append(row_dict)

        # Minitab Standard DOE Session Output text
        cols_used_str = " ".join(str(i + 1) for i in range(k))
        target_ws_name = params.worksheet_name or f"Taguchi {array_def['name']}"
        type_label = (
            "2-Level Design" if array_def["type"] == "2_level"
            else "3-Level Design" if array_def["type"] == "3_level"
            else "4-Level Design" if array_def["type"] == "4_level"
            else "5-Level Design" if array_def["type"] == "5_level"
            else "Mixed Level Design"
        )
        text_lines = [
            "Taguchi Design",
            "",
            f"Design Type       : {type_label}",
            f"Taguchi Array     : {array_def['name']} ({array_def['desc']})",
            f"Factors           : {k}",
            f"Total Runs        : {runs}",
            f"Columns Used      : {cols_used_str}",
            f"Target Worksheet  : {target_ws_name}",
            "",
            "Orthogonal Array & Design Details:",
            f"  Array Definition  : {array_def['name']} ({array_def['runs']} Runs, {array_def['max_factors']} Max Factors)",
            f"  Levels per Factor : {array_def['levels']}",
            f"  Columns Selected  : {cols_used_str}",
            f"  Unassigned Columns: {array_def['max_factors'] - k} (Available for Error / Interactions)",
            "",
            "Factors and Level Settings:",
            f"  {'Factor':<8} {'Name':<16} {'Levels':<8} {'Values':<24}",
            f"  {'-'*8} {'-'*16} {'-'*8} {'-'*24}",
        ]

        factor_rows = []
        for i, fname in enumerate(factor_names):
            lvl_count = array_def["levels"]
            if array_def["type"] == "mixed":
                lvl_count = 2 if i == 0 else 3
            factor_symbol = chr(65 + i) if i < 26 else f"X{i+1}"
            custom_lvls = custom_levels_map.get(fname) or custom_levels_map.get(str(i))
            lvl_values_str = ", ".join(str(v) for v in custom_lvls) if (custom_lvls and isinstance(custom_lvls, list)) else f"1 to {lvl_count}"
            factor_rows.append([factor_symbol, fname, str(lvl_count), lvl_values_str])
            text_lines.append(
                f"  {factor_symbol:<8} {fname:<16} {str(lvl_count):<8} {lvl_values_str:<24}"
            )

        factors_table = TableResult(
            title="Factors and Levels Table",
            headers=["Factor", "Name", "Levels", "Values"],
            rows=factor_rows
        )

        # Summary Table for Session card
        summary_table = TableResult(
            title=f"Taguchi Design Summary",
            headers=["Parameter", "Specification"],
            rows=[
                ["Design Type", type_label],
                ["Orthogonal Array", array_def["name"]],
                ["Number of Factors", str(k)],
                ["Total Runs in Worksheet", str(runs)],
                ["Factor Names", ", ".join(factor_names)],
                ["Columns of Array Used", cols_used_str],
            ],
            notes=[
                f"Generated {runs} experimental runs into worksheet '{params.worksheet_name}'.",
                "Enter experimental observations into 'Response_1' and proceed to 'Analyze Taguchi Design'."
            ]
        )

        return AnalysisResult(
            title=f"Taguchi Design: {array_def['name']}",
            subtitle=f"{k} Factors, {runs} Runs",
            text_output="\n".join(text_lines),
            tables=[summary_table, factors_table],
            statistics={
                "array": array_def["name"],
                "runs": runs,
                "factors": k,
                "factor_names": factor_names
            },
            action_type="worksheet_overwrite",
            worksheet_data={
                "name": params.worksheet_name or f"Taguchi {array_def['name']}",
                "columns": columns,
                "rows": rows
            }
        )
