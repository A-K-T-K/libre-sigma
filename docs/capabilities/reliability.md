# Reliability Engineering & Life Data Analysis

LibRE Sigma provides statistical tools for analyzing failure time data, estimating component life expectancy, and modeling survival functions.

---

## 1. Parametric Lifetime Distribution Fitting

Fits failure time data using Maximum Likelihood Estimation (MLE):

### Weibull Distribution (2-Parameter & 3-Parameter)
The standard distribution for modeling mechanical, electronic, and material wear-out:

$$f(t) = \frac{\beta}{\eta} \left(\frac{t - \gamma}{\eta}\right)^{\beta - 1} \exp\left(-\left(\frac{t - \gamma}{\eta}\right)^\beta\right)$$

- **Shape Parameter ($\beta$)**:
  - $\beta < 1$: Infant mortality / decreasing failure rate (burn-in period).
  - $\beta = 1$: Constant failure rate (random exponential failures).
  - $\beta > 1$: Wear-out period / increasing failure rate (aging).
- **Scale Parameter ($\eta$)**: Characteristic life ($63.2\%$ point of cumulative failures).
- **Location Parameter ($\gamma$)**: Threshold / minimum guaranteed lifetime.

### Other Parametric Distributions
- **Lognormal**: Models chemical degradation, fatigue crack growth, and wear processes.
- **Exponential**: Models pure random failure mechanisms with constant failure rate $\lambda$.
- **Normal & Logistic**: Models standard symmetric failure distributions.

---

## 2. Non-Parametric Survival Analysis

### Kaplan-Meier Survival Estimator
Computes empirical product-limit survival probabilities for right-censored life data:

$$\hat{S}(t) = \prod_{t_i \le t} \left(1 - \frac{d_i}{n_i}\right)$$

Where $d_i$ represents the number of observed failure events at time $t_i$, and $n_i$ represents individuals at risk.

### Cumulative Hazard & Hazard Function
Estimates Nelson-Aalen cumulative hazard rates $H(t)$:

$$\hat{H}(t) = \sum_{t_i \le t} \frac{d_i}{n_i}$$

---

## 3. Reliability Metrics & Deliverables

- **Percentile Estimates ($B_{10}, B_{50}$ Life)**: Time by which $10\%$ or $50\%$ of the population is expected to fail.
- **Mean Time to Failure (MTTF / MTBF)**: Expected operational life.
- **Survival Plots & Hazard Plots**: Empirical and fitted curves with $95\%$ confidence bounds.
