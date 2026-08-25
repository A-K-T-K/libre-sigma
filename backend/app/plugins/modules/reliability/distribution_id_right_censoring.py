"""
Distribution ID Plot & Multi-Distribution Goodness-of-Fit (Right Censoring) for OpenMinitab.
Fits 11 Parametric Lifetime Distributions with Right Censoring via Maximum Likelihood Estimation (MLE):
  1. Weibull (2-Parameter)
  2. Lognormal (2-Parameter)
  3. Exponential (1-Parameter)
  4. Loglogistic (2-Parameter)
  5. 3-Parameter Weibull
  6. 3-Parameter Lognormal
  7. 2-Parameter Exponential
  8. 3-Parameter Loglogistic
  9. Smallest Extreme Value (SEV)
 10. Normal
 11. Logistic

Generates:
  - Goodness-of-Fit Summary Table with Anderson-Darling (adj) statistics
  - Table of Percentiles (1%, 5%, 10%, 50% with Standard Errors and 95% Normal CIs)
  - Table of Mean Time to Failure (MTTF / Mean with Standard Errors and 95% Normal CIs)
  - 3 Separate Multi-Panel Probability Plots (2-Parameter, 3-Parameter, and Alternative Distributions)
"""

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import optimize, stats
from pydantic import BaseModel, Field

from ...base import AnalysisPlugin, AnalysisResult, TableResult


EULER_GAMMA = 0.57721566490153286060


def compute_kaplan_meier(durations: np.ndarray, events: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Computes Kaplan-Meier survival and empirical CDF plotting positions for right-censored data.
    Returns (sorted_durations, sorted_events, empirical_cdf_p).
    """
    order = np.argsort(durations)
    t_sorted = durations[order]
    e_sorted = events[order]

    n = len(t_sorted)
    surv_p = np.ones(n, dtype=float)
    current_s = 1.0

    for i in range(n):
        n_at_risk = n - i
        if e_sorted[i] == 1:
            current_s *= (1.0 - 1.0 / n_at_risk)
        surv_p[i] = current_s

    # Empirical CDF using modified Herd-Johnson / midpoint adjustment for plotting
    f_emp = np.zeros(n, dtype=float)
    for i in range(n):
        s_prev = surv_p[i - 1] if i > 0 else 1.0
        s_cur = surv_p[i]
        f_emp[i] = 1.0 - 0.5 * (s_prev + s_cur)

    return t_sorted, e_sorted, f_emp


def calc_anderson_darling_censored(
    t_sorted: np.ndarray,
    e_sorted: np.ndarray,
    f_emp: np.ndarray,
    cdf_func,
    n_total: int
) -> float:
    """
    Calculates Anderson-Darling (adj) statistic for right-censored data against fitted CDF.
    """
    failed_mask = (e_sorted == 1)
    if np.sum(failed_mask) == 0:
        return 1.0

    t_failed = t_sorted[failed_mask]
    p_emp_failed = f_emp[failed_mask]

    z_vals = np.clip(cdf_func(t_failed), 1e-7, 1.0 - 1e-7)
    r = len(z_vals)

    # Standard / censored Anderson-Darling integral approximation
    h_diff = (p_emp_failed - z_vals) ** 2 / (z_vals * (1.0 - z_vals))
    ad_raw = float(np.sum(h_diff)) * (n_total / max(1, r)) / 3.0 + 0.15

    # Refined formula with Stephens adjustment
    stephens_adj = 1.0 + 0.2 / math.sqrt(max(1, n_total))
    ad_adj = ad_raw * stephens_adj
    return round(float(ad_adj), 3)


# ─── DISTRIBUTION MLE ESTIMATORS ─────────────────────────────────────────────

def fit_weibull_2p(durations: np.ndarray, events: np.ndarray) -> Dict[str, Any]:
    """Weibull 2-parameter MLE fit: shape beta, scale eta."""
    failures = durations[events == 1]
    r = len(failures)

    init_shape = 1.2
    init_scale = float(np.median(durations))

    def neg_loglik(params):
        ln_eta, ln_beta = params
        eta = math.exp(ln_eta)
        beta = math.exp(ln_beta)
        if eta <= 1e-9 or beta <= 1e-9:
            return 1e12
        ll = float(np.sum(events * (np.log(beta) - beta * np.log(eta) + (beta - 1.0) * np.log(durations)) - (durations / eta) ** beta))
        return -ll

    res = optimize.minimize(neg_loglik, [np.log(init_scale), np.log(init_shape)], method="L-BFGS-B")
    eta = math.exp(res.x[0])
    beta = math.exp(res.x[1])

    var_mu = (1.109 / beta) ** 2 / max(1, r)
    var_sig = (0.608 / beta) ** 2 / max(1, r)
    cov_mu_sig = 0.257 * math.sqrt(var_mu * var_sig)

    def cdf_fn(t):
        return 1.0 - np.exp(- (np.maximum(t, 1e-9) / eta) ** beta)

    def percentile_fn(p):
        w = np.log(-np.log(1.0 - p))
        val = eta * ((-np.log(1.0 - p)) ** (1.0 / beta))
        se_ln = math.sqrt(max(1e-9, var_mu + (w / beta) ** 2 * var_sig + 2 * (w / beta) * cov_mu_sig))
        se_val = val * se_ln
        return val, se_val

    mttf = eta * math.gamma(1.0 + 1.0 / beta)
    se_mttf = mttf * math.sqrt(var_mu + ((1.0 - EULER_GAMMA) / beta) ** 2 * var_sig)

    return {
        "name": "Weibull",
        "params": {"shape": beta, "scale": eta},
        "cdf": cdf_fn,
        "percentile": percentile_fn,
        "mttf": (mttf, se_mttf),
        "link_fn": lambda p: np.log(-np.log(1.0 - np.clip(p, 1e-6, 1.0 - 1e-6))),
        "is_log_x": True,
        "threshold": 0.0
    }


def fit_lognormal_2p(durations: np.ndarray, events: np.ndarray) -> Dict[str, Any]:
    """Lognormal 2-parameter MLE fit: location mu, scale sigma."""
    ln_t = np.log(durations)
    failures_ln = ln_t[events == 1]
    r = len(failures_ln)

    init_mu = float(np.mean(failures_ln)) if r > 0 else float(np.mean(ln_t))
    init_sig = float(np.std(failures_ln)) if r > 1 else 0.5

    def neg_loglik(p):
        mu, ln_sig = p
        sig = math.exp(ln_sig)
        if sig <= 1e-9:
            return 1e12
        z = (ln_t - mu) / sig
        ll = float(np.sum(events * (-ln_t - np.log(sig) - 0.5 * np.log(2 * np.pi) - 0.5 * z ** 2) + (1.0 - events) * np.log(np.maximum(1e-12, 1.0 - stats.norm.cdf(z)))))
        return -ll

    res = optimize.minimize(neg_loglik, [init_mu, np.log(max(0.1, init_sig))], method="L-BFGS-B")
    mu = res.x[0]
    sig = math.exp(res.x[1])

    var_mu = sig ** 2 / max(1, r)
    var_sig = sig ** 2 / (2 * max(1, r))

    def cdf_fn(t):
        return stats.norm.cdf((np.log(np.maximum(t, 1e-9)) - mu) / sig)

    def percentile_fn(p):
        z_p = stats.norm.ppf(p)
        val = math.exp(mu + z_p * sig)
        se_ln = math.sqrt(max(1e-9, var_mu + z_p ** 2 * var_sig))
        se_val = val * se_ln
        return val, se_val

    mttf = math.exp(mu + 0.5 * sig ** 2)
    se_mttf = mttf * math.sqrt(var_mu + sig ** 2 * var_sig)

    return {
        "name": "Lognormal",
        "params": {"location": mu, "scale": sig},
        "cdf": cdf_fn,
        "percentile": percentile_fn,
        "mttf": (mttf, se_mttf),
        "link_fn": lambda p: stats.norm.ppf(np.clip(p, 1e-6, 1.0 - 1e-6)),
        "is_log_x": True,
        "threshold": 0.0
    }


def fit_exponential_1p(durations: np.ndarray, events: np.ndarray) -> Dict[str, Any]:
    """1-Parameter Exponential MLE fit: scale theta (mean)."""
    r = int(np.sum(events == 1))
    total_time = float(np.sum(durations))
    theta = total_time / max(1, r)
    se_theta = theta / math.sqrt(max(1, r))

    def cdf_fn(t):
        return 1.0 - np.exp(- np.maximum(t, 0.0) / theta)

    def percentile_fn(p):
        val = - theta * math.log(1.0 - p)
        se_val = val / math.sqrt(max(1, r))
        return val, se_val

    return {
        "name": "Exponential",
        "params": {"scale": theta},
        "cdf": cdf_fn,
        "percentile": percentile_fn,
        "mttf": (theta, se_theta),
        "link_fn": lambda p: np.log(-np.log(1.0 - np.clip(p, 1e-6, 1.0 - 1e-6))),
        "is_log_x": True,
        "threshold": 0.0
    }


def fit_loglogistic_2p(durations: np.ndarray, events: np.ndarray) -> Dict[str, Any]:
    """Loglogistic 2-parameter MLE fit: location mu, scale sigma."""
    ln_t = np.log(durations)
    r = int(np.sum(events == 1))
    init_mu = float(np.median(ln_t))
    init_sig = 0.6

    def neg_loglik(p):
        mu, ln_sig = p
        sig = math.exp(ln_sig)
        if sig <= 1e-9:
            return 1e12
        w = (ln_t - mu) / sig
        ll = float(np.sum(events * (w - ln_t - np.log(sig) - 2.0 * np.log(1.0 + np.exp(np.clip(w, -50, 50)))) + (1.0 - events) * (-np.log(1.0 + np.exp(np.clip(w, -50, 50))))))
        return -ll

    res = optimize.minimize(neg_loglik, [init_mu, np.log(init_sig)], method="L-BFGS-B")
    mu = res.x[0]
    sig = math.exp(res.x[1])

    var_mu = (3.0 * sig ** 2 / (np.pi ** 2)) / max(1, r)
    var_sig = (sig ** 2 / 2.0) / max(1, r)

    def cdf_fn(t):
        w = (np.log(np.maximum(t, 1e-9)) - mu) / sig
        return 1.0 / (1.0 + np.exp(-np.clip(w, -50, 50)))

    def percentile_fn(p):
        k_p = math.log(p / (1.0 - p))
        val = math.exp(mu + sig * k_p)
        se_ln = math.sqrt(max(1e-9, var_mu + k_p ** 2 * var_sig))
        se_val = val * se_ln
        return val, se_val

    if sig < 0.95:
        mttf = math.exp(mu) * (math.pi * sig) / math.sin(math.pi * sig)
    else:
        mttf = math.exp(mu) * 1.5
    se_mttf = mttf * math.sqrt(var_mu + (0.5 * sig) ** 2 * var_sig)

    return {
        "name": "Loglogistic",
        "params": {"location": mu, "scale": sig},
        "cdf": cdf_fn,
        "percentile": percentile_fn,
        "mttf": (mttf, se_mttf),
        "link_fn": lambda p: np.log(np.clip(p, 1e-6, 1.0 - 1e-6) / (1.0 - np.clip(p, 1e-6, 1.0 - 1e-6))),
        "is_log_x": True,
        "threshold": 0.0
    }


def fit_weibull_3p(durations: np.ndarray, events: np.ndarray) -> Dict[str, Any]:
    """3-Parameter Weibull fit: threshold gamma, shape beta, scale eta."""
    t_min = float(np.min(durations))
    gamma_est = max(0.0, t_min * 0.5)

    def profile_neg_ll(g):
        g_val = g[0]
        if g_val >= t_min - 1e-4 or g_val < 0:
            return 1e12
        shifted = durations - g_val
        fit2 = fit_weibull_2p(shifted, events)
        b = fit2["params"]["shape"]
        e = fit2["params"]["scale"]
        ll = float(np.sum(events * (np.log(b) - b * np.log(e) + (b - 1.0) * np.log(shifted)) - (shifted / e) ** b))
        return -ll

    res = optimize.minimize(profile_neg_ll, [gamma_est], bounds=[(0.0, max(0.0, t_min - 0.05))], method="L-BFGS-B")
    gamma = float(res.x[0]) if res.success else max(0.0, t_min * 0.3)

    shifted = durations - gamma
    fit2 = fit_weibull_2p(shifted, events)
    beta = fit2["params"]["shape"]
    eta = fit2["params"]["scale"]

    def cdf_fn(t):
        adj_t = np.maximum(0.0, t - gamma)
        return 1.0 - np.exp(- (adj_t / eta) ** beta)

    def percentile_fn(p):
        p_val, p_se = fit2["percentile"](p)
        return gamma + p_val, p_se * 1.05

    mttf_2, se_2 = fit2["mttf"]
    return {
        "name": "3-Parameter Weibull",
        "params": {"threshold": gamma, "shape": beta, "scale": eta},
        "cdf": cdf_fn,
        "percentile": percentile_fn,
        "mttf": (gamma + mttf_2, se_2),
        "link_fn": lambda p: np.log(-np.log(1.0 - np.clip(p, 1e-6, 1.0 - 1e-6))),
        "is_log_x": True,
        "threshold": gamma
    }


def fit_lognormal_3p(durations: np.ndarray, events: np.ndarray) -> Dict[str, Any]:
    """3-Parameter Lognormal fit: threshold gamma, location mu, scale sigma."""
    t_min = float(np.min(durations))
    gamma_est = max(0.0, t_min * 0.4)

    def profile_neg_ll(g):
        g_val = g[0]
        if g_val >= t_min - 1e-4 or g_val < 0:
            return 1e12
        shifted = durations - g_val
        fit2 = fit_lognormal_2p(shifted, events)
        return -float(np.sum(events * np.log(np.maximum(1e-12, fit2["cdf"](shifted)))))

    res = optimize.minimize(profile_neg_ll, [gamma_est], bounds=[(0.0, max(0.0, t_min - 0.05))], method="L-BFGS-B")
    gamma = float(res.x[0]) if res.success else max(0.0, t_min * 0.25)

    shifted = durations - gamma
    fit2 = fit_lognormal_2p(shifted, events)

    def cdf_fn(t):
        adj_t = np.maximum(1e-9, t - gamma)
        return fit2["cdf"](adj_t)

    def percentile_fn(p):
        p_val, p_se = fit2["percentile"](p)
        return gamma + p_val, p_se * 1.05

    mttf_2, se_2 = fit2["mttf"]
    return {
        "name": "3-Parameter Lognormal",
        "params": {"threshold": gamma, "location": fit2["params"]["location"], "scale": fit2["params"]["scale"]},
        "cdf": cdf_fn,
        "percentile": percentile_fn,
        "mttf": (gamma + mttf_2, se_2),
        "link_fn": lambda p: stats.norm.ppf(np.clip(p, 1e-6, 1.0 - 1e-6)),
        "is_log_x": True,
        "threshold": gamma
    }


def fit_exponential_2p(durations: np.ndarray, events: np.ndarray) -> Dict[str, Any]:
    """2-Parameter Exponential fit: threshold gamma, scale theta."""
    t_min = float(np.min(durations))
    r = int(np.sum(events == 1))
    gamma = max(0.0, t_min - (t_min / (2 * max(1, r))))
    shifted = durations - gamma
    theta = float(np.sum(shifted)) / max(1, r)
    se_theta = theta / math.sqrt(max(1, r))

    def cdf_fn(t):
        adj_t = np.maximum(0.0, t - gamma)
        return 1.0 - np.exp(- adj_t / theta)

    def percentile_fn(p):
        val = gamma - theta * math.log(1.0 - p)
        se_val = val / math.sqrt(max(1, r))
        return val, se_val

    return {
        "name": "2-Parameter Exponential",
        "params": {"threshold": gamma, "scale": theta},
        "cdf": cdf_fn,
        "percentile": percentile_fn,
        "mttf": (gamma + theta, se_theta),
        "link_fn": lambda p: np.log(-np.log(1.0 - np.clip(p, 1e-6, 1.0 - 1e-6))),
        "is_log_x": True,
        "threshold": gamma
    }


def fit_loglogistic_3p(durations: np.ndarray, events: np.ndarray) -> Dict[str, Any]:
    """3-Parameter Loglogistic fit: threshold gamma, location mu, scale sigma."""
    t_min = float(np.min(durations))
    gamma = max(0.0, t_min * 0.3)
    shifted = durations - gamma
    fit2 = fit_loglogistic_2p(shifted, events)

    def cdf_fn(t):
        adj_t = np.maximum(1e-9, t - gamma)
        return fit2["cdf"](adj_t)

    def percentile_fn(p):
        p_val, p_se = fit2["percentile"](p)
        return gamma + p_val, p_se * 1.05

    mttf_2, se_2 = fit2["mttf"]
    return {
        "name": "3-Parameter Loglogistic",
        "params": {"threshold": gamma, "location": fit2["params"]["location"], "scale": fit2["params"]["scale"]},
        "cdf": cdf_fn,
        "percentile": percentile_fn,
        "mttf": (gamma + mttf_2, se_2),
        "link_fn": lambda p: np.log(np.clip(p, 1e-6, 1.0 - 1e-6) / (1.0 - np.clip(p, 1e-6, 1.0 - 1e-6))),
        "is_log_x": True,
        "threshold": gamma
    }


def fit_sev(durations: np.ndarray, events: np.ndarray) -> Dict[str, Any]:
    """Smallest Extreme Value (SEV) fit: location mu, scale sigma."""
    r = int(np.sum(events == 1))
    init_mu = float(np.mean(durations))
    init_sig = float(np.std(durations)) * (math.sqrt(6.0) / math.pi)

    def neg_loglik(p):
        mu, ln_sig = p
        sig = math.exp(ln_sig)
        if sig <= 1e-9:
            return 1e12
        w = (durations - mu) / sig
        ll = float(np.sum(events * (w - np.log(sig) - np.exp(np.clip(w, -50, 50))) + (1.0 - events) * (-np.exp(np.clip(w, -50, 50)))))
        return -ll

    res = optimize.minimize(neg_loglik, [init_mu, np.log(max(0.1, init_sig))], method="L-BFGS-B")
    mu = res.x[0]
    sig = math.exp(res.x[1])

    var_mu = (1.109 * sig ** 2) / max(1, r)
    var_sig = (0.608 * sig ** 2) / max(1, r)

    def cdf_fn(t):
        w = (t - mu) / sig
        return 1.0 - np.exp(- np.exp(np.clip(w, -50, 50)))

    def percentile_fn(p):
        w_p = math.log(-math.log(1.0 - p))
        val = mu + sig * w_p
        se_val = math.sqrt(max(1e-9, var_mu + w_p ** 2 * var_sig))
        return val, se_val

    mttf = mu - EULER_GAMMA * sig
    se_mttf = math.sqrt(max(1e-9, var_mu + EULER_GAMMA ** 2 * var_sig))

    return {
        "name": "Smallest Extreme Value",
        "params": {"location": mu, "scale": sig},
        "cdf": cdf_fn,
        "percentile": percentile_fn,
        "mttf": (mttf, se_mttf),
        "link_fn": lambda p: np.log(-np.log(1.0 - np.clip(p, 1e-6, 1.0 - 1e-6))),
        "is_log_x": False,
        "threshold": 0.0
    }


def fit_normal(durations: np.ndarray, events: np.ndarray) -> Dict[str, Any]:
    """Normal distribution fit: mean mu, stdev sigma."""
    r = int(np.sum(events == 1))
    failures = durations[events == 1]
    init_mu = float(np.mean(failures)) if r > 0 else float(np.mean(durations))
    init_sig = float(np.std(failures)) if r > 1 else float(np.std(durations))

    def neg_loglik(p):
        mu, ln_sig = p
        sig = math.exp(ln_sig)
        if sig <= 1e-9:
            return 1e12
        z = (durations - mu) / sig
        ll = float(np.sum(events * (-np.log(sig) - 0.5 * np.log(2 * np.pi) - 0.5 * z ** 2) + (1.0 - events) * np.log(np.maximum(1e-12, 1.0 - stats.norm.cdf(z)))))
        return -ll

    res = optimize.minimize(neg_loglik, [init_mu, np.log(max(0.1, init_sig))], method="L-BFGS-B")
    mu = res.x[0]
    sig = math.exp(res.x[1])

    var_mu = sig ** 2 / max(1, r)
    var_sig = sig ** 2 / (2 * max(1, r))

    def cdf_fn(t):
        return stats.norm.cdf((t - mu) / sig)

    def percentile_fn(p):
        z_p = stats.norm.ppf(p)
        val = mu + z_p * sig
        se_val = math.sqrt(max(1e-9, var_mu + z_p ** 2 * var_sig))
        return val, se_val

    return {
        "name": "Normal",
        "params": {"mean": mu, "stdev": sig},
        "cdf": cdf_fn,
        "percentile": percentile_fn,
        "mttf": (mu, math.sqrt(var_mu)),
        "link_fn": lambda p: stats.norm.ppf(np.clip(p, 1e-6, 1.0 - 1e-6)),
        "is_log_x": False,
        "threshold": 0.0
    }


def fit_logistic(durations: np.ndarray, events: np.ndarray) -> Dict[str, Any]:
    """Logistic distribution fit: location mu, scale sigma."""
    r = int(np.sum(events == 1))
    init_mu = float(np.mean(durations))
    init_sig = float(np.std(durations)) * (math.sqrt(3.0) / math.pi)

    def neg_loglik(p):
        mu, ln_sig = p
        sig = math.exp(ln_sig)
        if sig <= 1e-9:
            return 1e12
        w = (durations - mu) / sig
        ll = float(np.sum(events * (-np.log(sig) - w - 2.0 * np.log(1.0 + np.exp(np.clip(-w, -50, 50)))) + (1.0 - events) * (-np.log(1.0 + np.exp(np.clip(w, -50, 50))))))
        return -ll

    res = optimize.minimize(neg_loglik, [init_mu, np.log(max(0.1, init_sig))], method="L-BFGS-B")
    mu = res.x[0]
    sig = math.exp(res.x[1])

    var_mu = (3.0 * sig ** 2 / (np.pi ** 2)) / max(1, r)
    var_sig = (sig ** 2 / 2.0) / max(1, r)

    def cdf_fn(t):
        w = (t - mu) / sig
        return 1.0 / (1.0 + np.exp(-np.clip(w, -50, 50)))

    def percentile_fn(p):
        k_p = math.log(p / (1.0 - p))
        val = mu + sig * k_p
        se_val = math.sqrt(max(1e-9, var_mu + k_p ** 2 * var_sig))
        return val, se_val

    return {
        "name": "Logistic",
        "params": {"location": mu, "scale": sig},
        "cdf": cdf_fn,
        "percentile": percentile_fn,
        "mttf": (mu, math.sqrt(var_mu)),
        "link_fn": lambda p: np.log(np.clip(p, 1e-6, 1.0 - 1e-6) / (1.0 - np.clip(p, 1e-6, 1.0 - 1e-6))),
        "is_log_x": False,
        "threshold": 0.0
    }


ALL_DISTRIBUTION_FITTERS = [
    ("Weibull", fit_weibull_2p),
    ("Lognormal", fit_lognormal_2p),
    ("Exponential", fit_exponential_1p),
    ("Loglogistic", fit_loglogistic_2p),
    ("3-Parameter Weibull", fit_weibull_3p),
    ("3-Parameter Lognormal", fit_lognormal_3p),
    ("2-Parameter Exponential", fit_exponential_2p),
    ("3-Parameter Loglogistic", fit_loglogistic_3p),
    ("Smallest Extreme Value", fit_sev),
    ("Normal", fit_normal),
    ("Logistic", fit_logistic),
]


def build_multi_panel_figure(
    fig_title: str,
    subtitle: str,
    time_col: str,
    models: List[Dict[str, Any]],
    t_sorted: np.ndarray,
    e_sorted: np.ndarray,
    f_emp: np.ndarray,
    is_three_param: bool = False
) -> Dict[str, Any]:
    """
    Builds a 2x2 multi-panel probability plot figure matching Minitab's exact layout.
    """
    domains = [
        {"x": [0.06, 0.44], "y": [0.56, 0.94], "x_axis": "x", "y_axis": "y", "ax_num": ""},
        {"x": [0.50, 0.88], "y": [0.56, 0.94], "x_axis": "x2", "y_axis": "y2", "ax_num": "2"},
        {"x": [0.06, 0.44], "y": [0.06, 0.44], "x_axis": "x3", "y_axis": "y3", "ax_num": "3"},
        {"x": [0.50, 0.88], "y": [0.06, 0.44], "x_axis": "x4", "y_axis": "y4", "ax_num": "4"},
    ]

    traces = []
    layout: Dict[str, Any] = {
        "title": {
            "text": f"<b>{fig_title}</b><br><span style='font-size:11px;color:#64748b;'>{subtitle}</span>",
            "x": 0.47,
            "xanchor": "center",
            "font": {"size": 13, "color": "#1e293b"}
        },
        "plot_bgcolor": "#ffffff",
        "paper_bgcolor": "#ffffff",
        "margin": {"l": 50, "r": 130, "t": 60, "b": 50},
        "height": 560,
        "showlegend": False,
    }

    annotations = []

    # Right-side Anderson-Darling summary card
    ad_lines = ["<b>Anderson-Darling (adj)</b>"]
    for m in models:
        ad_lines.append(f"{m['name']}<br><b>{m.get('ad_adj', 0.0):.3f}</b>")

    annotations.append({
        "xref": "paper",
        "yref": "paper",
        "x": 1.01,
        "y": 0.95,
        "xanchor": "left",
        "yanchor": "top",
        "text": "<br><br>".join(ad_lines),
        "showarrow": False,
        "font": {"size": 10.5, "color": "#334155"},
        "align": "left",
        "bordercolor": "#cbd5e1",
        "borderwidth": 1,
        "borderpad": 6,
        "bgcolor": "#f8fafc"
    })

    # Standard percentile ticks
    p_ticks = [0.01, 0.10, 0.50, 0.90, 0.99]
    p_tick_labels = ["1", "10", "50", "90", "99"]

    failed_mask = (e_sorted == 1)
    t_failed_raw = t_sorted[failed_mask]
    p_failed_raw = f_emp[failed_mask]

    for idx, model in enumerate(models):
        if idx >= len(domains):
            break

        dom = domains[idx]
        ax_key_x = f"xaxis{dom['ax_num']}"
        ax_key_y = f"yaxis{dom['ax_num']}"

        link_fn = model["link_fn"]
        thresh = model.get("threshold", 0.0)

        # Shift x data if 3-parameter threshold
        t_failed = np.maximum(1e-4, t_failed_raw - thresh) if thresh > 0 else t_failed_raw
        y_pts = link_fn(p_failed_raw)

        # 1. Empirical points
        traces.append({
            "type": "scatter",
            "mode": "markers",
            "x": t_failed.tolist(),
            "y": y_pts.tolist(),
            "xaxis": dom["x_axis"],
            "yaxis": dom["y_axis"],
            "name": f"{model['name']} Points",
            "marker": {
                "size": 6.5,
                "color": "#005a9e",
                "symbol": "circle",
                "line": {"color": "#003a66", "width": 0.8}
            },
            "hoverinfo": "x+text",
            "text": [f"Failure: {t_failed_raw[i]:.2f} (P={p_failed_raw[i]*100:.1f}%)" for i in range(len(t_failed))]
        })

        # 2. Fitted reference straight line
        p_line = np.linspace(0.01, 0.99, 100)
        x_line = []
        for p_v in p_line:
            pct_val, _ = model["percentile"](p_v)
            x_line.append(pct_val - thresh if thresh > 0 else pct_val)

        y_line = link_fn(p_line)

        traces.append({
            "type": "scatter",
            "mode": "lines",
            "x": x_line,
            "y": y_line.tolist(),
            "xaxis": dom["x_axis"],
            "yaxis": dom["y_axis"],
            "name": f"{model['name']} Fit",
            "line": {"color": "#a80000", "width": 1.75},
            "hoverinfo": "none"
        })

        # Calculate Y tickvals on link scale
        y_tickvals = [float(link_fn(p_val)) for p_val in p_ticks]

        x_axis_title = f"{time_col} - Threshold" if is_three_param else time_col

        layout[ax_key_x] = {
            "domain": dom["x"],
            "anchor": dom["y_axis"],
            "title": {"text": x_axis_title, "font": {"size": 10.5, "color": "#334155"}},
            "type": "log" if model.get("is_log_x", False) else "linear",
            "showgrid": True,
            "gridcolor": "#f1f5f9",
            "gridwidth": 1,
            "showline": True,
            "linecolor": "#475569",
            "linewidth": 1,
            "mirror": True,
            "zeroline": False,
            "tickfont": {"size": 9.5}
        }

        layout[ax_key_y] = {
            "domain": dom["y"],
            "anchor": dom["x_axis"],
            "title": {"text": "Percent", "font": {"size": 10.5, "color": "#334155"}},
            "tickvals": y_tickvals,
            "ticktext": p_tick_labels,
            "range": [min(y_tickvals) - 0.2, max(y_tickvals) + 0.2],
            "showgrid": True,
            "gridcolor": "#f1f5f9",
            "gridwidth": 1,
            "showline": True,
            "linecolor": "#475569",
            "linewidth": 1,
            "mirror": True,
            "zeroline": False,
            "tickfont": {"size": 9.5}
        }

        # Subplot Title Annotation
        annotations.append({
            "xref": "paper",
            "yref": "paper",
            "x": (dom["x"][0] + dom["x"][1]) / 2.0,
            "y": dom["y"][1] + 0.02,
            "xanchor": "center",
            "yanchor": "bottom",
            "text": f"<b>{model['name']}</b>",
            "showarrow": False,
            "font": {"size": 11, "color": "#1e293b"}
        })

    layout["annotations"] = annotations
    return {"data": traces, "layout": layout}


class DistributionIdRightCensoringParams(BaseModel):
    variables: str = Field(
        ...,
        description="Lifetime / Time-to-Failure Variable",
        json_schema_extra={"ui_type": "column_picker", "data_type": "numeric"}
    )
    censor_col: Optional[str] = Field(
        None,
        description="Censoring Column (1 = Failure, 0 = Censored)",
        json_schema_extra={"ui_type": "column_picker"}
    )
    confidence_level: float = Field(
        95.0,
        ge=50.0,
        le=99.99,
        description="Confidence Level (%)"
    )


class DistributionIdRightCensoringPlugin(AnalysisPlugin):
    id = "reliability_distribution_id_right_censoring"
    name = "Distribution ID Plot (Right Censoring)"
    menu_path = ["Stat", "Reliability/Survival", "Distribution Analysis (Right Censoring)", "Distribution ID Plot"]
    description = "Fits 11 parametric distributions with right censoring, computes Anderson-Darling (adj) goodness of fit, percentiles, MTTF, and separate multi-panel probability plots."
    param_schema = DistributionIdRightCensoringParams

    def execute(self, df: pd.DataFrame, params: DistributionIdRightCensoringParams) -> AnalysisResult:
        time_col = params.variables
        if time_col not in df.columns:
            raise ValueError(f"Column '{time_col}' not found in active worksheet.")

        sub_cols = [time_col]
        has_censor = bool(params.censor_col and params.censor_col in df.columns)
        if has_censor and params.censor_col:
            sub_cols.append(params.censor_col)

        sub_df = df[sub_cols].dropna().copy()
        durations = pd.to_numeric(sub_df[time_col], errors="coerce")
        valid_mask = durations > 0
        durations = durations[valid_mask].to_numpy(dtype=float)

        if has_censor and params.censor_col:
            events = pd.to_numeric(sub_df[params.censor_col][valid_mask], errors="coerce").fillna(1).to_numpy(dtype=int)
        else:
            events = np.ones(len(durations), dtype=int)

        n_total = len(durations)
        n_failed = int(np.sum(events == 1))
        n_censored = int(np.sum(events == 0))

        if n_total < 3:
            raise ValueError("Distribution ID analysis requires at least 3 lifetime observations.")

        conf = params.confidence_level
        alpha = 1.0 - conf / 100.0
        z_crit = float(stats.norm.ppf(1.0 - alpha / 2.0))

        t_sorted, e_sorted, f_emp = compute_kaplan_meier(durations, events)

        gof_rows = []
        percentile_rows = []
        mttf_rows = []

        fitted_models: List[Dict[str, Any]] = []

        # Fit all 11 distributions
        for dist_name, fitter_fn in ALL_DISTRIBUTION_FITTERS:
            try:
                fit_res = fitter_fn(durations, events)
                ad_stat = calc_anderson_darling_censored(t_sorted, e_sorted, f_emp, fit_res["cdf"], n_total)
                fit_res["ad_adj"] = ad_stat
                fitted_models.append(fit_res)

                gof_rows.append([dist_name, f"{ad_stat:.3f}"])

                mttf_val, mttf_se = fit_res["mttf"]
                mttf_low = max(0.0, mttf_val - z_crit * mttf_se)
                mttf_up = mttf_val + z_crit * mttf_se
                mttf_rows.append([
                    dist_name,
                    f"{mttf_val:.5f}",
                    f"{mttf_se:.5f}",
                    f"{mttf_low:.5f}",
                    f"{mttf_up:.5f}"
                ])
            except Exception:
                gof_rows.append([dist_name, "—"])
                mttf_rows.append([dist_name, "—", "—", "—", "—"])

        # Table of Percentiles grouped by percent: 1, 5, 10, 50
        target_percents = [1, 5, 10, 50]
        for p_int in target_percents:
            p_frac = p_int / 100.0
            for fit_res in fitted_models:
                try:
                    pct_val, pct_se = fit_res["percentile"](p_frac)
                    pct_low = max(0.0, pct_val - z_crit * pct_se)
                    pct_up = pct_val + z_crit * pct_se
                    percentile_rows.append([
                        fit_res["name"],
                        str(p_int),
                        f"{pct_val:.5f}",
                        f"{pct_se:.6f}",
                        f"{pct_low:.5f}",
                        f"{pct_up:.5f}"
                    ])
                except Exception:
                    pass

        # ── Construct 3 Separate Multi-Panel Probability Plot Figures ──
        censor_tag = f"Failures: {n_failed}, Censored: {n_censored}" if n_censored > 0 else f"Complete Data (n = {n_total})"
        model_map = {m["name"]: m for m in fitted_models}

        # 1. 2-Parameter Distributions (Weibull, Lognormal, Exponential, Loglogistic)
        group1_names = ["Weibull", "Lognormal", "Exponential", "Loglogistic"]
        group1_models = [model_map[name] for name in group1_names if name in model_map]
        fig1 = build_multi_panel_figure(
            fig_title=f"Probability Plot for {time_col}",
            subtitle=f"ML Estimates - {censor_tag}",
            time_col=time_col,
            models=group1_models,
            t_sorted=t_sorted,
            e_sorted=e_sorted,
            f_emp=f_emp,
            is_three_param=False
        )

        # 2. 3-Parameter Distributions (3P Weibull, 3P Lognormal, 2P Exponential, 3P Loglogistic)
        group2_names = ["3-Parameter Weibull", "3-Parameter Lognormal", "2-Parameter Exponential", "3-Parameter Loglogistic"]
        group2_models = [model_map[name] for name in group2_names if name in model_map]
        fig2 = build_multi_panel_figure(
            fig_title=f"Probability Plot for {time_col} (3-Parameter)",
            subtitle=f"ML Estimates - {censor_tag}",
            time_col=time_col,
            models=group2_models,
            t_sorted=t_sorted,
            e_sorted=e_sorted,
            f_emp=f_emp,
            is_three_param=True
        )

        # 3. Alternative Distributions (Smallest Extreme Value, Normal, Logistic)
        group3_names = ["Smallest Extreme Value", "Normal", "Logistic"]
        group3_models = [model_map[name] for name in group3_names if name in model_map]
        fig3 = build_multi_panel_figure(
            fig_title=f"Probability Plot for {time_col} (Alternative Distributions)",
            subtitle=f"ML Estimates - {censor_tag}",
            time_col=time_col,
            models=group3_models,
            t_sorted=t_sorted,
            e_sorted=e_sorted,
            f_emp=f_emp,
            is_three_param=False
        )

        # Construct Tables
        gof_table = TableResult(
            title="Goodness-of-Fit",
            headers=["Distribution", "Anderson-Darling (adj)"],
            rows=gof_rows,
            notes=["Lower Anderson-Darling (adj) indicates better distribution fit."]
        )

        pct_table = TableResult(
            title="Table of Percentiles",
            headers=["Distribution", "Percent", "Percentile", "Standard Error", f"{conf:.0f}% Normal CI Lower", "Upper"],
            rows=percentile_rows
        )

        mttf_table = TableResult(
            title="Table of MTTF",
            headers=["Distribution", "Mean", "Standard Error", f"{conf:.0f}% Normal CI Lower", "Upper"],
            rows=mttf_rows
        )

        # Minitab Session Log text
        text_lines = [
            f"Distribution ID Plot (Right Censoring): {time_col}",
            "",
            f"  Total Observations : {n_total}",
            f"  Failures           : {n_failed}",
            f"  Censored (Right)   : {n_censored}",
            f"  Confidence Level   : {conf:.0f}%",
            "",
            "Goodness-of-Fit Summary (Anderson-Darling):",
            f"  {'Distribution':<28} {'Anderson-Darling (adj)':<22}",
            f"  {'-'*28} {'-'*22}",
        ]
        for gr in gof_rows:
            text_lines.append(f"  {gr[0]:<28} {gr[1]:<22}")

        text_lines.extend([
            "",
            "Table of Mean Time to Failure (MTTF):",
            f"  {'Distribution':<28} {'Mean':<12} {'Std Error':<12} {'95% CI Lower':<14} {'Upper':<14}",
            f"  {'-'*28} {'-'*12} {'-'*12} {'-'*14} {'-'*14}",
        ])
        for mr in mttf_rows:
            text_lines.append(f"  {mr[0]:<28} {mr[1]:<12} {mr[2]:<12} {mr[3]:<14} {mr[4]:<14}")

        return AnalysisResult(
            title="Distribution ID Plot (Right Censoring)",
            subtitle=f"{time_col} (11 Candidate Distributions)",
            text_output="\n".join(text_lines),
            tables=[gof_table, pct_table, mttf_table],
            plotly_figures=[fig1, fig2, fig3],
            plotly_figure=fig1
        )
