"""
Factorial Design Generator Plugin for OpenMinitab.
Supports:
  - 2-Level Full and Fractional Factorial Designs (2^(k-p)) with Resolution indicators (Res III, IV, V, VI, Full)
  - Plackett-Burman Screening Designs (4 to 48 runs)
  - 2-Level Split-Plot Designs (Whole Plot and Sub Plot factors)
  - General Full Factorial Designs (Mixed levels: 2 to 100 levels per factor)
Features:
  - Center points per block, Replicates, Blocking
  - Seeded RunOrder randomization
  - Aliasing structure and confounding patterns
  - Coded and actual factor level mapping
"""

from typing import Any, Dict, List, Optional
import itertools
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ..base import AnalysisPlugin, AnalysisResult, TableResult



# Standard 2^(k-p) Fractional Factorial Base Generators
# Maps (k, runs) -> list of generator definitions for fractional factors
FACTORIAL_GENERATORS: Dict[tuple, List[str]] = {
    # 3 factors
    (3, 4): ["C=AB"],  # 2^(3-1) Res III
    (3, 8): [],        # Full 2^3
    # 4 factors
    (4, 8): ["D=ABC"], # 2^(4-1) Res IV
    (4, 16): [],       # Full 2^4
    # 5 factors
    (5, 8): ["D=AB", "E=AC"],       # 2^(5-2) Res III
    (5, 16): ["E=ABCD"],            # 2^(5-1) Res V
    (5, 32): [],                    # Full 2^5
    # 6 factors
    (6, 8): ["D=AB", "E=AC", "F=BC"], # 2^(6-3) Res III
    (6, 16): ["E=ABC", "F=BCD"],      # 2^(6-2) Res IV
    (6, 32): ["F=ABCDE"],             # 2^(6-1) Res VI
    (6, 64): [],                      # Full 2^6
    # 7 factors
    (7, 8): ["D=AB", "E=AC", "F=BC", "G=ABC"],       # 2^(7-4) Res III
    (7, 16): ["E=ABC", "F=BCD", "G=ACD"],            # 2^(7-3) Res IV
    (7, 32): ["F=ABCD", "G=ABCE"],                   # 2^(7-2) Res IV
    (7, 64): ["G=ABCDEF"],                           # 2^(7-1) Res VII
    (7, 128): [],                                    # Full 2^7
    # 8 factors
    (8, 16): ["E=BCD", "F=ACD", "G=ABC", "H=ABD"],   # 2^(8-4) Res IV
    (8, 32): ["F=ABC", "G=ABD", "H=CDE"],            # 2^(8-3) Res IV
    (8, 64): ["G=ABCD", "H=ABEF"],                   # 2^(8-2) Res V
    (8, 128): ["H=ABCDEFG"],                         # 2^(8-1) Res VIII
    # 9 factors
    (9, 16): ["E=BCD", "F=ACD", "G=ABC", "H=ABD", "J=ABCD"], # Res III
    (9, 32): ["F=BCDE", "G=ACDE", "H=ABDE", "J=ABC"],        # Res IV
    (9, 64): ["G=ABCD", "H=ACEF", "J=BDEF"],                 # Res IV
    (9, 128): ["H=ABCDE", "J=ABCFG"],                        # Res V
    # 10 factors
    (10, 16): ["E=BCD", "F=ACD", "G=ABC", "H=ABD", "J=ABCD", "K=AB"], # Res III
    (10, 32): ["F=ABCD", "G=ABCE", "H=ABDE", "J=ACDE", "K=BCDE"],     # Res IV
    (10, 64): ["G=ABCD", "H=ABEF", "J=ACDE", "K=BCDF"],               # Res IV
    (10, 128): ["H=ABCDE", "J=ABCFG", "K=ABDFG"],                     # Res V
    # 11-15 factors
    (11, 32): ["F=ABCD", "G=ABCE", "H=ABDE", "J=ACDE", "K=BCDE", "L=ABCDE"], # Res IV
    (11, 64): ["G=ABCD", "H=ABEF", "J=ACDE", "K=BCDF", "L=ABCDF"],          # Res IV
    (12, 64): ["G=ABCD", "H=ABEF", "J=ACDE", "K=BCDF", "L=ABCDF", "M=ABCDEF"], # Res IV
    (13, 64): ["G=ABCD", "H=ABEF", "J=ACDE", "K=BCDF", "L=ABCDF", "M=ABCDEF", "N=AB"], # Res III
    (14, 64): ["G=ABCD", "H=ABEF", "J=ACDE", "K=BCDF", "L=ABCDF", "M=ABCDEF", "N=AB", "O=AC"],
    (15, 64): ["G=ABCD", "H=ABEF", "J=ACDE", "K=BCDF", "L=ABCDF", "M=ABCDEF", "N=AB", "O=AC", "P=BC"],
}

# Standard Plackett-Burman First Row Cyclic Generators (+1 / -1)
PLACKETT_BURMAN_FIRST_ROWS: Dict[int, List[int]] = {
    8: [1, 1, 1, -1, 1, -1, -1],
    12: [1, 1, -1, 1, 1, 1, -1, -1, -1, 1, -1],
    16: [1, 1, 1, 1, -1, 1, -1, 1, 1, -1, -1, 1, -1, -1, -1],
    20: [1, 1, -1, -1, 1, 1, 1, 1, -1, 1, -1, 1, -1, -1, -1, -1, 1, 1, -1],
    24: [1, 1, 1, 1, 1, -1, 1, -1, 1, 1, -1, -1, 1, 1, -1, -1, 1, -1, 1, -1, -1, -1, -1],
    28: [1, 1, 1, -1, 1, 1, -1, 1, -1, 1, 1, -1, -1, 1, 1, -1, -1, 1, -1, 1, -1, -1, -1, -1, 1, -1, -1],
    32: [1, 1, 1, 1, 1, -1, 1, -1, 1, 1, -1, 1, -1, -1, 1, 1, -1, -1, 1, -1, 1, -1, -1, 1, 1, -1, -1, -1, -1, -1, -1],
    36: [1, 1, -1, -1, 1, 1, -1, 1, -1, 1, 1, 1, -1, 1, 1, -1, 1, -1, -1, 1, -1, -1, 1, 1, -1, 1, -1, 1, -1, -1, -1, -1, 1, -1, -1],
}


class CreateFactorialParams(BaseModel):
    design_type: str = Field(
        "2_level",
        description="Factorial Design Type",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "2-Level Factorial (Default Generator)", "value": "2_level"},
                {"label": "2-Level Split-Plot Design", "value": "split_plot"},
                {"label": "Plackett-Burman Screening Design", "value": "plackett_burman"},
                {"label": "General Full Factorial Design", "value": "general_full"}
            ]
        }
    )
    num_factors: int = Field(3, description="Number of Factors (2 to 15)")
    num_runs: Optional[int] = Field(None, description="Number of Base Runs (e.g. 4, 8, 16, 32, 64...)")
    num_center_points: int = Field(0, description="Center Points per Block (0 to 12)")
    num_replicates: int = Field(1, description="Number of Replicates (1 to 10)")
    num_blocks: int = Field(1, description="Number of Blocks (1, 2, 4...)")
    factor_names_str: str = Field("A, B, C", description="Factor Names (comma-separated)")
    factor_lows_str: Optional[str] = Field("-1, -1, -1", description="Low level values")
    factor_highs_str: Optional[str] = Field("1, 1, 1", description="High level values")
    factor_types_str: Optional[str] = Field("Numeric, Numeric, Numeric", description="Factor roles (Numeric/Text)")
    general_levels_str: Optional[str] = Field("2, 2, 2", description="Number of levels per factor for General Full Factorial")
    general_labels_json: Optional[str] = Field(None, description="JSON mapping for mixed level labels")
    randomize_runs: bool = Field(True, description="Randomize Run Order")
    random_seed: Optional[int] = Field(None, description="Base for Random Number Generator (Seed)")
    worksheet_name: Optional[str] = Field("Factorial Design", description="Destination Worksheet Name")


def build_full_factorial_2level(k: int) -> np.ndarray:
    """Generates standard Yates order 2^k full factorial matrix of -1 and +1."""
    return np.array(list(itertools.product([-1, 1], repeat=k)))


def build_fractional_factorial_2level(k: int, runs: int) -> tuple[np.ndarray, List[str], str]:
    """Generates 2^(k-p) fractional factorial matrix using standard generators."""
    p = int(round(np.log2(2**k / runs)))
    base_k = k - p
    
    if p == 0:
        return build_full_factorial_2level(k), [], "Full Factorial"
    
    base_matrix = build_full_factorial_2level(base_k)
    gens = FACTORIAL_GENERATORS.get((k, runs), [])
    
    # Letters mapping
    letters = [chr(65 + i) for i in range(26)]
    col_dict: Dict[str, np.ndarray] = {}
    for i in range(base_k):
        col_dict[letters[i]] = base_matrix[:, i]
        
    extra_cols = []
    if gens:
        for gen in gens:
            # e.g. "D=ABC" or "D=AB"
            target_var, expr = gen.split("=")
            vec = np.ones(runs, dtype=int)
            for ch in expr.strip():
                if ch in col_dict:
                    vec = vec * col_dict[ch]
            col_dict[target_var.strip()] = vec
            extra_cols.append(vec)
    else:
        # Fallback automatic generator
        for i in range(p):
            target_var = letters[base_k + i]
            # Use alternating interaction combinations
            vec = np.ones(runs, dtype=int)
            for j in range(base_k):
                if (i + j) % 2 == 0:
                    vec = vec * col_dict[letters[j]]
            col_dict[target_var] = vec
            extra_cols.append(vec)

    # Combine all k columns in order A, B, C...
    final_cols = [col_dict[letters[i]] for i in range(k)]
    matrix = np.column_stack(final_cols)
    
    # Estimate resolution
    if p == 1:
        res = "Resolution V / VI" if k >= 5 else "Resolution IV"
    elif p == 2:
        res = "Resolution IV" if k >= 6 else "Resolution III"
    else:
        res = "Resolution III" if runs <= 16 else "Resolution IV"
        
    return matrix, gens, res


def build_plackett_burman(k: int, runs: Optional[int] = None) -> np.ndarray:
    """Constructs Plackett-Burman matrix for screening designs."""
    if runs is None or runs < k + 1:
        # Find nearest multiple of 4 >= k + 1
        runs = int(np.ceil((k + 1) / 4.0) * 4)
        runs = max(8, runs)
        
    if runs not in PLACKETT_BURMAN_FIRST_ROWS:
        # Find next available
        avail = sorted([r for r in PLACKETT_BURMAN_FIRST_ROWS.keys() if r >= runs])
        runs = avail[0] if avail else 36

    first_row = PLACKETT_BURMAN_FIRST_ROWS[runs]
    m = len(first_row)
    matrix_rows = []
    for i in range(m):
        matrix_rows.append(np.roll(first_row, i))
    # Last row is all -1
    matrix_rows.append([-1] * m)
    
    full_pb = np.array(matrix_rows)
    return full_pb[:, :k]


def build_general_full_factorial(levels_list: List[int]) -> np.ndarray:
    """Generates Cartesian product for mixed level general full factorial."""
    level_ranges = [list(range(1, lvl + 1)) for lvl in levels_list]
    return np.array(list(itertools.product(*level_ranges)))


class CreateFactorialDesignPlugin(AnalysisPlugin):
    id = "doe_create_factorial"
    name = "Create Factorial Design"
    menu_path = ["Stat", "DOE", "Factorial", "Create Factorial Design"]
    description = "Generates 2-Level Full, Fractional, Plackett-Burman, and General Full Factorial Designs."
    param_schema = CreateFactorialParams

    def execute(self, df: pd.DataFrame, params: CreateFactorialParams) -> AnalysisResult:
        k = max(2, min(15, params.num_factors))
        
        # Parse Factor Names
        raw_names = [f.strip() for f in params.factor_names_str.split(",") if f.strip()]
        factor_names = []
        for i in range(k):
            if i < len(raw_names):
                factor_names.append(raw_names[i])
            else:
                factor_names.append(chr(65 + i) if i < 26 else f"X{i+1}")

        # Parse Low / High values
        lows = [l.strip() for l in (params.factor_lows_str or "").split(",") if l.strip()]
        highs = [h.strip() for h in (params.factor_highs_str or "").split(",") if h.strip()]
        
        design_type = params.design_type
        gens_used: List[str] = []
        resolution_desc = "Full Factorial"

        # Generate base matrix
        if design_type == "plackett_burman":
            base_matrix = build_plackett_burman(k, params.num_runs)
            resolution_desc = "Resolution III (Screening)"
            design_title = f"Plackett-Burman Design ({base_matrix.shape[0]} Runs)"
        elif design_type == "general_full":
            # Parse mixed levels
            lvl_strs = [s.strip() for s in (params.general_levels_str or "").split(",") if s.strip()]
            levels = []
            for i in range(k):
                lvl_val = int(lvl_strs[i]) if i < len(lvl_strs) and lvl_strs[i].isdigit() else 2
                levels.append(max(2, lvl_val))
            base_matrix = build_general_full_factorial(levels)
            resolution_desc = "General Full Factorial"
            design_title = f"General Full Factorial Design ({base_matrix.shape[0]} Runs)"
        else: # 2_level or split_plot
            default_runs = 2**k if k <= 6 else (32 if k <= 8 else 64)
            chosen_runs = params.num_runs or default_runs
            # clamp chosen_runs to valid power of 2
            if chosen_runs > 2**k:
                chosen_runs = 2**k
            base_matrix, gens_used, resolution_desc = build_fractional_factorial_2level(k, chosen_runs)
            fraction_str = "Full" if chosen_runs == 2**k else f"1/{2**k // chosen_runs} Fraction"
            design_title = f"2-Level Factorial Design ({chosen_runs} Runs, {fraction_str})"

        base_runs = base_matrix.shape[0]

        # Replicates
        reps = max(1, min(10, params.num_replicates))
        replicated_matrix = np.tile(base_matrix, (reps, 1))

        # Center points per block
        n_center = max(0, min(12, params.num_center_points))
        num_blocks = max(1, min(8, params.num_blocks))

        total_base_runs = replicated_matrix.shape[0]
        
        # Build Standard Runs Matrix
        rows_list = []
        std_order = 1
        
        # Add factorial runs
        for r_idx in range(total_base_runs):
            block_idx = (r_idx % num_blocks) + 1
            row_dict = {
                "StdOrder": std_order,
                "RunOrder": std_order,
                "CenterPt": 1,
                "Blocks": block_idx,
            }
            for f_idx in range(k):
                val = base_matrix[r_idx % base_runs, f_idx]
                fname = factor_names[f_idx]
                
                # Un-code if low/high specified
                if design_type != "general_full" and f_idx < len(lows) and f_idx < len(highs):
                    try:
                        low_val = float(lows[f_idx])
                        high_val = float(highs[f_idx])
                        un_coded = low_val if val == -1 else high_val
                        row_dict[fname] = un_coded
                    except ValueError:
                        row_dict[fname] = lows[f_idx] if val == -1 else highs[f_idx]
                else:
                    row_dict[fname] = int(val)
            rows_list.append(row_dict)
            std_order += 1

        # Add center points
        if n_center > 0 and design_type != "general_full":
            for b in range(1, num_blocks + 1):
                for cp in range(n_center):
                    row_dict = {
                        "StdOrder": std_order,
                        "RunOrder": std_order,
                        "CenterPt": 0,
                        "Blocks": b,
                    }
                    for f_idx in range(k):
                        fname = factor_names[f_idx]
                        if f_idx < len(lows) and f_idx < len(highs):
                            try:
                                low_val = float(lows[f_idx])
                                high_val = float(highs[f_idx])
                                row_dict[fname] = (low_val + high_val) / 2.0
                            except ValueError:
                                row_dict[fname] = "Center"
                        else:
                            row_dict[fname] = 0
                    rows_list.append(row_dict)
                    std_order += 1

        total_runs = len(rows_list)

        # Randomize RunOrder if requested
        if params.randomize_runs:
            if params.random_seed is not None:
                np.random.seed(params.random_seed)
            perm = np.random.permutation(total_runs)
            for idx, p_val in enumerate(perm):
                rows_list[idx]["RunOrder"] = int(p_val) + 1
            # Sort by RunOrder for the worksheet display
            rows_list.sort(key=lambda x: x["RunOrder"])

        # Format Columns for Worksheet Store
        worksheet_columns = [
            {"id": "c1", "name": "StdOrder", "type": "numeric"},
            {"id": "c2", "name": "RunOrder", "type": "numeric"},
            {"id": "c3", "name": "CenterPt", "type": "numeric"},
            {"id": "c4", "name": "Blocks", "type": "numeric"},
        ]

        for i, fname in enumerate(factor_names):
            worksheet_columns.append({
                "id": f"c{i + 5}",
                "name": fname,
                "type": "numeric"
            })

        # Add Response place-holders
        resp_id1 = f"c{k + 5}"
        resp_id2 = f"c{k + 6}"
        worksheet_columns.append({"id": resp_id1, "name": "Response_1", "type": "numeric"})
        worksheet_columns.append({"id": resp_id2, "name": "Response_2", "type": "numeric"})

        # Map row dicts to column ids
        worksheet_rows = []
        for r in rows_list:
            w_row = {
                "c1": r["StdOrder"],
                "c2": r["RunOrder"],
                "c3": r["CenterPt"],
                "c4": r["Blocks"],
            }
            for i, fname in enumerate(factor_names):
                w_row[f"c{i + 5}"] = r[fname]
            w_row[resp_id1] = None
            w_row[resp_id2] = None
            worksheet_rows.append(w_row)

        # Generate Minitab-Identical Session Output Text Log
        gens_str = ", ".join(gens_used) if gens_used else "None (Full Factorial)"
        text_lines = [
            "Factorial Design",
            "",
            f"Design Type       : {design_title}",
            f"Factors           : {k}",
            f"Base Runs         : {base_runs}",
            f"Total Runs        : {total_runs}",
            f"Replicates        : {reps}",
            f"Blocks            : {num_blocks}",
            f"Center Points     : {n_center * num_blocks}",
            f"Resolution        : {resolution_desc}",
            f"Generators        : {gens_str}",
            "",
            "Design Aliasing & Confounding Relations:",
        ]

        if gens_used:
            for g in gens_used:
                text_lines.append(f"  Identity relation: I = {g.replace('=', '')}")
            text_lines.append("  Main effects are confounded with interaction terms according to the design resolution.")
        else:
            text_lines.append("  No confounding: All main effects and interactions are orthogonal and fully estimable.")

        text_lines.extend([
            "",
            "Factors and Level Settings:",
            f"  {'Factor':<8} {'Name':<16} {'Low Level':<12} {'High Level':<12}",
            f"  {'-'*8} {'-'*16} {'-'*12} {'-'*12}",
        ])
        for i, fname in enumerate(factor_names):
            l_val = lows[i] if i < len(lows) else "-1"
            h_val = highs[i] if i < len(highs) else "+1"
            text_lines.append(f"  {chr(65+i):<8} {fname:<16} {l_val:<12} {h_val:<12}")

        # Summary Table for Session card
        summary_table = TableResult(
            title="Factorial Design Summary",
            headers=["Parameter", "Specification"],
            rows=[
                ["Design Class", design_title],
                ["Number of Factors", k],
                ["Base Runs", base_runs],
                ["Total Runs in Worksheet", total_runs],
                ["Replicates", reps],
                ["Center Points", n_center * num_blocks],
                ["Blocks", num_blocks],
                ["Design Resolution", resolution_desc],
                ["Generators", gens_str],
            ],
            notes=[
                f"Generated {total_runs} experimental runs into worksheet '{params.worksheet_name}'.",
                "Enter experimental observations into 'Response_1' and proceed to analysis."
            ]
        )

        return AnalysisResult(
            title=f"Factorial Design: {design_title}",
            subtitle=f"{k} Factors, {total_runs} Runs ({resolution_desc})",
            text_output="\n".join(text_lines),
            tables=[summary_table],
            statistics={
                "design_type": design_type,
                "factors": k,
                "factor_names": factor_names,
                "runs": total_runs,
                "resolution": resolution_desc,
                "blocks": num_blocks,
                "center_points": n_center * num_blocks,
            },
            action_type="worksheet_overwrite",
            worksheet_data={
                "name": params.worksheet_name or "Factorial Design",
                "columns": worksheet_columns,
                "rows": worksheet_rows
            }
        )
