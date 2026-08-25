<p align="center">
  <img src="assets/logo.svg" alt="LibRE Tab Logo - Statistical Analysis and Reliability Engineering Platform" width="128" height="128" />
</p>

<h1 align="center">LibRE Tab</h1>

<p align="center">
  <strong>Open-Source Statistical Analysis, Six Sigma & Reliability Engineering Desktop Platform</strong>
</p>

<p align="center">
  <a href="https://a-k-t-k.github.io/libre-tab/"><img src="https://img.shields.io/badge/Docs-Live%20Guide-008450?style=for-the-badge&logo=material-for-mkdocs&logoColor=white" alt="Documentation"></a>
  <a href="#getting-started"><img src="https://img.shields.io/badge/Status-v1.0.0-008450?style=for-the-badge" alt="Release Status"></a>
  <a href="#architecture-overview"><img src="https://img.shields.io/badge/Platform-Tauri%20%7C%20Rust%20%7C%20React-0078d4?style=for-the-badge" alt="Platform"></a>
  <a href="#architecture-overview"><img src="https://img.shields.io/badge/Engine-Python%20%7C%20SciPy%20%7C%20Statsmodels-3776AB?style=for-the-badge" alt="Engine"></a>
  <a href="#license"><img src="https://img.shields.io/badge/License-MIT-008450?style=for-the-badge" alt="License"></a>
  <a href="#architecture-overview"><img src="https://img.shields.io/badge/Privacy-100%25%20Offline%20%26%20Local-8E24AA?style=for-the-badge" alt="Local First"></a>
</p>

<p align="center">
  LibRE Tab is an open-source, local-first statistical analysis desktop platform for quality engineers, data scientists, and researchers. Built with Rust (Tauri), React, and scientific Python (NumPy, SciPy, Statsmodels), LibRE Tab provides a modern alternative to commercial statistical suites like Minitab® and JMP® for <strong>Six Sigma</strong>, <strong>Statistical Process Control (SPC)</strong>, <strong>Design of Experiments (DOE)</strong>, and <strong>Weibull Reliability Engineering</strong>.
</p>

---

## Architecture Overview

LibRE Tab utilizes a decoupled client-server architecture packaged as a desktop binary:

- **Desktop Shell**: [Tauri](https://tauri.app/) (Rust) managing application windows, OS lifecycle, and local sidecar processes.
- **Frontend Application**: React 18, TypeScript, Fluent UI, and [Glide Data Grid](https://github.com/glideapps/glide-data-grid) for high-performance multi-sheet tabular data editing.
- **Visualizations**: [Plotly.js](https://plotly.com/javascript/) for interactive analytical charts and publication-grade exports.
- **Analytical Engine**: FastAPI application executing computational workflows using NumPy, SciPy, Statsmodels, Scikit-Learn, and Lifelines.
- **Local-First Execution**: All calculations and file I/O operations execute locally on the host machine without external network dependencies.

```
+-------------------------------------------------------------+
|                     LibRE Tab Frontend                      |
| (React, TypeScript, Glide Data Grid, Fluent UI, Plotly.js)  |
+------------------------------+------------------------------+
                               | IPC / Local HTTP (Port 8000)
+------------------------------v------------------------------+
|                   Python Analytical Engine                  |
|   (FastAPI, NumPy, SciPy, Statsmodels, Scikit-Learn, Pandas)|
+-------------------------------------------------------------+
```

---

## Statistical Capabilities

### Basic Statistics & Inference
- **Hypothesis Testing**: 1-sample and 2-sample $t$-tests (independent, Welch's correction, pooled variance), paired $t$-test, 1-sample and 2-sample $Z$-tests.
- **Proportion & Variance Tests**: 1-proportion and 2-proportion tests, 1-variance and 2-variances tests (F-test, Levene's test, Bartlett's test), Poisson rate comparisons.
- **Correlation & Association**: Pearson product-moment, Spearman rank correlation, covariance matrix estimation, contingency tables, and Chi-square goodness-of-fit.

### Linear Models & ANOVA
- **Regression**: Simple and multiple linear regression, polynomial fitting, fitted line plots with confidence/prediction intervals, logistic regression (binary, nominal, ordinal).
- **Analysis of Variance**: One-way and two-way ANOVA with balanced and unbalanced designs, General Linear Models (GLM), post-hoc multiple comparison procedures (Tukey HSD, Fisher LSD).

### Design of Experiments (DOE)
- **Factorial Designs**: 2-level full and fractional factorial designs ($2^{k}$ and $2^{k-p}$), Plackett-Burman screening designs.
- **Response Surface Methodology (RSM)**: Central Composite Designs (CCD), Box-Behnken designs, 2D contour and 3D response surface plots.
- **Mixture Designs**: Simplex-lattice, simplex-centroid, and constrained mixture experiments.
- **Taguchi Methods**: Standard orthogonal arrays ($L_4, L_8, L_9, L_{12}, L_{16}, L_{18}, L_{27}$), Signal-to-Noise (S/N) ratio calculations (Larger-the-Better, Smaller-the-Better, Nominal-the-Best), response tables, and main effects plots.

### Statistical Process Control (SPC) & Quality Engineering
- **Variables Control Charts**: Individuals and Moving Range ($I\text{-}MR$, $Z\text{-}MR$), Subgroup Means and Ranges ($\bar{X}\text{-}R$), Subgroup Means and Standard Deviations ($\bar{X}\text{-}S$).
- **Attributes Control Charts**: Proportion defective ($p$), count defective ($np$), defects per unit ($u$), total defects ($c$), with configurable out-of-control zone tests (Nelson/Western Electric rules).
- **Specialized Charts**: EWMA, CUSUM, $g$-charts, $t$-charts, Hotelling's $T^2$ multivariate control charts.
- **Process Capability Analysis**: Normal and non-normal capability evaluation ($C_p$, $C_{pk}$, $P_p$, $P_{pk}$, Z-scores, PPM benchmarks, Sixpack summaries).

### Reliability & Life Data Analysis
- **Distribution Fitting**: Parametric lifetime models including Weibull (2-parameter and 3-parameter), Lognormal, Exponential, and Normal distributions with maximum likelihood estimation.
- **Survival Analysis**: Non-parametric Kaplan-Meier survival curves, cumulative hazard estimation, and Cox proportional hazards regression.

---

## Workspace & I/O Specifications

- **Spreadsheet Engine**: Multi-sheet grid supporting numeric, categorical text, and date-time data formats.
- **Formulas & Transformations**: Dynamic column-level formula bar supporting mathematical operations, standard functions, standardization, and conditional recoding.
- **Data Manipulation**: Patterned data generation, multi-key sorting, column stacking/unstacking, value/range recoding, and condition-based worksheet subsetting.
- **File Formats**:
  - Native LibRE Tab Project format (`.ltb`, JSON-based state serialization including multi-sheet data, column metadata, and session history).
  - Microsoft Excel import and multi-sheet export (`.xlsx`, `.xls`).
  - Delimited text files (`.csv`, `.tsv`, `.txt`).
  - Formatted session transcripts (`.txt`) and PDF print reports.

---

## Getting Started

### Prerequisites
- **Python**: v3.10 or higher
- **Node.js**: v18.0 or higher
- **Rust / Cargo**: Optional (required only for building native Tauri desktop release binaries)

---

### Quick Start (Universal 1-Step Launch)

Clone the repository and run the cross-platform launcher. It automatically verifies your environment, installs missing dependencies, and opens the application:

```bash
git clone https://github.com/A-K-T-K/libre-tab.git
cd libre-tab

# Universal (Windows, macOS, Linux):
python start.py

# Or Windows quick launch (double-click from File Explorer):
start.bat

# Or macOS / Linux:
chmod +x start.sh && ./start.sh
```

---

### Manual Setup (Optional)

If you prefer setting up frontend and backend services separately:

#### 1. Backend Service
```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Start the computational backend server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### 3. Frontend Application
In a separate terminal window:
```bash
cd frontend

# Install Node dependencies
npm install

# Start the Vite development server
npm run dev
```
Navigate to `http://localhost:5173` in a web browser.

#### 4. Running as a Native Desktop App
```bash
# Development mode with Tauri shell
npm run tauri:dev

# Build production desktop installers
npm run tauri:build
```

---

## Directory Structure

```
libre-tab/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI server entry point and CORS setup
│   │   ├── plugins/
│   │   │   ├── base.py          # Abstract plugin classes and schema definitions
│   │   │   ├── registry.py      # Dynamic plugin discovery and manifest generator
│   │   │   └── modules/         # Modular statistical analysis plugins
│   │   │       ├── basic_statistics/
│   │   │       ├── regression/
│   │   │       ├── doe/
│   │   │       ├── spc/
│   │   │       └── reliability/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/          # Layout, worksheet grid, session pane, dialogs
│   │   ├── hooks/               # Undo/redo shortcuts, unsaved changes guard
│   │   ├── services/            # Backend API communication and heartbeat monitor
│   │   ├── store/               # Zustand stores (worksheet, session, plugins)
│   │   ├── types/               # TypeScript interfaces and data models
│   │   └── utils/               # Formula engine, project I/O, formatters
│   ├── src-tauri/               # Rust desktop shell configuration and lifecycle
│   └── package.json
└── tests/                       # Statistical verification and integration test suites
```

---

## Plugin Architecture

New statistical methods and analytical routines can be added as standalone Python modules in `backend/app/plugins/modules/`. The application automatically discovers modules, generates input dialogs based on Pydantic schemas, and mounts actions into the top menu.

```python
from pydantic import BaseModel, Field
import pandas as pd
from ..base import AnalysisPlugin, AnalysisResult, TableResult

class MetricParams(BaseModel):
    column: str = Field(..., description="Measurement Column", json_schema_extra={"ui_type": "column_picker"})
    alpha: float = Field(0.05, description="Significance Level")

class CustomMetricPlugin(AnalysisPlugin):
    id = "custom_metric"
    name = "Custom Metric Analysis"
    menu_path = ["Stat", "Basic Statistics", "Custom Metric"]
    description = "Computes summary metrics and distribution parameters."
    param_schema = MetricParams

    def execute(self, df: pd.DataFrame, params: MetricParams) -> AnalysisResult:
        series = df[params.column].dropna().astype(float)
        mean_val = float(series.mean())
        std_val = float(series.std(ddof=1))
        
        table = TableResult(
            title="Summary Statistics",
            headers=["Variable", "N", "Mean", "StdDev"],
            rows=[[params.column, len(series), round(mean_val, 4), round(std_val, 4)]]
        )
        return AnalysisResult(
            title="Custom Metric Summary",
            tables=[table],
            session_text=f"Variable: {params.column}\nN = {len(series)}\nMean = {mean_val:.4f}\nStd Dev = {std_val:.4f}"
        )
```

---

## Statistical Module Matrix

| Domain | Key Capabilities & Algorithms | Common Use Cases |
| :--- | :--- | :--- |
| **Statistical Process Control (SPC)** | $\bar{X}\text{-}R$, $\bar{X}\text{-}S$, $I\text{-}MR$, $p$, $np$, $c$, $u$, CUSUM, EWMA, Hotelling $T^2$, Nelson Rules | Manufacturing quality control, process stability monitoring |
| **Process Capability** | $C_p$, $C_{pk}$, $P_p$, $P_{pk}$, Z-Bench, Non-normal (Weibull/Box-Cox) Capability, Sixpack | Six Sigma DMAIC, tolerance compliance, defect rate reduction |
| **Design of Experiments (DOE)** | Full/Fractional $2^k$, Taguchi $L_4\text{--}L_{27}$, Central Composite, Box-Behnken, Mixture | Industrial parameter optimization, robust product design |
| **Reliability & Life Data** | Weibull (2P/3P), Lognormal, Exponential, Kaplan-Meier, Cox Proportional Hazards | Accelerated life testing (ALT), MTBF estimation, failure modeling |
| **Hypothesis Testing & ANOVA** | 1/2-sample $t$-tests, Paired $t$, GLM, One-Way/Two-Way ANOVA, Tukey/Fisher Post-Hoc | Scientific research, A/B testing, clinical data analysis |
| **Regression & Multivariate** | Multiple Linear Regression, Binary/Nominal Logistic, PCA, Cluster Analysis | Predictive modeling, root-cause analysis, dimensionality reduction |

---

## Testing

Run the automated test suite to verify statistical calculations and data pipelines:

```bash
python tests/test_master_suite.py
python tests/test_anova_suite.py
python tests/test_regression_suite.py
python tests/test_quality_tools.py
python tests/test_spc_plugins.py
```

---

## License

This project is licensed under the [MIT License](LICENSE).

