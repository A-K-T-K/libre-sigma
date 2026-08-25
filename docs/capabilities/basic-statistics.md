# Basic Statistics & Inferential Methods

LibRE Sigma provides a complete suite of classical parametric and non-parametric statistical hypothesis tests, estimation procedures, and descriptive summaries.

---

## 1. Descriptive Statistics

Computes central tendency, dispersion, and shape parameters for one or more continuous variables:

- **Central Tendency**: Mean, Trimmed Mean (5%), Median, Mode.
- **Dispersion**: Standard Deviation ($s$), Variance ($s^2$), Standard Error of Mean ($\text{SE}_{\bar{x}}$), Interquartile Range ($\text{IQR}$), Range ($\text{Max} - \text{Min}$).
- **Shape & Distribution**: Skewness, Kurtosis, Coefficient of Variation ($\text{CV}$).
- **Graphical Displays**: Histogram with normal curve overlay, Boxplot with outlier detection (1.5 × IQR rule), and Individual Value Plot.

---

## 2. Hypothesis Testing for Means

### 1-Sample $t$-Test
Tests whether the population mean $\mu$ equals a hypothesized value $\mu_0$:

$$t = \frac{\bar{x} - \mu_0}{s / \sqrt{n}}, \quad \text{df} = n - 1$$

- **Confidence Intervals**: $100(1-\alpha)\%$ two-sided or one-sided bounds.
- **Alternative Hypotheses**: Less than ($\mu < \mu_0$), greater than ($\mu > \mu_0$), or two-sided ($\mu \neq \mu_0$).

### 2-Sample Independent $t$-Test
Compares the means of two independent groups ($\mu_1 - \mu_2$):

=== "Equal Variances Assumed (Pooled)"
    $$t = \frac{\bar{x}_1 - \bar{x}_2}{s_p \sqrt{\frac{1}{n_1} + \frac{1}{n_2}}}, \quad s_p = \sqrt{\frac{(n_1-1)s_1^2 + (n_2-1)s_2^2}{n_1 + n_2 - 2}}$$

=== "Unequal Variances (Welch's Satterthwaite Correction)"
    $$t = \frac{\bar{x}_1 - \bar{x}_2}{\sqrt{\frac{s_1^2}{n_1} + \frac{s_2^2}{n_2}}}, \quad \text{df} = \frac{\left(\frac{s_1^2}{n_1} + \frac{s_2^2}{n_2}\right)^2}{\frac{(s_1^2/n_1)^2}{n_1-1} + \frac{(s_2^2/n_2)^2}{n_2-1}}$$

### Paired $t$-Test
Evaluates mean differences for matched pairs or repeated measures:

$$t = \frac{\bar{d} - \mu_d}{s_d / \sqrt{n}}$$

---

## 3. Analysis of Variance (ANOVA) & Linear Models

### One-Way ANOVA
Tests for differences among $k$ group means:

$$\text{SS}_{\text{Total}} = \text{SS}_{\text{Factor}} + \text{SS}_{\text{Error}}, \quad F = \frac{\text{MS}_{\text{Factor}}}{\text{MS}_{\text{Error}}}$$

- **Post-Hoc Multiple Comparisons**: Tukey's Honestly Significant Difference (HSD), Fisher's LSD, and Dunnett's test against a control group.
- **Model Diagnostics**: Residual vs. Fits plot, Normal Probability plot of residuals, Residual vs. Order plot.

### General Linear Model (GLM) & Two-Way ANOVA
Handles crossed and nested factors, unbalanced replication, covariates, and interaction terms ($A \times B$).

---

## 4. Proportions & Rates

- **1-Proportion & 2-Proportion Tests**: Normal approximation and exact Fisher/binomial tests.
- **1-Variance & 2-Variances Tests**: Chi-Square test for one variance, Fisher's F-test, Levene's test, and Bartlett's test for homogeneity of variances across groups.
- **1-Sample & 2-Sample Poisson Rate Tests**: Evaluates occurrence rates per unit of inspection.
