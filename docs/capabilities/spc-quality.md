# Statistical Process Control (SPC) & Quality Engineering

LibRE Tab includes an industrial-grade quality control suite for process monitoring, stability analysis, and tolerance compliance.

---

## 1. Variables Control Charts

Used for continuous measurement data.

### Individuals & Moving Range ($I\text{-}MR$)
For continuous data with subgroup size $n = 1$:

$$\text{CL}_I = \bar{X}, \quad \text{UCL}_I = \bar{X} + 3 \frac{\overline{MR}}{d_2}, \quad \text{LCL}_I = \bar{X} - 3 \frac{\overline{MR}}{d_2}$$
$$\text{CL}_{MR} = \overline{MR}, \quad \text{UCL}_{MR} = D_4 \overline{MR}, \quad \text{LCL}_{MR} = D_3 \overline{MR}$$

### Subgroup Means & Ranges ($\bar{X}\text{-}R$ Chart)
For subgroup sizes $2 \le n \le 8$:

$$\text{CL}_{\bar{X}} = \bar{\bar{X}}, \quad \text{UCL}_{\bar{X}} = \bar{\bar{X}} + A_2 \bar{R}, \quad \text{LCL}_{\bar{X}} = \bar{\bar{X}} - A_2 \bar{R}$$
$$\text{CL}_R = \bar{R}, \quad \text{UCL}_R = D_4 \bar{R}, \quad \text{LCL}_R = D_3 \bar{R}$$

### Subgroup Means & Standard Deviations ($\bar{X}\text{-}S$ Chart)
For larger subgroup sizes ($n \ge 9$):

$$\text{CL}_{\bar{X}} = \bar{\bar{X}}, \quad \text{UCL}_{\bar{X}} = \bar{\bar{X}} + A_3 \bar{S}, \quad \text{LCL}_{\bar{X}} = \bar{\bar{X}} - A_3 \bar{S}$$
$$\text{CL}_S = \bar{S}, \quad \text{UCL}_S = B_4 \bar{S}, \quad \text{LCL}_S = B_3 \bar{S}$$

---

## 2. Attributes Control Charts

Used for discrete count and defect classification data:

| Chart | Characteristic Monitored | Subgroup Size | Control Limits Calculation |
| :--- | :--- | :--- | :--- |
| **$p$-Chart** | Proportion Defective | Variable or Constant | $\bar{p} \pm 3 \sqrt{\frac{\bar{p}(1-\bar{p})}{n_i}}$ |
| **$np$-Chart** | Number of Defectives | Constant ($n$) | $n\bar{p} \pm 3 \sqrt{n\bar{p}(1-\bar{p})}$ |
| **$c$-Chart** | Total Defects per Subgroup | Constant Area of Opportunity | $\bar{c} \pm 3 \sqrt{\bar{c}}$ |
| **$u$-Chart** | Defects per Unit | Variable Area of Opportunity | $\bar{u} \pm 3 \sqrt{\frac{\bar{u}}{n_i}}$ |

---

## 3. Out-of-Control Nelson Rules

All control charts automatically evaluate the standard 8 Nelson / Western Electric zone tests:

- **Rule 1**: 1 point $> 3\sigma$ from center line.
- **Rule 2**: 9 points in a row on the same side of the center line.
- **Rule 3**: 6 points in a row strictly increasing or decreasing (trend).
- **Rule 4**: 14 points in a row alternating up and down.
- **Rule 5**: 2 out of 3 points $> 2\sigma$ from center line (same side).
- **Rule 6**: 4 out of 5 points $> 1\sigma$ from center line (same side).
- **Rule 7**: 15 points in a row within $1\sigma$ of center line (stratification).
- **Rule 8**: 8 points in a row $> 1\sigma$ from center line (both sides).

---

## 4. Process Capability Analysis ($C_p, C_{pk}$)

Evaluates whether a stable process meets upper (USL) and lower (LSL) specification limits:

### Potential Capability ($C_p, C_{pk}$) & Overall Performance ($P_p, P_{pk}$)

$$C_p = \frac{\text{USL} - \text{LSL}}{6\hat{\sigma}_{\text{within}}}, \quad C_{pk} = \min\left(\frac{\text{USL} - \bar{x}}{3\hat{\sigma}_{\text{within}}}, \frac{\bar{x} - \text{LSL}}{3\hat{\sigma}_{\text{within}}}\right)$$
$$P_p = \frac{\text{USL} - \text{LSL}}{6 s_{\text{overall}}}, \quad P_{pk} = \min\left(\frac{\text{USL} - \bar{x}}{3 s_{\text{overall}}}, \frac{\bar{x} - \text{LSL}}{3 s_{\text{overall}}}\right)$$

### Capability Sixpack Report
Generates a consolidated 6-panel diagnostic dashboard:
1. Xbar or Individuals Chart
2. R, S, or Moving Range Chart
3. Last 25 Observations Run Plot
4. Capability Histogram with Normal Distribution Overlay
5. Normal Probability Plot (Quantile-Quantile)
6. Capability Metrics Summary ($C_p, C_{pk}, P_p, P_{pk}, \text{PPM}$ defect benchmarks)
