"""
Excel (.xlsx / .xls) Service for LibRE Sigma.
Handles multi-sheet Excel workbook importing and exporting.
"""

import io
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np
from fastapi import APIRouter, File, UploadFile, HTTPException, Response
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/project", tags=["Excel Service"])


class ColumnData(BaseModel):
    id: str
    name: str
    type: str = "numeric"
    width: Optional[int] = 110


class WorksheetData(BaseModel):
    id: str
    name: str
    columns: List[ColumnData]
    rows: List[Dict[str, Any]]
    designMeta: Optional[Dict[str, Any]] = None


class ProjectPayload(BaseModel):
    title: Optional[str] = "LibRE Sigma Data"
    worksheets: List[WorksheetData]


@router.post("/xlsx/import")
async def import_xlsx(file: UploadFile = File(...)):
    """Imports an Excel (.xlsx / .xls) workbook with all sheets."""
    try:
        content = await file.read()
        excel_file = io.BytesIO(content)
        xl = pd.ExcelFile(excel_file)
        
        worksheets: List[Dict[str, Any]] = []
        for sheet_name in xl.sheet_names:
            df = xl.parse(sheet_name, dtype=str)
            if df.empty and len(df.columns) == 0:
                continue

            cols = []
            for c_idx, col_name in enumerate(df.columns):
                c_id = f"c{c_idx+1}"
                col_name_str = str(col_name).strip()
                if not col_name_str or col_name_str.startswith("Unnamed"):
                    col_name_str = f"C{c_idx+1}"
                
                col_type = "numeric"
                try:
                    pd.to_numeric(df[col_name], errors="raise")
                except (ValueError, TypeError):
                    col_type = "text"
                
                cols.append({
                    "id": c_id,
                    "name": col_name_str,
                    "type": col_type,
                    "width": 110
                })

            rows = []
            for _, r_series in df.iterrows():
                r_dict = {}
                for c_idx, col_name in enumerate(df.columns):
                    c_id = f"c{c_idx+1}"
                    val = r_series[col_name]
                    
                    if val is None or (isinstance(val, float) and (pd.isna(val) or not np.isfinite(val))):
                        r_dict[c_id] = ""
                    elif isinstance(val, str):
                        stripped = val.strip()
                        if stripped in ("", "*", "NA", "NaN", "nan", "null", "None"):
                            r_dict[c_id] = ""
                        elif cols[c_idx]["type"] == "numeric":
                            try:
                                r_dict[c_id] = float(stripped)
                            except ValueError:
                                r_dict[c_id] = stripped
                                cols[c_idx]["type"] = "text"
                        else:
                            r_dict[c_id] = stripped
                    elif isinstance(val, (int, float, np.integer, np.floating)):
                        if pd.isna(val) or not np.isfinite(float(val)):
                            r_dict[c_id] = ""
                        else:
                            r_dict[c_id] = float(val)
                    else:
                        r_dict[c_id] = str(val)
                rows.append(r_dict)

            worksheets.append({
                "id": f"ws-{sheet_name.lower().replace(' ', '-')}-{int(datetime.now().timestamp())}",
                "name": sheet_name,
                "columns": cols,
                "rows": rows
            })

        if not worksheets:
            raise ValueError("No readable sheets found in the workbook.")

        return {"worksheets": worksheets}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import Excel workbook: {str(e)}")


@router.post("/xlsx/export")
async def export_xlsx(payload: ProjectPayload):
    """Exports all worksheets into a multi-tab Excel (.xlsx) workbook."""
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for ws in payload.worksheets:
                data_dict = {}
                for col in ws.columns:
                    col_vals = [r.get(col.id, "") for r in ws.rows]
                    data_dict[col.name] = col_vals
                df = pd.DataFrame(data_dict)
                safe_name = ws.name[:31]
                df.to_excel(writer, sheet_name=safe_name, index=False)

        filename = f"{payload.title or 'LibRE_Sigma_Data'}.xlsx".replace(" ", "_")
        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel workbook: {str(e)}")
