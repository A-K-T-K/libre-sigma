# LibRE Sigma Documentation

<p align="center">
  <img src="assets/logo.svg" alt="LibRE Sigma Logo" width="100" height="100" />
</p>

Welcome to the official documentation for **LibRE Sigma**, an open-source, local-first desktop application for statistical analysis, reliability engineering, design of experiments (DOE), and statistical process control (SPC).

LibRE Sigma is designed to provide an open, modern alternative to commercial statistical software packages (such as Minitab® and JMP®), combining a spreadsheet interface with Python scientific computing libraries.

---

## Key Capabilities

!!! success "Comprehensive Statistical Engine"
    Over 120 built-in analytical plugins powered by **NumPy**, **SciPy**, **Statsmodels**, **Scikit-Learn**, and **Lifelines**. Includes ANOVA, GLM, Nonparametric tests, and Time Series models.

!!! info "Six Sigma & Quality Engineering"
    Full support for Variables and Attributes Control Charts ($\bar{X}\text{-}R$, $I\text{-}MR$, $p$, $u$), automated Nelson rule detection, Process Capability ($C_p, C_{pk}, P_p, P_{pk}$), and Gage R&R studies.

!!! example "Design of Experiments (DOE)"
    Full and fractional $2^k$ factorial designs, Central Composite Designs (CCD), Box-Behnken response surface models, Simplex mixture designs, and Taguchi orthogonal arrays ($L_4\text{--}L_{27}$).

!!! note "100% Offline & Local-First"
    Zero cloud transmission and zero telemetry. All computations, datasets, and visualizations are processed entirely on your local machine.

---

## Quick Start (1-Step Launch)

```bash
git clone https://github.com/A-K-T-K/libre-tab.git
cd libre-tab

# Run universal launcher (Windows, macOS, Linux):
python start.py
```

---

## Quick Navigation

- **[How to Use Guide](how-to-use.md)**: A complete walkthrough of worksheets, importing data, running statistical analyses, and generating reports.
- **[System Architecture](architecture.md)**: Technical overview of the Tauri desktop shell, Glide Data Grid frontend, and FastAPI analytical sidecar.
- **[Statistical Capabilities](capabilities/basic-statistics.md)**: Detailed algorithms, assumptions, and formulas across all statistical modules.
- **[Plugin Development Guide](plugin-guide.md)**: Step-by-step tutorial on extending LibRE Sigma with custom Python analysis plugins.

---

## System Requirements

| Component | Minimum Requirement | Recommended |
| :--- | :--- | :--- |
| **Operating System** | Windows 10/11 (64-bit), macOS 11+, Linux (Ubuntu 20.04+) | Windows 11 / macOS 13+ |
| **Memory (RAM)** | 4 GB | 8 GB or more |
| **Python** | Python 3.10+ | Python 3.11+ |
| **Node.js** | Node.js 18+ (for building from source) | Node.js 20 LTS |
| **Display Resolution** | 1280 × 800 | 1920 × 1080 or higher |
