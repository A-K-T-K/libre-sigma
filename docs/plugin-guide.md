# Plugin Developer Guide

LibRE Sigma features a schema-driven plugin architecture. Adding a new statistical test, quality tool, or DOE routine requires only creating a single Python module in `backend/app/plugins/modules/`.

The application automatically handles dynamic parameter schema generation, interactive modal dialog rendering, column pickers, top-menu mounting, session transcript formatting, and Plotly chart generation.

---

## 1. Anatomy of a Plugin

Every plugin consists of two key components:
1. **Parameter Schema (`BaseModel`)**: Defines user-configurable inputs, data types, validation rules, and UI widget types.
2. **Plugin Class (`AnalysisPlugin`)**: Defines metadata (ID, display name, menu path) and the computational logic in `execute()`.

```python
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
from ..base import AnalysisPlugin, AnalysisResult, TableResult

# 1. Define parameter schema
class MyAnalysisParams(BaseModel):
    sample_col: str = Field(
        ...,
        description="Measurement Column",
        json_schema_extra={"ui_type": "column_picker"}
    )
    conf_level: float = Field(
        0.95,
        ge=0.50,
        le=0.999,
        description="Confidence Level"
    )

# 2. Define plugin implementation
class MyAnalysisPlugin(AnalysisPlugin):
    id = "my_custom_analysis"
    name = "My Custom Analysis"
    menu_path = ["Stat", "Basic Statistics", "Custom Metric"]
    description = "Calculates custom statistical metrics."
    param_schema = MyAnalysisParams

    def execute(self, df: pd.DataFrame, params: MyAnalysisParams) -> AnalysisResult:
        data = df[params.sample_col].dropna().astype(float)
        mean_val = float(np.mean(data))
        std_val = float(np.std(data, ddof=1))
        
        # Build structured output table
        summary_table = TableResult(
            title="Descriptive Summary",
            headers=["Variable", "N", "Mean", "StdDev"],
            rows=[[params.sample_col, len(data), round(mean_val, 4), round(std_val, 4)]]
        )
        
        # Return structured analysis result
        return AnalysisResult(
            title=f"Analysis of {params.sample_col}",
            tables=[summary_table],
            text_output=f"Mean: {mean_val:.4f}\nStandard Deviation: {std_val:.4f}"
        )
```

---

## 2. Interactive UI Types

You can customize how input parameters are rendered in the dialog modal using `json_schema_extra={"ui_type": ...}`:

| `ui_type` | Rendered UI Widget | Python Type |
| :--- | :--- | :--- |
| `column_picker` | Interactive column selection input | `str` |
| `multi_column_picker` | Multi-select variable bucket | `List[str]` |
| `select` | Dropdown menu with defined choices | `Literal[...]` or `str` |
| `checkbox` | Boolean toggle switch | `bool` |
| `number` | Numeric stepper / float input | `int` or `float` |

---

## 3. Returning Interactive Charts

To render interactive Plotly figures in the session output, return a Plotly figure dictionary in `AnalysisResult`:

```python
import plotly.graph_objects as go

def execute(self, df: pd.DataFrame, params: MyParams) -> AnalysisResult:
    # Compute statistics...
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=data, name="Distribution", marker_color="#008450"))
    fig.update_layout(
        title="Custom Distribution Plot",
        xaxis_title=params.sample_col,
        yaxis_title="Frequency",
        template="plotly_white"
    )

    return AnalysisResult(
        title="Distribution Analysis",
        plotly_figure=fig.to_dict(),
        tables=[...]
    )
```

---

## 4. Automatic Discovery & Testing

1. Save your Python module in `backend/app/plugins/modules/<category>/your_plugin.py`.
2. Restart the backend or run:
   ```bash
   python -c "from app.plugins.loader import discover_and_load_plugins; discover_and_load_plugins('app.plugins.modules')"
   ```
3. Create a unit test under `tests/test_your_plugin.py` to verify calculations against known sample benchmarks.
