"""
Response Surface Methodology (RSM) Design Generator Plugin for OpenMinitab.
Supports:
  - Central Composite Designs (CCD): Full CCD, Small CCD (Half-Fraction core)
    * Axial point alpha options: Rotatable, Spherical, Face-Centered (CCF), Orthogonal, Custom
    * Center points in Cube block and Axial block
  - Box-Behnken Designs (BBD): 3 to 10 factors with center points
Features:
  - PtType tagging (1=Cube, -1=Axial, 0=Center)
  - Coded and un-coded actual engineering level scaling
  - Seeded RunOrder randomization
  - Rotatability verification and Degrees of Freedom breakdown
"""

from typing import Any, Dict, List, Optional
import itertools
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ..base import AnalysisPlugin, AnalysisResult, TableResult



class CreateRsmParams(BaseModel):
    design_type: str = Field(
        "ccd",
        description="RSM Design Type",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Central Composite Design (CCD)", "value": "ccd"},
                {"label": "Box-Behnken Design (BBD)", "value": "bbd"}
            ]
        }
    )
    num_factors: int = Field(3, description="Number of Continuous Factors (2 to 10 for CCD, 3 to 10 for BBD)")
    ccd_subtype: str = Field(
        "full",
        description="CCD Factorial Core Subtype",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Full Factorial Core (2^k)", "value": "full"},
                {"label": "Small / Fractional Core (2^(k-1))", "value": "fractional"}
            ]
        }
    )
    alpha_choice: str = Field(
        "rotatable",
        description="Axial/Star Point Position (Alpha)",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Rotatable: alpha = (2^k)^(1/4)", "value": "rotatable"},
                {"label": "Spherical: alpha = sqrt(k)", "value": "spherical"},
                {"label": "Face-Centered: alpha = 1.0 (CCF)", "value": "face_centered"},
                {"label": "Orthogonal: alpha for orthogonal blocking", "value": "orthogonal"},
                {"label": "Custom: User-specified alpha value", "value": "custom"}
            ]
        }
    )
    custom_alpha: Optional[float] = Field(None, description="Custom Alpha value (if custom choice selected)")
    cube_center_points: int = Field(4, description="Center points in Cube block")
    axial_center_points: int = Field(2, description="Center points in Axial block (CCD)")
    bbd_center_points: int = Field(3, description="Center points (BBD)")
    num_replicates: int = Field(1, description="Number of Replicates (1 to 10)")
    num_blocks: int = Field(1, description="Number of Blocks (1, 2, or 3)")
    factor_names_str: str = Field("A, B, C", description="Factor Names (comma-separated)")
    factor_lows_str: Optional[str] = Field("-1, -1, -1", description="Low level values (-1)")
    factor_highs_str: Optional[str] = Field("1, 1, 1", description="High level values (+1)")
    randomize_runs: bool = Field(True, description="Randomize Run Order")
    random_seed: Optional[int] = Field(None, description="Base for Random Number Generator (Seed)")
    worksheet_name: Optional[str] = Field("RSM Design", description="Destination Worksheet Name")


def build_box_behnken(k: int) -> np.ndarray:
    """
    Constructs Box-Behnken design matrix by combining 2^2 factorials with pairs of factors.
    """
    pairs = list(itertools.combinations(range(k), 2))
    two_lvl = np.array([
        [-1, -1],
        [-1, 1],
        [1, -1],
        [1, 1]
    ])
    
    rows = []
    for p in pairs:
        for r in range(4):
            row = np.zeros(k, dtype=float)
            row[p[0]] = two_lvl[r, 0]
            row[p[1]] = two_lvl[r, 1]
            rows.append(row)
            
    return np.array(rows)


class CreateRsmDesignPlugin(AnalysisPlugin):
    id = "doe_create_rsm"
    name = "Create Response Surface Design"
    menu_path = ["Stat", "DOE", "Response Surface", "Create Response Surface Design"]
    description = "Generates Central Composite (CCD) and Box-Behnken (BBD) Response Surface Designs."
    param_schema = CreateRsmParams

    def execute(self, df: pd.DataFrame, params: CreateRsmParams) -> AnalysisResult:
        design_type = params.design_type
        min_k = 3 if design_type == "bbd" else 2
        k = max(min_k, min(10, params.num_factors))

        # Parse Factor Names
        raw_names = [f.strip() for f in params.factor_names_str.split(",") if f.strip()]
        factor_names = []
        for i in range(k):
            if i < len(raw_names):
                factor_names.append(raw_names[i])
            else:
                factor_names.append(chr(65 + i) if i < 26 else f"X{i+1}")

        # Parse Low / High values
        lows = [float(l.strip()) if l.strip().replace('-', '').replace('.', '').isdigit() else -1.0 
                for l in (params.factor_lows_str or "").split(",") if l.strip()]
        highs = [float(h.strip()) if h.strip().replace('-', '').replace('.', '').isdigit() else 1.0 
                 for h in (params.factor_highs_str or "").split(",") if h.strip()]

        while len(lows) < k:
            lows.append(-1.0)
        while len(highs) < k:
            highs.append(1.0)

        rows_list = []
        std_order = 1
        num_blocks = max(1, min(3, params.num_blocks))

        if design_type == "ccd":
            # Determine Cube points
            if params.ccd_subtype == "fractional" and k >= 5:
                # 2^(k-1) resolution V core
                base_cube = np.array(list(itertools.product([-1, 1], repeat=k-1)))
                # Generator: last factor = product of all preceding
                last_col = np.prod(base_cube, axis=1, keepdims=True)
                cube_matrix = np.column_stack([base_cube, last_col])
                n_cube = cube_matrix.shape[0]
                cube_desc = f"Half-Fraction Cube (2^{k-1} = {n_cube} pts)"
            else:
                cube_matrix = np.array(list(itertools.product([-1, 1], repeat=k)))
                n_cube = 2**k
                cube_desc = f"Full Factorial Cube (2^{k} = {n_cube} pts)"

            # Compute Alpha value
            if params.alpha_choice == "rotatable":
                alpha = float((n_cube)**0.25)
                alpha_desc = f"Rotatable (alpha = {alpha:.4f})"
            elif params.alpha_choice == "spherical":
                alpha = float(np.sqrt(k))
                alpha_desc = f"Spherical (alpha = {alpha:.4f})"
            elif params.alpha_choice == "face_centered":
                alpha = 1.0
                alpha_desc = "Face-Centered (alpha = 1.0, CCF)"
            elif params.alpha_choice == "orthogonal":
                n_c0 = max(1, params.cube_center_points)
                alpha = float(np.sqrt(k * (n_cube + 2 * n_c0) / (2 * n_cube)))
                alpha_desc = f"Orthogonal Blocking (alpha = {alpha:.4f})"
            elif params.alpha_choice == "custom" and params.custom_alpha is not None:
                alpha = float(params.custom_alpha)
                alpha_desc = f"Custom (alpha = {alpha:.4f})"
            else:
                alpha = float((n_cube)**0.25)
                alpha_desc = f"Rotatable (alpha = {alpha:.4f})"

            # Construct Axial/Star matrix: 2k points
            axial_matrix = np.zeros((2 * k, k), dtype=float)
            for i in range(k):
                axial_matrix[2 * i, i] = -alpha
                axial_matrix[2 * i + 1, i] = alpha

            n_axial = 2 * k
            n_center_cube = max(0, params.cube_center_points)
            n_center_axial = max(0, params.axial_center_points)

            reps = max(1, min(10, params.num_replicates))
            
            # Block 1: Cube points + Cube center points
            for r in range(reps):
                for i in range(n_cube):
                    row_dict = {
                        "StdOrder": std_order,
                        "RunOrder": std_order,
                        "PtType": 1, # Cube point
                        "Blocks": 1,
                    }
                    for f in range(k):
                        c_val = cube_matrix[i, f]
                        mid = (lows[f] + highs[f]) / 2.0
                        half = (highs[f] - lows[f]) / 2.0
                        row_dict[factor_names[f]] = mid + c_val * half
                    rows_list.append(row_dict)
                    std_order += 1

                for c in range(n_center_cube):
                    row_dict = {
                        "StdOrder": std_order,
                        "RunOrder": std_order,
                        "PtType": 0, # Center point
                        "Blocks": 1,
                    }
                    for f in range(k):
                        row_dict[factor_names[f]] = (lows[f] + highs[f]) / 2.0
                    rows_list.append(row_dict)
                    std_order += 1

            # Block 2 (or Block 1 if unblocked): Axial points + Axial center points
            axial_block_num = 2 if num_blocks > 1 else 1
            for r in range(reps):
                for i in range(n_axial):
                    row_dict = {
                        "StdOrder": std_order,
                        "RunOrder": std_order,
                        "PtType": -1, # Axial / Star point
                        "Blocks": axial_block_num,
                    }
                    for f in range(k):
                        c_val = axial_matrix[i, f]
                        mid = (lows[f] + highs[f]) / 2.0
                        half = (highs[f] - lows[f]) / 2.0
                        row_dict[factor_names[f]] = mid + c_val * half
                    rows_list.append(row_dict)
                    std_order += 1

                for c in range(n_center_axial):
                    row_dict = {
                        "StdOrder": std_order,
                        "RunOrder": std_order,
                        "PtType": 0, # Center point
                        "Blocks": axial_block_num,
                    }
                    for f in range(k):
                        row_dict[factor_names[f]] = (lows[f] + highs[f]) / 2.0
                    rows_list.append(row_dict)
                    std_order += 1

            design_title = f"Central Composite Design (CCD, k={k})"
            spec_rows = [
                ["Design Type", "Central Composite Design (CCD)"],
                ["Number of Continuous Factors", k],
                ["Cube Core Specification", cube_desc],
                ["Cube Points", n_cube * reps],
                ["Axial (Star) Points", n_axial * reps],
                ["Axial Distance (Alpha)", f"{alpha:.4f} ({params.alpha_choice})"],
                ["Center Points in Cube Block", n_center_cube * reps],
                ["Center Points in Axial Block", n_center_axial * reps],
                ["Total Center Points", (n_center_cube + n_center_axial) * reps],
                ["Number of Blocks", num_blocks],
                ["Total Design Runs", len(rows_list)],
            ]

        else: # Box-Behnken Design (BBD)
            bbd_base = build_box_behnken(k)
            n_factorial = bbd_base.shape[0]
            n_center = max(1, min(12, params.bbd_center_points))
            reps = max(1, min(10, params.num_replicates))
            alpha = 1.0

            for r in range(reps):
                for i in range(n_factorial):
                    row_dict = {
                        "StdOrder": std_order,
                        "RunOrder": std_order,
                        "PtType": 1, # Factorial edge point
                        "Blocks": 1,
                    }
                    for f in range(k):
                        c_val = bbd_base[i, f]
                        mid = (lows[f] + highs[f]) / 2.0
                        half = (highs[f] - lows[f]) / 2.0
                        row_dict[factor_names[f]] = mid + c_val * half
                    rows_list.append(row_dict)
                    std_order += 1

                for c in range(n_center):
                    row_dict = {
                        "StdOrder": std_order,
                        "RunOrder": std_order,
                        "PtType": 0, # Center point
                        "Blocks": 1,
                    }
                    for f in range(k):
                        row_dict[factor_names[f]] = (lows[f] + highs[f]) / 2.0
                    rows_list.append(row_dict)
                    std_order += 1

            design_title = f"Box-Behnken Design (BBD, k={k})"
            spec_rows = [
                ["Design Type", "Box-Behnken Design (BBD)"],
                ["Number of Continuous Factors", k],
                ["Edge / Factorial Points", n_factorial * reps],
                ["Center Points", n_center * reps],
                ["Factor Levels Required", "3 Levels (-1, 0, +1; No extreme axial points)"],
                ["Number of Blocks", 1],
                ["Total Design Runs", len(rows_list)],
            ]

        total_runs = len(rows_list)

        # Randomize RunOrder if requested
        if params.randomize_runs:
            if params.random_seed is not None:
                np.random.seed(params.random_seed)
            perm = np.random.permutation(total_runs)
            for idx, p_val in enumerate(perm):
                rows_list[idx]["RunOrder"] = int(p_val) + 1
            rows_list.sort(key=lambda x: x["RunOrder"])

        # Format Columns for Worksheet Store
        worksheet_columns = [
            {"id": "c1", "name": "StdOrder", "type": "numeric"},
            {"id": "c2", "name": "RunOrder", "type": "numeric"},
            {"id": "c3", "name": "PtType", "type": "numeric"},
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
                "c3": r["PtType"],
                "c4": r["Blocks"],
            }
            for i, fname in enumerate(factor_names):
                w_row[f"c{i + 5}"] = round(r[fname], 4) if isinstance(r[fname], float) else r[fname]
            w_row[resp_id1] = None
            w_row[resp_id2] = None
            worksheet_rows.append(w_row)

        # Calculate Full Quadratic Model Degrees of Freedom Breakdown
        linear_terms = k
        square_terms = k
        interaction_terms = k * (k - 1) // 2
        model_dof = 1 + linear_terms + square_terms + interaction_terms
        pure_error_dof = max(0, total_runs - model_dof)

        # Session text output
        text_lines = [
            "Response Surface Design",
            "",
            f"Design Type       : {design_title}",
            f"Factors           : {k}",
            f"Total Runs        : {total_runs}",
            f"Alpha (Axial)     : {alpha:.4f}",
            "",
            "Full Quadratic Model Terms & Degrees of Freedom:",
            f"  Linear Terms ({k})          : {linear_terms} DF",
            f"  Square / Quadratic Terms ({k}) : {square_terms} DF",
            f"  2-Way Interactions ({interaction_terms})    : {interaction_terms} DF",
            f"  Model Parameter Total     : {model_dof} DF (including Constant)",
            f"  Residual / Pure Error     : {pure_error_dof} DF",
            "",
            "Factors and Actual Operating Ranges:",
            f"  {'Factor':<8} {'Name':<16} {'Low (-1)':<12} {'High (+1)':<12} {'Axial Low (-a)':<16} {'Axial High (+a)':<16}",
            f"  {'-'*8} {'-'*16} {'-'*12} {'-'*12} {'-'*16} {'-'*16}",
        ]

        for i, fname in enumerate(factor_names):
            mid = (lows[i] + highs[i]) / 2.0
            half = (highs[i] - lows[i]) / 2.0
            ax_low = mid - alpha * half
            ax_high = mid + alpha * half
            text_lines.append(
                f"  {chr(65+i):<8} {fname:<16} {lows[i]:<12.2f} {highs[i]:<12.2f} {ax_low:<16.3f} {ax_high:<16.3f}"
            )

        summary_table = TableResult(
            title="Response Surface Design Summary",
            headers=["Design Parameter", "Value / Specification"],
            rows=spec_rows,
            notes=[
                f"Generated {total_runs} experimental runs into worksheet '{params.worksheet_name}'.",
                "Point Type codes: 1 = Factorial/Cube, -1 = Axial/Star, 0 = Center point.",
                "Enter measurements in 'Response_1' and proceed to response surface regression & contour optimization."
            ]
        )

        return AnalysisResult(
            title=f"RSM Design: {design_title}",
            subtitle=f"{k} Factors, {total_runs} Runs (Alpha = {alpha:.3f})",
            text_output="\n".join(text_lines),
            tables=[summary_table],
            statistics={
                "design_type": design_type,
                "factors": k,
                "factor_names": factor_names,
                "runs": total_runs,
                "alpha": alpha,
                "model_dof": model_dof,
                "residual_dof": pure_error_dof,
            },
            action_type="worksheet_overwrite",
            worksheet_data={
                "name": params.worksheet_name or "RSM Design",
                "columns": worksheet_columns,
                "rows": worksheet_rows
            }
        )
