# Design of Experiments (DOE)

LibRE Tab supports standard industrial experimental design methodologies for parameter design, screening, and surface optimization.

---

## 1. Taguchi Methods (Robust Design)

Taguchi experimental designs use orthogonal arrays to optimize process performance while minimizing sensitivity to uncontrollable noise factors.

### Orthogonal Arrays Available
- **2-Level Arrays**: $L_4(2^3), L_8(2^7), L_{12}(2^{11}), L_{16}(2^{15}), L_{32}(2^{31})$
- **3-Level Arrays**: $L_9(3^4), L_{18}(2^1 \times 3^7), L_{27}(3^{13})$

### Signal-to-Noise (S/N) Ratio Metrics

=== "Larger is Better (e.g. Strength, Efficiency)"
    $$\eta = -10 \log_{10} \left(\frac{1}{n} \sum_{i=1}^n \frac{1}{y_i^2}\right)$$

=== "Smaller is Better (e.g. Wear, Defects, Noise)"
    $$\eta = -10 \log_{10} \left(\frac{1}{n} \sum_{i=1}^n y_i^2\right)$$

=== "Nominal is Best (e.g. Dimension, Target Voltage)"
    $$\eta = 10 \log_{10} \left(\frac{\bar{y}^2}{s^2}\right)$$

### Output Deliverables
- S/N Ratio Response Table with delta ranking of factor significance.
- Means Response Table.
- Interactive Main Effects Plots for S/N Ratios and Means.

---

## 2. Factorial Experiment Designs

### 2-Level Full & Fractional Factorial ($2^k, 2^{k-p}$)
- Evaluates main effects and high-order interaction terms ($A, B, AB, ABC$).
- Generators, confounding resolution (Resolution III, IV, V), and alias tables.
- **Pareto Chart of Standardized Effects**: Highlights statistically significant factors relative to the $t$-critical threshold.
- **Cube Plots & Interaction Plots**: Visualizes multi-factor combinations and non-parallel interaction slopes.

---

## 3. Response Surface Methodology (RSM)

Used for second-order quadratic modeling and optimization:

$$y = \beta_0 + \sum_{i=1}^k \beta_i x_i + \sum_{i=1}^k \beta_{ii} x_i^2 + \sum_{i < j} \beta_{ij} x_i x_j + \varepsilon$$

### Design Types
- **Central Composite Design (CCD)**: Full factorial cube points, axial/star points at distance $\alpha$, and center points for curvature estimation.
- **Box-Behnken Design (BBD)**: Spherical design requiring only 3 levels per factor without extreme corner runs.
- **Visual Outputs**: Interactive 2D Contour Maps and 3D Response Surface mesh plots.

---

## 4. Mixture Designs

For formulations where factor levels represent proportional components constrained to sum to 100%:

$$\sum_{i=1}^q x_i = 1, \quad x_i \ge 0$$

- **Simplex Lattice & Simplex Centroid** designs.
- Ternary contour plots and response trace plots.
