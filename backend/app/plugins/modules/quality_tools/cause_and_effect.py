"""
Cause-and-Effect (Ishikawa / Fishbone) Diagram Plugin for OpenMinitab Quality Tools.
Generates structured root-cause layout with 6Ms categories, major ribs, sub-branches, and vector rendering.
"""

import json
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


DEFAULT_6M_BRANCHES = [
    {"name": "Personnel", "causes": ["Training", "Fatigue", "Communication", "Experience"]},
    {"name": "Machine", "causes": ["Calibration", "Wear & Tear", "Maintenance", "Speed Settings"]},
    {"name": "Material", "causes": ["Raw Material", "Supplier Variation", "Viscosity", "Moisture"]},
    {"name": "Method", "causes": ["Standard SOP", "Work Instructions", "Setup Time", "Process Flow"]},
    {"name": "Measurement", "causes": ["Gage Precision", "Bias", "Sampling Method", "Inspector Bias"]},
    {"name": "Environment", "causes": ["Temperature", "Humidity", "Vibration", "Dust / Cleanliness"]}
]


class CauseAndEffectParams(BaseModel):
    effect_label: str = Field(
        "Quality Defect",
        description="Effect / Problem Statement (Box at the right)",
        json_schema_extra={"ui_type": "text"}
    )
    branches_json: Optional[str] = Field(
        None,
        description="Custom Branches and Causes (JSON format, optional)",
        json_schema_extra={"ui_type": "text"}
    )


class CauseAndEffectPlugin(AnalysisPlugin):
    id = "cause_and_effect"
    name = "Cause-and-Effect Diagram"
    menu_path = ["Stat", "Quality Tools", "Cause-and-Effect"]
    description = "Constructs an Ishikawa (fishbone) diagram organizing potential root causes into structured branches."
    param_schema = CauseAndEffectParams

    def execute(self, df: pd.DataFrame, params: CauseAndEffectParams) -> AnalysisResult:
        effect = params.effect_label or "Process Problem"

        # Parse branches
        branches = DEFAULT_6M_BRANCHES
        if params.branches_json:
            try:
                parsed = json.loads(params.branches_json)
                if isinstance(parsed, list) and len(parsed) > 0:
                    branches = parsed
            except Exception:
                pass

        num_branches = len(branches)
        top_branches = [branches[i] for i in range(0, num_branches, 2)]
        bottom_branches = [branches[i] for i in range(1, num_branches, 2)]

        # Layout Geometry
        # Spine: from x=0.5 to x=8.5 at y=0.0. Effect box at x=9.5, y=0.0
        spine_start = 0.5
        spine_end = 8.0
        effect_x = 9.2

        shapes = []
        annotations = []

        # Central Backbone Spine line
        shapes.append({
            "type": "line",
            "x0": spine_start,
            "y0": 0.0,
            "x1": spine_end + 0.5,
            "y1": 0.0,
            "line": {"color": "#004d2c", "width": 4}
        })

        # Effect Box Annotation at right
        annotations.append({
            "x": effect_x,
            "y": 0.0,
            "text": f"<b>{effect}</b>",
            "showarrow": False,
            "bgcolor": "#004d2c",
            "bordercolor": "#003820",
            "borderwidth": 2,
            "font": {"color": "white", "size": 13, "family": "Arial, sans-serif"},
            "align": "center",
            "xanchor": "left"
        })

        # Render Top Ribs (angled at ~60 deg, connecting to spine)
        n_top = max(1, len(top_branches))
        top_positions = np.linspace(spine_start + 1.2, spine_end - 0.5, n_top)

        for i, branch in enumerate(top_branches):
            attach_x = top_positions[i]
            rib_top_x = attach_x - 1.2
            rib_top_y = 2.5
            b_name = branch.get("name", f"Category {i+1}")
            causes = branch.get("causes", [])

            # Major rib line
            shapes.append({
                "type": "line",
                "x0": attach_x,
                "y0": 0.0,
                "x1": rib_top_x,
                "y1": rib_top_y,
                "line": {"color": "#0078d4", "width": 2.5}
            })

            # Branch Label Box
            annotations.append({
                "x": rib_top_x,
                "y": rib_top_y + 0.3,
                "text": f"<b>{b_name}</b>",
                "showarrow": False,
                "bgcolor": "#e6faf0",
                "bordercolor": "#0078d4",
                "borderwidth": 1.5,
                "font": {"color": "#004d2c", "size": 11},
                "align": "center"
            })

            # Sub-branches
            if causes:
                n_causes = len(causes)
                for c_idx, cause in enumerate(causes):
                    frac = (c_idx + 1) / (n_causes + 1)
                    sub_attach_x = attach_x - frac * 1.2
                    sub_attach_y = frac * rib_top_y
                    sub_len = 1.0

                    shapes.append({
                        "type": "line",
                        "x0": sub_attach_x,
                        "y0": sub_attach_y,
                        "x1": sub_attach_x - sub_len,
                        "y1": sub_attach_y,
                        "line": {"color": "#605e5c", "width": 1.5, "dash": "solid"}
                    })

                    annotations.append({
                        "x": sub_attach_x - sub_len - 0.1,
                        "y": sub_attach_y,
                        "text": str(cause),
                        "showarrow": False,
                        "xanchor": "right",
                        "font": {"size": 9.5, "color": "#323130"}
                    })

        # Render Bottom Ribs (angled at ~120 deg)
        n_bot = max(1, len(bottom_branches))
        bot_positions = np.linspace(spine_start + 1.2, spine_end - 0.5, n_bot)

        for i, branch in enumerate(bottom_branches):
            attach_x = bot_positions[i]
            rib_bot_x = attach_x - 1.2
            rib_bot_y = -2.5
            b_name = branch.get("name", f"Category {i+1}")
            causes = branch.get("causes", [])

            # Major rib line
            shapes.append({
                "type": "line",
                "x0": attach_x,
                "y0": 0.0,
                "x1": rib_bot_x,
                "y1": rib_bot_y,
                "line": {"color": "#0078d4", "width": 2.5}
            })

            # Branch Label Box
            annotations.append({
                "x": rib_bot_x,
                "y": rib_bot_y - 0.3,
                "text": f"<b>{b_name}</b>",
                "showarrow": False,
                "bgcolor": "#e6faf0",
                "bordercolor": "#0078d4",
                "borderwidth": 1.5,
                "font": {"color": "#004d2c", "size": 11},
                "align": "center"
            })

            # Sub-branches
            if causes:
                n_causes = len(causes)
                for c_idx, cause in enumerate(causes):
                    frac = (c_idx + 1) / (n_causes + 1)
                    sub_attach_x = attach_x - frac * 1.2
                    sub_attach_y = frac * rib_bot_y
                    sub_len = 1.0

                    shapes.append({
                        "type": "line",
                        "x0": sub_attach_x,
                        "y0": sub_attach_y,
                        "x1": sub_attach_x - sub_len,
                        "y1": sub_attach_y,
                        "line": {"color": "#605e5c", "width": 1.5, "dash": "solid"}
                    })

                    annotations.append({
                        "x": sub_attach_x - sub_len - 0.1,
                        "y": sub_attach_y,
                        "text": str(cause),
                        "showarrow": False,
                        "xanchor": "right",
                        "font": {"size": 9.5, "color": "#323130"}
                    })

        # Build Session Log Table
        table_rows = []
        for b in branches:
            table_rows.append([
                b.get("name", ""),
                str(len(b.get("causes", []))),
                ", ".join(b.get("causes", []))
            ])

        ishikawa_table = TableResult(
            title="Cause-and-Effect Structure: " + effect,
            headers=["Branch Category", "Cause Count", "Sub-Causes"],
            rows=table_rows
        )

        plotly_fig = {
            "data": [
                {
                    "type": "scatter",
                    "x": [-1.5, 11.5],
                    "y": [-3.5, 3.5],
                    "mode": "markers",
                    "marker": {"opacity": 0},
                    "hoverinfo": "none",
                    "showlegend": False
                }
            ],
            "layout": {
                "title": f"Cause-and-Effect (Ishikawa) Diagram for {effect}",
                "xaxis": {"showgrid": False, "zeroline": False, "showticklabels": False, "range": [-1.5, 12.0]},
                "yaxis": {"showgrid": False, "zeroline": False, "showticklabels": False, "range": [-3.8, 3.8]},
                "shapes": shapes,
                "annotations": annotations,
                "margin": {"l": 20, "r": 20, "t": 60, "b": 20}
            }
        }

        return AnalysisResult(
            title=f"Cause-and-Effect Diagram: {effect}",
            subtitle=f"{len(branches)} Main Branches | {sum(len(b.get('causes', [])) for b in branches)} Total Potential Causes",
            tables=[ishikawa_table],
            plotly_figure=plotly_fig,
            statistics={
                "effect": effect,
                "num_branches": len(branches),
                "total_causes": sum(len(b.get("causes", [])) for b in branches)
            }
        )
