import math
import numpy as np
from scipy import stats, special
from typing import Any, Dict, List, Optional, Tuple


# --- 1. Unbiasing Constants Matrix & Calculation ---

def get_c4(n: int) -> float:
    """Unbiasing constant c4 for sample standard deviation."""
    if n <= 1:
        return 1.0
    try:
        val = math.sqrt(2.0 / (n - 1)) * (math.gamma(n / 2.0) / math.gamma((n - 1) / 2.0))
        return val
    except OverflowError:
        # Stirling approximation for large n
        return 4.0 * (n - 1) / (4.0 * n - 3)

def get_c5(n: int) -> float:
    """Unbiasing constant c5 = sqrt(1 - c4^2)."""
    c4 = get_c4(n)
    return math.sqrt(max(0.0, 1.0 - c4 ** 2))

# Exact d2 and d3 values for n = 2 to 25 from ASTM E2587 / Minitab standards
D2_LOOKUP = {
    2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078,
    11: 3.173, 12: 3.258, 13: 3.336, 14: 3.407, 15: 3.472, 16: 3.532, 17: 3.588, 18: 3.640,
    19: 3.689, 20: 3.735, 21: 3.778, 22: 3.819, 23: 3.858, 24: 3.895, 25: 3.931
}

D3_LOOKUP = {
    2: 0.8525, 3: 0.8884, 4: 0.8798, 5: 0.8641, 6: 0.8480, 7: 0.8332, 8: 0.8198, 9: 0.8078,
    10: 0.7971, 11: 0.7873, 12: 0.7785, 13: 0.7704, 14: 0.7630, 15: 0.7562, 16: 0.7499,
    17: 0.7441, 18: 0.7386, 19: 0.7335, 20: 0.7287, 21: 0.7242, 22: 0.7199, 23: 0.7159,
    24: 0.7121, 25: 0.7084
}

def get_d2(n: int) -> float:
    """Unbiasing factor d2 for sample range."""
    if n in D2_LOOKUP:
        return D2_LOOKUP[n]
    if n <= 1:
        return 1.0
    # Numerical approximation for n > 25
    return 3.931 + 0.12 * math.log(n / 25.0)

def get_d3(n: int) -> float:
    """Unbiasing factor d3 for standard error of sample range."""
    if n in D3_LOOKUP:
        return D3_LOOKUP[n]
    if n <= 1:
        return 0.8525
    return max(0.4, 0.7084 - 0.05 * math.log(n / 25.0))

def get_spc_factors(n: int) -> Dict[str, float]:
    """Computes full set of SPC unbiasing control chart factors for subgroup size n."""
    c4 = get_c4(n)
    d2 = get_d2(n)
    d3 = get_d3(n)
    sqrt_n = math.sqrt(n)

    a2 = 3.0 / (d2 * sqrt_n) if d2 > 0 else 1.88
    a3 = 3.0 / (c4 * sqrt_n) if c4 > 0 else 1.88

    d3_factor = max(0.0, 1.0 - 3.0 * (d3 / d2)) if d2 > 0 else 0.0
    d4_factor = 1.0 + 3.0 * (d3 / d2) if d2 > 0 else 2.0

    b3_factor = max(0.0, 1.0 - (3.0 / c4) * math.sqrt(max(0.0, 1.0 - c4 ** 2))) if c4 > 0 else 0.0
    b4_factor = 1.0 + (3.0 / c4) * math.sqrt(max(0.0, 1.0 - c4 ** 2)) if c4 > 0 else 2.0

    return {
        "n": n,
        "c4": round(c4, 4),
        "c5": round(get_c5(n), 4),
        "d2": round(d2, 4),
        "d3": round(d3, 4),
        "A2": round(a2, 4),
        "A3": round(a3, 4),
        "D3": round(d3_factor, 4),
        "D4": round(d4_factor, 4),
        "B3": round(b3_factor, 4),
        "B4": round(b4_factor, 4),
    }


# --- 2. Nelson / Western Electric Run Rules (Rules 1 to 8) ---

NELSON_TEST_DESCRIPTIONS = {
    1: "1 point > 3.00 standard deviations from center line (Out of control)",
    2: "9 points in a row on same side of center line (Shift)",
    3: "6 points in a row, all increasing or all decreasing (Trend)",
    4: "14 points in a row, alternating up and down (Systematic)",
    5: "2 out of 3 points > 2 standard deviations from center line on same side",
    6: "4 out of 5 points > 1 standard deviation from center line on same side",
    7: "15 points in a row within 1 standard deviation of center line on either side (Stratification)",
    8: "8 points in a row > 1 standard deviation from center line with none within 1 standard deviation (Mixture)",
}

def evaluate_nelson_rules(
    values: np.ndarray,
    cl: float,
    sigma: float,
    enabled_tests: Optional[List[int]] = None
) -> Dict[int, List[int]]:
    """
    Evaluates Nelson Rules 1 through 8 on a 1D sequence of points.
    Returns a dict mapping point_index (0-based) -> list of failed test numbers [1..8].
    """
    if enabled_tests is None:
        enabled_tests = [1, 2, 3, 4, 5, 6, 7, 8]

    n = len(values)
    failures: Dict[int, List[int]] = {i: [] for i in range(n)}
    if n == 0 or sigma <= 0:
        return failures

    z_scores = (values - cl) / sigma

    # Test 1: 1 point > 3 sigma from center line
    if 1 in enabled_tests:
        for i in range(n):
            if abs(z_scores[i]) > 3.0:
                failures[i].append(1)

    # Test 2: 9 points in a row on same side of center line
    if 2 in enabled_tests and n >= 9:
        for i in range(8, n):
            window = z_scores[i - 8 : i + 1]
            if np.all(window > 0) or np.all(window < 0):
                failures[i].append(2)

    # Test 3: 6 points in a row, strictly increasing or decreasing
    if 3 in enabled_tests and n >= 6:
        for i in range(5, n):
            window = values[i - 5 : i + 1]
            diffs = np.diff(window)
            if np.all(diffs > 0) or np.all(diffs < 0):
                failures[i].append(3)

    # Test 4: 14 points in a row, alternating up and down
    if 4 in enabled_tests and n >= 14:
        for i in range(13, n):
            window = values[i - 13 : i + 1]
            diffs = np.diff(window)
            # Check if signs alternate: diffs[k] * diffs[k+1] < 0
            if np.all(diffs[:-1] * diffs[1:] < 0):
                failures[i].append(4)

    # Test 5: 2 out of 3 points > 2 sigma on same side of center line
    if 5 in enabled_tests and n >= 3:
        for i in range(2, n):
            window = z_scores[i - 2 : i + 1]
            if np.sum(window > 2.0) >= 2 or np.sum(window < -2.0) >= 2:
                failures[i].append(5)

    # Test 6: 4 out of 5 points > 1 sigma on same side of center line
    if 6 in enabled_tests and n >= 5:
        for i in range(4, n):
            window = z_scores[i - 4 : i + 1]
            if np.sum(window > 1.0) >= 4 or np.sum(window < -1.0) >= 4:
                failures[i].append(6)

    # Test 7: 15 points in a row within 1 sigma of center line on either side
    if 7 in enabled_tests and n >= 15:
        for i in range(14, n):
            window = np.abs(z_scores[i - 14 : i + 1])
            if np.all(window <= 1.0):
                failures[i].append(7)

    # Test 8: 8 points in a row > 1 sigma on either side with none within 1 sigma
    if 8 in enabled_tests and n >= 8:
        for i in range(7, n):
            window = np.abs(z_scores[i - 7 : i + 1])
            if np.all(window > 1.0):
                failures[i].append(8)

    # Clean up empty failure lists
    return {k: v for k, v in failures.items() if v}


# --- 3. Plotly SPC Control Chart Figure Builder ---

def build_single_spc_plot(
    title: str,
    y_label: str,
    subgroups: List[Any],
    values: np.ndarray,
    cl: float,
    ucl: float,
    lcl: float,
    failed_points: Dict[int, List[int]],
    chart_height: int = 400
) -> Dict[str, Any]:
    """Generates a standalone Plotly SPC control chart with UCL/CL/LCL lines and red flagged violation markers."""
    n = len(values)
    x_axis = [str(s) for s in subgroups] if subgroups else [str(i + 1) for i in range(n)]

    # Distinguish normal vs failed points
    colors = []
    hover_texts = []
    for i in range(n):
        val = values[i]
        fails = failed_points.get(i, [])
        if fails:
            colors.append("#dc2626")  # Red for out-of-control
            fails_str = ", ".join([f"Test {f}" for f in fails])
            hover_texts.append(f"Subgroup: {x_axis[i]}<br>Value: {val:.4f}<br><b>FAILED: {fails_str}</b>")
        else:
            colors.append("#1d4ed8")  # Blue for in-control
            hover_texts.append(f"Subgroup: {x_axis[i]}<br>Value: {val:.4f}")

    data = [
        # Line connecting all points
        {
            "type": "scatter",
            "mode": "lines+markers",
            "x": x_axis,
            "y": values.tolist(),
            "name": "Subgroup Value",
            "line": {"color": "#64748b", "width": 1.5},
            "marker": {
                "color": colors,
                "size": 7,
                "line": {"color": colors, "width": 1.5}
            },
            "hovertext": hover_texts,
            "hoverinfo": "text",
            "showlegend": False,
        }
    ]

    shapes = [
        # UCL Line
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": ucl, "y1": ucl, "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"}},
        # CL Line
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": cl, "y1": cl, "line": {"color": "#16a34a", "width": 1.75}},
        # LCL Line
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": lcl, "y1": lcl, "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"}},
        # Outer Border Box
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "paper", "y0": 1, "y1": 1, "line": {"color": "#888888", "width": 1}},
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "paper", "y0": 0, "y1": 0, "line": {"color": "#888888", "width": 1}},
        {"type": "line", "xref": "paper", "x0": 0, "x1": 0, "yref": "paper", "y0": 0, "y1": 1, "line": {"color": "#888888", "width": 1}},
        {"type": "line", "xref": "paper", "x0": 1, "x1": 1, "yref": "paper", "y0": 0, "y1": 1, "line": {"color": "#888888", "width": 1}},
    ]

    annotations = [
        {"xref": "paper", "x": 1.01, "y": ucl, "text": f"<b>UCL={ucl:.3f}</b>", "showarrow": False, "font": {"color": "#dc2626", "size": 11}, "xanchor": "left"},
        {"xref": "paper", "x": 1.01, "y": cl, "text": f"<b>CL={cl:.3f}</b>", "showarrow": False, "font": {"color": "#16a34a", "size": 11}, "xanchor": "left"},
        {"xref": "paper", "x": 1.01, "y": lcl, "text": f"<b>LCL={lcl:.3f}</b>", "showarrow": False, "font": {"color": "#dc2626", "size": 11}, "xanchor": "left"},
    ]

    layout = {
        "title": {"text": f"<b>{title}</b>", "x": 0.5, "y": 0.95, "yanchor": "top", "font": {"size": 15, "color": "#1e293b"}},
        "paper_bgcolor": "#ffffff",
        "plot_bgcolor": "#ffffff",
        "margin": {"l": 75, "r": 95, "t": 75, "b": 55},
        "height": chart_height,
        "xaxis": {"title": {"text": "Subgroup / Sample"}, "showgrid": True, "gridcolor": "#ececec"},
        "yaxis": {"title": {"text": y_label}, "showgrid": True, "gridcolor": "#ececec"},
        "shapes": shapes,
        "annotations": annotations,
    }

    return {"data": data, "layout": layout}


def build_dual_spc_plot(
    title: str,
    top_label: str,
    bot_label: str,
    subgroups: List[Any],
    top_values: np.ndarray,
    top_cl: float,
    top_ucl: float,
    top_lcl: float,
    top_fails: Dict[int, List[int]],
    bot_values: np.ndarray,
    bot_cl: float,
    bot_ucl: float,
    bot_lcl: float,
    bot_fails: Dict[int, List[int]],
    chart_height: int = 560
) -> Dict[str, Any]:
    """Generates dual linked stacked Plotly SPC subplots (e.g. Xbar on top, R on bottom)."""
    n = len(top_values)
    x_axis = [str(s) for s in subgroups] if subgroups else [str(i + 1) for i in range(n)]

    # Top Chart Data
    top_colors = ["#dc2626" if i in top_fails else "#1d4ed8" for i in range(n)]
    top_hover = [
        f"Subgroup: {x_axis[i]}<br>Value: {top_values[i]:.4f}" + (f"<br><b>FAILED: {', '.join(['Test ' + str(f) for f in top_fails[i]])}</b>" if i in top_fails else "")
        for i in range(n)
    ]

    # Bottom Chart Data
    bot_colors = ["#dc2626" if i in bot_fails else "#0d9488" for i in range(n)]
    bot_hover = [
        f"Subgroup: {x_axis[i]}<br>Value: {bot_values[i]:.4f}" + (f"<br><b>FAILED: {', '.join(['Test ' + str(f) for f in bot_fails[i]])}</b>" if i in bot_fails else "")
        for i in range(n)
    ]

    data = [
        # Top Plot Trace
        {
            "type": "scatter",
            "mode": "lines+markers",
            "x": x_axis,
            "y": top_values.tolist(),
            "xaxis": "x",
            "yaxis": "y",
            "name": top_label,
            "line": {"color": "#64748b", "width": 1.5},
            "marker": {"color": top_colors, "size": 7},
            "hovertext": top_hover,
            "hoverinfo": "text",
            "showlegend": False,
        },
        # Bottom Plot Trace
        {
            "type": "scatter",
            "mode": "lines+markers",
            "x": x_axis,
            "y": bot_values.tolist(),
            "xaxis": "x",
            "yaxis": "y2",
            "name": bot_label,
            "line": {"color": "#64748b", "width": 1.5},
            "marker": {"color": bot_colors, "size": 7},
            "hovertext": bot_hover,
            "hoverinfo": "text",
            "showlegend": False,
        }
    ]

    shapes = [
        # Top Limits
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "y", "y0": top_ucl, "y1": top_ucl, "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"}},
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "y", "y0": top_cl, "y1": top_cl, "line": {"color": "#16a34a", "width": 1.75}},
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "y", "y0": top_lcl, "y1": top_lcl, "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"}},

        # Bottom Limits
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "y2", "y0": bot_ucl, "y1": bot_ucl, "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"}},
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "y2", "y0": bot_cl, "y1": bot_cl, "line": {"color": "#16a34a", "width": 1.75}},
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "y2", "y0": bot_lcl, "y1": bot_lcl, "line": {"color": "#dc2626", "width": 1.5, "dash": "dash"}},
    ]

    annotations = [
        # Top Annotations
        {"xref": "paper", "yref": "y", "x": 1.01, "y": top_ucl, "text": f"<b>UCL={top_ucl:.3f}</b>", "showarrow": False, "font": {"color": "#dc2626", "size": 11}, "xanchor": "left"},
        {"xref": "paper", "yref": "y", "x": 1.01, "y": top_cl, "text": f"<b>CL={top_cl:.3f}</b>", "showarrow": False, "font": {"color": "#16a34a", "size": 11}, "xanchor": "left"},
        {"xref": "paper", "yref": "y", "x": 1.01, "y": top_lcl, "text": f"<b>LCL={top_lcl:.3f}</b>", "showarrow": False, "font": {"color": "#dc2626", "size": 11}, "xanchor": "left"},

        # Bottom Annotations
        {"xref": "paper", "yref": "y2", "x": 1.01, "y": bot_ucl, "text": f"<b>UCL={bot_ucl:.3f}</b>", "showarrow": False, "font": {"color": "#dc2626", "size": 11}, "xanchor": "left"},
        {"xref": "paper", "yref": "y2", "x": 1.01, "y": bot_cl, "text": f"<b>CL={bot_cl:.3f}</b>", "showarrow": False, "font": {"color": "#16a34a", "size": 11}, "xanchor": "left"},
        {"xref": "paper", "yref": "y2", "x": 1.01, "y": bot_lcl, "text": f"<b>LCL={bot_lcl:.3f}</b>", "showarrow": False, "font": {"color": "#dc2626", "size": 11}, "xanchor": "left"},
    ]

    layout = {
        "title": {"text": f"<b>{title}</b>", "x": 0.5, "y": 0.96, "yanchor": "top", "font": {"size": 16, "color": "#1e293b"}},
        "paper_bgcolor": "#ffffff",
        "plot_bgcolor": "#ffffff",
        "margin": {"l": 75, "r": 95, "t": 70, "b": 50},
        "height": chart_height,
        "xaxis": {"title": {"text": "Subgroup / Sample"}, "showgrid": True, "gridcolor": "#ececec"},
        "yaxis": {"domain": [0.55, 1.0], "title": {"text": top_label}, "showgrid": True, "gridcolor": "#ececec"},
        "yaxis2": {"domain": [0.0, 0.45], "anchor": "x", "title": {"text": bot_label}, "showgrid": True, "gridcolor": "#ececec"},
        "shapes": shapes,
        "annotations": annotations,
    }

    return {"data": data, "layout": layout}
