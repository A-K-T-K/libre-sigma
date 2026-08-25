import numpy as np
import pandas as pd
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from ...base import AnalysisPlugin, AnalysisResult, TableResult


class CorrespondenceParams(BaseModel):
    analysis_type: str = Field("Simple Correspondence Analysis", description="Type: Simple Correspondence Analysis or Multiple (MCA)")
    variables: List[str] = Field(..., description="Categorical variables (2 for Simple CA, 2+ for MCA)")
    num_components: int = Field(2, description="Number of principal dimensions to extract (default: 2)")


class CorrespondenceAnalysisPlugin(AnalysisPlugin):
    id: str = "correspondence_analysis"
    name: str = "Correspondence Analysis"
    menu_path: List[str] = ["Stat", "Multivariate", "Correspondence Analysis..."]
    description: str = "Perform Simple & Multiple Correspondence Analysis with Symmetric Biplot and Inertia Decomposition."
    param_schema: type[BaseModel] = CorrespondenceParams

    def execute(self, df: pd.DataFrame, params: CorrespondenceParams) -> AnalysisResult:
        cat_cols = [c for c in params.variables if c in df.columns]
        if len(cat_cols) < 2:
            raise ValueError("Correspondence Analysis requires at least 2 categorical columns.")

        clean_df = df[cat_cols].dropna()
        n = len(clean_df)
        if n < 4:
            raise ValueError("Correspondence Analysis requires at least 4 observations.")

        is_mca = "multiple" in params.analysis_type.lower() or len(cat_cols) > 2

        if not is_mca and len(cat_cols) == 2:
            # -------------------------------------------------------------
            # Simple Correspondence Analysis (2-Way Contingency Table)
            # -------------------------------------------------------------
            row_col = cat_cols[0]
            col_col = cat_cols[1]

            contingency = pd.crosstab(clean_df[row_col], clean_df[col_col])
            row_names = [str(r) for r in contingency.index]
            col_names = [str(c) for c in contingency.columns]

            N = contingency.values.astype(float)
            grand_total = float(np.sum(N))
            if grand_total < 1:
                raise ValueError("Contingency table has zero observations.")

            P = N / grand_total
            r_mass = np.sum(P, axis=1)
            c_mass = np.sum(P, axis=0)

            # Avoid division by zero
            r_mass_safe = np.where(r_mass > 0, r_mass, 1e-12)
            c_mass_safe = np.where(c_mass > 0, c_mass, 1e-12)

            Dr_inv_sqrt = np.diag(1.0 / np.sqrt(r_mass_safe))
            Dc_inv_sqrt = np.diag(1.0 / np.sqrt(c_mass_safe))

            expected = np.outer(r_mass, c_mass)
            S = Dr_inv_sqrt @ (P - expected) @ Dc_inv_sqrt

            U, singular_vals, Vt = np.linalg.svd(S, full_matrices=False)
            V = Vt.T

            inertias = singular_vals**2
            total_inertia = float(np.sum(inertias))
            chi_sq = grand_total * total_inertia

            proportions = inertias / total_inertia if total_inertia > 0 else np.zeros(len(inertias))
            cumulative = np.cumsum(proportions)

            k_dims = max(1, min(params.num_components, len(inertias)))

            # Row & Column Principal Coordinates
            row_coords = Dr_inv_sqrt @ U[:, :k_dims] @ np.diag(singular_vals[:k_dims])
            col_coords = Dc_inv_sqrt @ V[:, :k_dims] @ np.diag(singular_vals[:k_dims])

            analysis_title = f"Simple Correspondence Analysis: {row_col} vs {col_col}"

        else:
            # -------------------------------------------------------------
            # Multiple Correspondence Analysis (MCA via Indicator Matrix)
            # -------------------------------------------------------------
            dummies = [pd.get_dummies(clean_df[c], prefix=c, drop_first=False) for c in cat_cols]
            Z = pd.concat(dummies, axis=1).values.astype(float)
            all_cat_names = [col for d in dummies for col in d.columns]

            n_obs, total_cats = Z.shape
            Q = len(cat_cols)  # number of variables

            P = Z / (n_obs * Q)
            r_mass = np.sum(P, axis=1)
            c_mass = np.sum(P, axis=0)

            r_mass_safe = np.where(r_mass > 0, r_mass, 1e-12)
            c_mass_safe = np.where(c_mass > 0, c_mass, 1e-12)

            Dr_inv_sqrt = np.diag(1.0 / np.sqrt(r_mass_safe))
            Dc_inv_sqrt = np.diag(1.0 / np.sqrt(c_mass_safe))

            expected = np.outer(r_mass, c_mass)
            S = Dr_inv_sqrt @ (P - expected) @ Dc_inv_sqrt

            U, singular_vals, Vt = np.linalg.svd(S, full_matrices=False)
            V = Vt.T

            # In MCA, first eigenvalue is trivial (1.0) on Burt or rank is total_cats - Q
            inertias = singular_vals**2
            total_inertia = float((total_cats - Q) / Q)

            proportions = inertias / np.sum(inertias) if np.sum(inertias) > 0 else np.zeros(len(inertias))
            cumulative = np.cumsum(proportions)

            k_dims = max(1, min(params.num_components, len(inertias)))

            row_names = [f"Obs {i+1}" for i in range(n_obs)]
            col_names = all_cat_names

            row_coords = Dr_inv_sqrt @ U[:, :k_dims] @ np.diag(singular_vals[:k_dims])
            col_coords = Dc_inv_sqrt @ V[:, :k_dims] @ np.diag(singular_vals[:k_dims])

            chi_sq = n_obs * Q * total_inertia
            grand_total = float(n_obs)
            analysis_title = f"Multiple Correspondence Analysis: {', '.join(cat_cols)}"

        # 1. Inertia Decomposition Table
        num_reported_comps = min(5, len(inertias))
        inertia_headers = ["Component", "Singular Value", "Inertia", "Chi-Square", "% Inertia", "Cumulative %"]
        inertia_rows = []
        for i in range(num_reported_comps):
            comp_chi = grand_total * inertias[i]
            inertia_rows.append([
                f"Dimension {i+1}",
                f"{singular_vals[i]:.4f}",
                f"{inertias[i]:.4f}",
                f"{comp_chi:.2f}",
                f"{proportions[i]*100:.2f}%",
                f"{cumulative[i]*100:.2f}%"
            ])

        inertia_table = TableResult(
            title=f"Decomposition of Total Inertia (Total Inertia = {total_inertia:.4f}, Chi-Square = {chi_sq:.2f})",
            headers=inertia_headers,
            rows=inertia_rows
        )

        # 2. Category Coordinates Table
        cat_headers = ["Category / Profile", "Type", "Mass", "Coord Dim 1", "Coord Dim 2"]
        cat_rows = []

        if not is_mca:
            for i, r_name in enumerate(row_names):
                cat_rows.append([
                    r_name,
                    "Row Profile",
                    f"{r_mass[i]:.4f}",
                    f"{row_coords[i, 0]:.4f}",
                    f"{row_coords[i, 1] if k_dims > 1 else 0.0:.4f}"
                ])
        for j, c_name in enumerate(col_names):
            cat_rows.append([
                c_name,
                "Column Category",
                f"{c_mass[j]:.4f}",
                f"{col_coords[j, 0]:.4f}",
                f"{col_coords[j, 1] if k_dims > 1 else 0.0:.4f}"
            ])

        coords_table = TableResult(
            title="Principal Coordinates (Dimensions 1 & 2)",
            headers=cat_headers,
            rows=cat_rows
        )

        # Visual Symmetric Biplot
        traces: List[Dict[str, Any]] = []

        # Row points
        if not is_mca:
            traces.append({
                "type": "scatter",
                "mode": "markers+text",
                "x": row_coords[:, 0].tolist(),
                "y": (row_coords[:, 1] if k_dims > 1 else np.zeros(len(row_names))).tolist(),
                "text": row_names,
                "textposition": "top right",
                "name": f"Rows ({cat_cols[0]})",
                "marker": {"size": 9, "color": "#0f6cbd", "symbol": "square"},
                "textfont": {"color": "#0f6cbd", "size": 11}
            })

        # Column points
        traces.append({
            "type": "scatter",
            "mode": "markers+text",
            "x": col_coords[:, 0].tolist(),
            "y": (col_coords[:, 1] if k_dims > 1 else np.zeros(len(col_names))).tolist(),
            "text": col_names,
            "textposition": "bottom right",
            "name": f"Columns ({cat_cols[1] if not is_mca else 'Categories'})",
            "marker": {"size": 10, "color": "#d13438", "symbol": "triangle-up"},
            "textfont": {"color": "#d13438", "size": 11, "weight": 600}
        })

        # Zero reference lines
        plotly_figure = {
            "data": traces,
            "layout": {
                "title": f"Symmetric Biplot ({analysis_title})",
                "showlegend": True,
                "margin": {"l": 50, "r": 30, "t": 60, "b": 45},
                "xaxis": {
                    "title": f"Dimension 1 ({proportions[0]*100:.1f}% Inertia)",
                    "zeroline": True,
                    "zerolinecolor": "#605e5c",
                    "zerolinewidth": 1
                },
                "yaxis": {
                    "title": f"Dimension 2 ({proportions[1]*100 if len(proportions) > 1 else 0:.1f}% Inertia)",
                    "zeroline": True,
                    "zerolinecolor": "#605e5c",
                    "zerolinewidth": 1
                }
            }
        }

        text_lines = [
            analysis_title,
            f"Total Inertia: {total_inertia:.4f} | Chi-Square: {chi_sq:.2f} | Total Observations: {n}",
            "",
            "Inertia Decomposition:",
            f"{'Dimension':<14} {'Singular Val':>14} {'Inertia':>12} {'% Inertia':>12} {'Cum %':>10}"
        ]
        for row in inertia_rows:
            text_lines.append(f"{row[0]:<14} {float(row[1]):>14.4f} {float(row[2]):>12.4f} {row[4]:>12} {row[5]:>10}")

        return AnalysisResult(
            title=analysis_title,
            subtitle=f"Total Inertia = {total_inertia:.4f} | Chi-Square = {chi_sq:.2f} | Dim 1+2 = {cumulative[min(1, len(cumulative)-1)]*100:.2f}%",
            text_output="\n".join(text_lines),
            tables=[inertia_table, coords_table],
            plotly_figure=plotly_figure,
            statistics={
                "total_inertia": total_inertia,
                "chi_square": chi_sq,
                "singular_values": singular_vals.tolist(),
                "inertias": inertias.tolist(),
                "proportions": proportions.tolist(),
                "variables": cat_cols
            }
        )
