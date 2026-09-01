---
layout: home

hero:
  name: "LibRE Sigma"
  text: "Scientific Statistical Analysis & Reliability Engineering"
  tagline: "The open-source, local-first platform for Six Sigma, SPC control charts, Taguchi DOE, and Weibull life data analysis. A modern, free alternative to Minitab and JMP."
  actions:
    - theme: brand
      text: Get Started
      link: /how-to-use
    - theme: alt
      text: Explore Capabilities
      link: /capabilities/basic-statistics
    - theme: alt
      text: GitHub
      link: https://github.com/A-K-T-K/libre-sigma

features:
  - icon: 📊
    title: 120+ Statistical Analysis Plugins
    details: Complete inferential suite powered by NumPy, SciPy, Statsmodels, Scikit-Learn, and Lifelines. Includes ANOVA, GLM, Nonparametrics, and Time Series.
  - icon: 🎯
    title: Six Sigma & SPC Quality Control
    details: Variables & Attributes Control Charts (Xbar-R, I-MR, p, u), automated 8 Nelson zone rule detection, and Capability Sixpack (Cp, Cpk, Pp, Ppk).
  - icon: 🧪
    title: Industrial Design of Experiments
    details: Taguchi Orthogonal Arrays (L4-L27) with S/N ratios, 2^k Full and Fractional Factorials, Central Composite (CCD), Box-Behnken, and Mixture designs.
  - icon: ⏳
    title: Reliability & Life Data Analysis
    details: Parametric Weibull (2P/3P), Lognormal, Exponential fitting with MLE, plus non-parametric Kaplan-Meier survival curves and B10/B50 life estimation.
  - icon: ⚡
    title: High-Performance Canvas Spreadsheet
    details: Dual-header grid with named variables, formula evaluation (LN, STANDARDIZE), multi-sheet tabs, and sub-millisecond 60 FPS rendering.
  - icon: 🔒
    title: 100% Local-First & Zero Telemetry
    details: Zero cloud dependency, zero data transmission, and zero telemetry. All computations execute directly on your local machine with full privacy.
---

<div class="hero-image-container">
  <img src="/main_window.png" alt="LibRE Sigma Main Window - Statistical Analysis & Reliability Platform" />
</div>

<p align="center" style="margin-top: 1rem; color: var(--vp-c-text-2); font-size: 0.95rem;">
  <em>LibRE Sigma Desktop Interface: Project Navigator, Interactive Xbar-R Control Charts, Process Capability Sixpack, and Multi-Sheet Data Grid</em>
</p>

---

## Quick Start (1-Step Launch)

Run LibRE Sigma instantly across Windows, macOS, or Linux using the universal launcher:

::: code-group

```bash [Quick Start]
# 1. Clone the repository
git clone https://github.com/A-K-T-K/libre-sigma.git
cd libre-sigma

# 2. Launch universal desktop application
python start.py
```

```bash [Native Desktop (Tauri)]
# Run native Tauri desktop shell in hot-reload dev mode
npm run tauri:dev
```

```bash [Web Browser Mode]
# Run in local web browser mode (FastAPI + Vite)
python start.py --web
```

:::

---

## Platform Highlights

::: tip 100% Free & Open Source
LibRE Sigma is released under the permissive **MIT License**. It is freely usable for academic research, industrial quality engineering, and commercial manufacturing.
:::

| Capability Area | Core Analytical Methods | Key Output Deliverables |
| :--- | :--- | :--- |
| **Basic Statistics** | Descriptive, 1-Sample & 2-Sample $t$-tests, Paired $t$, 1-Way & 2-Way ANOVA, GLM | Summary statistics, $p$-values, confidence intervals, residual plots |
| **SPC Quality Control** | $\bar{X}\text{-}R$, $\bar{X}\text{-}S$, $I\text{-}MR$, $p$, $np$, $c$, $u$, Laney $p'$, Laney $u'$ | Control charts, 8 Nelson rule alarms, $C_p, C_{pk}, P_p, P_{pk}$ |
| **Design of Experiments** | Taguchi $L_4\text{--}L_{27}$, $2^k$ Factorial, Response Surface (CCD, Box-Behnken), Mixture | S/N response tables, Pareto effects, 2D contour & 3D surface plots |
| **Reliability Engineering** | Weibull 2P/3P, Lognormal, Exponential, Kaplan-Meier, Nelson-Aalen | Hazard & survival curves, $B_{10}/B_{50}$ life, MTTF/MTBF benchmarks |
| **Data Engine** | Multi-sheet workbooks, formula bar, dual header labels, sorting, subsetting, recoding | `.lsg` project files, `.xlsx` import/export, CSV/TSV interchange |

---

## Citation Reference

If you use LibRE Sigma in academic work, research papers, or industrial publications, please cite:

```bibtex
@software{libresigma2026,
  author = {LibRE Sigma Contributors},
  title = {LibRE Sigma: Open-Source Statistical Analysis & Reliability Engineering Platform},
  year = {2026},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.22093338},
  url = {https://github.com/A-K-T-K/libre-sigma}
}
```
