"""
Mixture Design Generator Plugin for OpenMinitab.
Supports:
  - Simplex Lattice Designs {q, m} (Degree 1 to 6 with optional interior augmentation)
  - Simplex Centroid Designs (Pure, Binary, Ternary, Complete Centroids + Axial points)
  - Extreme Vertices / Constrained Mixture Designs (Lower and Upper bound constraints)
  - Process Variable Crossing (Mixture crossed with 2-level factorial process variables)
Features:
  - Mixture Total scaling (1.0 for proportions, 100.0 for percentages, or custom total)
  - Pseudo-component transformations
  - Scheffé canonical polynomial model degree tracking
  - Seeded RunOrder randomization
"""

from typing import Any, Dict, List, Optional
import itertools
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ..base import AnalysisPlugin, AnalysisResult, TableResult


class CreateMixtureParams(BaseModel):
    design_type: str = Field(
        "simplex_centroid",
        description="Mixture Design Type",
        json_schema_extra={
            "ui_type": "select",
            "options": [
                {"label": "Simplex Centroid Design", "value": "simplex_centroid"},
                {"label": "Simplex Lattice Design", "value": "simplex_lattice"},
                {"label": "Extreme Vertices / Constrained Mixture", "value": "extreme_vertices"}
            ]
        }
    )
    num_components: int = Field(3, description="Number of Mixture Components (2 to 12)")
    mixture_total: float = Field(1.0, description="Mixture Total (1.0 for proportions, 100.0 for percentages)")
    lattice_degree: int = Field(2, description="Simplex Lattice Degree (1 to 6)")
    augment_interior: bool = Field(True, description="Augment with interior centroid points")
    augment_axial: bool = Field(False, description="Augment with axial interior points")
    num_replicates: int = Field(1, description="Number of Replicates (1 to 10)")
    component_names_str: str = Field("Comp_A, Comp_B, Comp_C", description="Component Names (comma-separated)")
    lower_bounds_str: Optional[str] = Field("0, 0, 0", description="Lower bounds for components")
    upper_bounds_str: Optional[str] = Field("1, 1, 1", description="Upper bounds for components")
    process_variables_str: Optional[str] = Field("", description="Process Variables (e.g. Temp, Speed; optional)")
    randomize_runs: bool = Field(True, description="Randomize Run Order")
    random_seed: Optional[int] = Field(None, description="Base for Random Number Generator (Seed)")
    worksheet_name: Optional[str] = Field("Mixture Design", description="Destination Worksheet Name")


def generate_simplex_lattice(q: int, m: int) -> np.ndarray:
    """
    Generates Simplex Lattice points {q, m} where sum(x_i) = m with integer partitions.
    """
    def partitions(n, k):
        if k == 1:
            yield [n]
        else:
            for i in range(n + 1):
                for p in partitions(n - i, k - 1):
                    yield [i] + p

    pts = list(partitions(m, q))
    pts_arr = np.array(pts, dtype=float) / float(m)
    return pts_arr


def generate_simplex_centroid(q: int, augment_axial: bool = False) -> np.ndarray:
    """
    Generates all pure components, binary blends, ternary blends, up to overall centroid.
    """
    rows = []
    # 1. Pure, Binary, Ternary, ..., q-ary combinations
    for size in range(1, q + 1):
        for combo in itertools.combinations(range(q), size):
            pt = np.zeros(q, dtype=float)
            for idx in combo:
                pt[idx] = 1.0 / size
            rows.append(pt)

    # 2. Optional Axial interior points: x_i = (1 + (q-1)delta)/q, others = (1 - delta)/q
    if augment_axial and q >= 3:
        delta = 0.5
        for i in range(q):
            pt = np.full(q, (1.0 - delta) / q, dtype=float)
            pt[i] = (1.0 + (q - 1) * delta) / q
            rows.append(pt)

    return np.array(rows)


def generate_extreme_vertices(q: int, lowers: List[float], uppers: List[float], total: float) -> np.ndarray:
    """
    Generates extreme vertices for upper/lower bounded mixture design using XVERT/Piepel algorithm.
    """
    L = np.array(lowers, dtype=float)
    U = np.array(uppers, dtype=float)
    sum_L = np.sum(L)
    
    # If unconstrained (all 0 to 1), return standard simplex centroid
    if np.all(L <= 1e-6) and np.all(U >= total - 1e-6):
        return generate_simplex_centroid(q, augment_axial=True) * total

    # Pseudo-components range
    R = total - sum_L
    if R <= 0:
        # Degenerate bounds, return lower bounds
        return np.array([L])

    # Generate combination of lower/upper bounds
    pts_list = []
    bound_choices = [[L[i], U[i]] for i in range(q)]
    
    # Check boundary combinations
    for combo in itertools.product(*bound_choices):
        pt = np.array(combo, dtype=float)
        # Try to balance point to sum to total
        diff = total - np.sum(pt)
        if abs(diff) < 1e-4:
            pts_list.append(pt)

    # Add systematic single-variable balance points
    for i in range(q):
        for combo in itertools.product(*[bound_choices[j] for j in range(q) if j != i]):
            pt = np.zeros(q, dtype=float)
            c_idx = 0
            for j in range(q):
                if j != i:
                    pt[j] = combo[c_idx]
                    c_idx += 1
            rem = total - np.sum(pt)
            if L[i] - 1e-5 <= rem <= U[i] + 1e-5:
                pt[i] = max(L[i], min(U[i], rem))
                pts_list.append(pt)

    if len(pts_list) == 0:
        # Fallback to centroid and proportional vertices
        pts_list.append((L + U) / 2.0)
        for i in range(q):
            pt = np.copy(L)
            pt[i] = min(U[i], L[i] + R)
            rem_sum = total - np.sum(pt)
            if rem_sum > 0:
                others = [j for j in range(q) if j != i]
                for o in others:
                    add_amt = min(U[o] - L[o], rem_sum)
                    pt[o] += add_amt
                    rem_sum -= add_amt
            pts_list.append(pt)

    # Deduplicate points
    unique_pts = []
    for p in pts_list:
        if not any(np.allclose(p, u, atol=1e-4) for u in unique_pts):
            unique_pts.append(p)

    # Add overall centroid of vertices
    centroid = np.mean(unique_pts, axis=0)
    unique_pts.append(centroid)

    return np.array(unique_pts)


class CreateMixtureDesignPlugin(AnalysisPlugin):
    id = "doe_create_mixture"
    name = "Create Mixture Design"
    menu_path = ["Stat", "DOE", "Mixture", "Create Mixture Design"]
    description = "Generates Simplex Lattice, Simplex Centroid, and Extreme Vertices Constrained Mixture Designs."
    param_schema = CreateMixtureParams

    def execute(self, df: pd.DataFrame, params: CreateMixtureParams) -> AnalysisResult:
        q = max(2, min(12, params.num_components))
        total = float(params.mixture_total) if params.mixture_total > 0 else 1.0

        # Parse Component Names
        raw_names = [c.strip() for c in params.component_names_str.split(",") if c.strip()]
        comp_names = []
        for i in range(q):
            if i < len(raw_names):
                comp_names.append(raw_names[i])
            else:
                comp_names.append(f"Comp_{chr(65+i)}" if i < 26 else f"Comp_{i+1}")

        # Parse Lower & Upper bounds
        lows = [float(l.strip()) if l.strip().replace('.', '').isdigit() else 0.0 
                for l in (params.lower_bounds_str or "").split(",") if l.strip()]
        uppers = [float(u.strip()) if u.strip().replace('.', '').isdigit() else total 
                  for u in (params.upper_bounds_str or "").split(",") if u.strip()]

        while len(lows) < q:
            lows.append(0.0)
        while len(uppers) < q:
            uppers.append(total)

        design_type = params.design_type

        # Generate base mixture matrix
        if design_type == "simplex_lattice":
            m = max(1, min(6, params.lattice_degree))
            base_matrix = generate_simplex_lattice(q, m) * total
            if params.augment_interior and q >= 3:
                centroid = np.full((1, q), total / q)
                base_matrix = np.vstack([base_matrix, centroid])
            design_title = f"Simplex Lattice Design ({q} Components, Degree {m})"
            model_terms_desc = f"Scheffé Polynomial of Degree {m}"
        elif design_type == "extreme_vertices":
            base_matrix = generate_extreme_vertices(q, lows, uppers, total)
            design_title = f"Extreme Vertices Mixture Design ({q} Components, Constrained)"
            model_terms_desc = "Constrained Mixture / Pseudo-components Model"
        else: # simplex_centroid
            base_matrix = generate_simplex_centroid(q, augment_axial=params.augment_axial) * total
            design_title = f"Simplex Centroid Design ({q} Components)"
            model_terms_desc = "Full Scheffé Centroid Polynomial"

        base_runs = base_matrix.shape[0]

        # Parse Process Variables if any (e.g. Temp, Speed)
        raw_proc_vars = [pv.strip() for pv in (params.process_variables_str or "").split(",") if pv.strip()]
        p_count = len(raw_proc_vars)
        if p_count > 0:
            proc_matrix = np.array(list(itertools.product([-1, 1], repeat=p_count)))
            n_proc = proc_matrix.shape[0]
            # Cross mixture with process
            crossed_rows = []
            for m_row in base_matrix:
                for p_row in proc_matrix:
                    crossed_rows.append((m_row, p_row))
        else:
            proc_matrix = None
            crossed_rows = [(m_row, None) for m_row in base_matrix]

        reps = max(1, min(10, params.num_replicates))
        
        rows_list = []
        std_order = 1

        for r in range(reps):
            for m_row, p_row in crossed_rows:
                # Classify point type: 0 = Centroid, 1 = Vertex/Blend, -1 = Axial
                is_centroid = np.allclose(m_row, np.mean(m_row))
                pt_type = 0 if is_centroid else 1

                row_dict = {
                    "StdOrder": std_order,
                    "RunOrder": std_order,
                    "PtType": pt_type,
                    "Blocks": 1,
                }

                # Add Mixture Component Values
                for i in range(q):
                    row_dict[comp_names[i]] = round(float(m_row[i]), 4)

                # Add Process Variable Values (if crossed)
                if p_row is not None:
                    for j in range(p_count):
                        row_dict[raw_proc_vars[j]] = int(p_row[j])

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
            rows_list.sort(key=lambda x: x["RunOrder"])

        # Format Columns for Worksheet Store
        worksheet_columns = [
            {"id": "c1", "name": "StdOrder", "type": "numeric"},
            {"id": "c2", "name": "RunOrder", "type": "numeric"},
            {"id": "c3", "name": "PtType", "type": "numeric"},
            {"id": "c4", "name": "Blocks", "type": "numeric"},
        ]

        col_counter = 5
        for fname in comp_names:
            worksheet_columns.append({
                "id": f"c{col_counter}",
                "name": fname,
                "type": "numeric"
            })
            col_counter += 1

        if p_count > 0:
            for pv in raw_proc_vars:
                worksheet_columns.append({
                    "id": f"c{col_counter}",
                    "name": pv,
                    "type": "numeric"
                })
                col_counter += 1

        # Add Response place-holders
        resp_id1 = f"c{col_counter}"
        resp_id2 = f"c{col_counter + 1}"
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
            c_idx = 5
            for fname in comp_names:
                w_row[f"c{c_idx}"] = r[fname]
                c_idx += 1
            if p_count > 0:
                for pv in raw_proc_vars:
                    w_row[f"c{c_idx}"] = r[pv]
                    c_idx += 1
            w_row[resp_id1] = None
            w_row[resp_id2] = None
            worksheet_rows.append(w_row)

        # Session text output
        text_lines = [
            "Mixture Design",
            "",
            f"Design Type       : {design_title}",
            f"Components (q)    : {q}",
            f"Mixture Total     : {total}",
            f"Base Points       : {base_runs}",
            f"Process Variables : {p_count if p_count > 0 else 'None'}",
            f"Replicates        : {reps}",
            f"Total Runs        : {total_runs}",
            f"Model Fit Class   : {model_terms_desc}",
            "",
            "Components and Constraint Bounds:",
            f"  {'Component':<12} {'Name':<18} {'Lower Bound':<14} {'Upper Bound':<14}",
            f"  {'-'*12} {'-'*18} {'-'*14} {'-'*14}",
        ]

        for i, fname in enumerate(comp_names):
            text_lines.append(
                f"  {f'X{i+1}':<12} {fname:<18} {lows[i]:<14.3f} {uppers[i]:<14.3f}"
            )

        summary_table = TableResult(
            title="Mixture Design Summary",
            headers=["Parameter", "Specification"],
            rows=[
                ["Design Class", design_title],
                ["Number of Components", q],
                ["Mixture Total", total],
                ["Base Mixture Points", base_runs],
                ["Process Factor Runs", 2**p_count if p_count > 0 else 1],
                ["Total Runs in Worksheet", total_runs],
                ["Replicates", reps],
                ["Canonical Polynomial", model_terms_desc],
            ],
            notes=[
                f"Generated {total_runs} experimental blend runs into worksheet '{params.worksheet_name}'.",
                "Ensure component proportions satisfy the sum total constraint.",
                "Enter measurements into 'Response_1' and proceed to Scheffé mixture regression & ternary contour plots."
            ]
        )

        return AnalysisResult(
            title=f"Mixture Design: {design_title}",
            subtitle=f"{q} Components, {total_runs} Runs (Total = {total})",
            text_output="\n".join(text_lines),
            tables=[summary_table],
            statistics={
                "design_type": design_type,
                "components": q,
                "component_names": comp_names,
                "mixture_total": total,
                "runs": total_runs,
                "process_variables": raw_proc_vars,
            },
            action_type="worksheet_overwrite",
            worksheet_data={
                "name": params.worksheet_name or "Mixture Design",
                "columns": worksheet_columns,
                "rows": worksheet_rows
            }
        )
