from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import pandas as pd
from pydantic import BaseModel, Field


class TableResult(BaseModel):
    title: str
    headers: List[str]
    rows: List[List[Any]]
    notes: Optional[List[str]] = None


class AnalysisResult(BaseModel):
    title: str
    subtitle: Optional[str] = None
    text_output: Optional[str] = None
    tables: List[TableResult] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    plotly_figure: Optional[Dict[str, Any]] = None
    plotly_figures: Optional[List[Dict[str, Any]]] = None
    action_type: Optional[str] = None  # e.g., 'worksheet_overwrite'
    worksheet_data: Optional[Dict[str, Any]] = None  # { "name": str, "columns": [...], "rows": [...] }


class PluginManifestItem(BaseModel):
    id: str
    name: str
    menu_path: List[str]
    description: str
    param_schema: Dict[str, Any]


class AnalysisPlugin(ABC):
    id: str
    name: str
    menu_path: List[str]
    description: str
    param_schema: type[BaseModel]

    @abstractmethod
    def execute(self, df: pd.DataFrame, params: BaseModel) -> AnalysisResult:
        """
        Execute statistical analysis on the provided DataFrame using params.
        """
        pass
