import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
import numpy as np
import pandas as pd

from app.plugins.loader import discover_and_load_plugins, registry


def test_plugin_discovery():
    discover_and_load_plugins()
    plugins = registry.all()
    assert len(plugins) >= 121, f"Expected at least 121 plugins, found {len(plugins)}"
    print(f"Total plugins discovered: {len(plugins)}")


def test_1sample_wilcoxon():
    p = registry.get("nonparam_1sample_wilcoxon")
    assert p is not None
    df = pd.DataFrame({"Data": [1.2, 2.3, -0.5, 4.1, 3.2, 5.0, 2.8, 3.5, 4.0, 1.9]})
    params = p.param_schema(variables=["Data"], test_median=2.0, alternative="two-sided", store_estimates=True)
    res = p.execute(df, params)
    assert len(res.tables) == 1
    assert res.plotly_figure is not None
    assert res.action_type == "worksheet_append_columns"
    print("1-Sample Wilcoxon: PASSED")


def test_mann_whitney():
    p = registry.get("nonparam_mann_whitney")
    assert p is not None
    df = pd.DataFrame({
        "SampleA": [12.1, 14.3, 11.8, 15.0, 13.2, 14.5],
        "SampleB": [9.8, 10.5, 11.2, 10.1, 9.5, 10.8]
    })
    params = p.param_schema(first_sample="SampleA", second_sample="SampleB", alternative="two-sided")
    res = p.execute(df, params)
    assert len(res.tables) == 2
    assert res.plotly_figure is not None
    print("Mann-Whitney: PASSED")


def test_kruskal_wallis():
    p = registry.get("nonparam_kruskal_wallis")
    assert p is not None
    df = pd.DataFrame({
        "Group": ["A", "A", "A", "B", "B", "B", "C", "C", "C"],
        "Score": [10.2, 11.5, 12.1, 20.4, 21.8, 22.5, 15.1, 16.2, 14.8]
    })
    params = p.param_schema(response="Score", factor="Group", store_ranks=True)
    res = p.execute(df, params)
    assert len(res.tables) == 2
    assert res.action_type == "worksheet_append_columns"
    print("Kruskal-Wallis: PASSED")


def test_moods_median():
    p = registry.get("nonparam_moods_median")
    assert p is not None
    df = pd.DataFrame({
        "Method": ["M1", "M1", "M1", "M1", "M2", "M2", "M2", "M2"],
        "Output": [45, 48, 52, 50, 62, 65, 59, 70]
    })
    params = p.param_schema(response="Output", factor="Method")
    res = p.execute(df, params)
    assert len(res.tables) == 2
    print("Mood's Median Test: PASSED")


def test_friedman():
    p = registry.get("nonparam_friedman")
    assert p is not None
    df = pd.DataFrame({
        "Block": [1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4],
        "Treatment": ["T1", "T2", "T3", "T1", "T2", "T3", "T1", "T2", "T3", "T1", "T2", "T3"],
        "Value": [5.2, 6.1, 7.8, 4.9, 5.8, 8.2, 5.5, 6.4, 7.9, 5.1, 6.0, 8.0]
    })
    params = p.param_schema(response="Value", treatment="Treatment", blocks="Block")
    res = p.execute(df, params)
    assert len(res.tables) == 2
    print("Friedman Test: PASSED")


def test_cross_tabulation():
    p = registry.get("tables_cross_tabulation")
    assert p is not None
    df = pd.DataFrame({
        "Gender": ["M", "M", "F", "F", "M", "F", "M", "F", "M", "F"],
        "Preference": ["Yes", "No", "Yes", "Yes", "No", "Yes", "No", "No", "Yes", "Yes"]
    })
    params = p.param_schema(row_variable="Gender", col_variable="Preference", show_counts=True, show_row_pct=True)
    res = p.execute(df, params)
    assert len(res.tables) == 2
    print("Cross-Tabulation: PASSED")


def test_chisq_gof():
    p = registry.get("tables_chisq_gof")
    assert p is not None
    df = pd.DataFrame({
        "Color": ["Red", "Blue", "Green", "Red", "Red", "Blue", "Green", "Green", "Green", "Blue"]
    })
    params = p.param_schema(observed_counts="Color", proportion_mode="equal")
    res = p.execute(df, params)
    assert len(res.tables) == 2
    print("Chi-Square Goodness-of-Fit: PASSED")


def test_power_sample_size():
    p = registry.get("power_and_sample_size")
    assert p is not None
    df = pd.DataFrame()
    params = p.param_schema(test_type="2_sample_t", solve_for="sample_size", difference_effect=1.5, standard_deviation=2.0, target_power=0.80)
    res = p.execute(df, params)
    assert len(res.tables) == 1
    assert res.statistics["sample_size"] > 0
    print("Power and Sample Size: PASSED")


def test_distribution_analysis():
    p = registry.get("reliability_distribution_analysis")
    assert p is not None
    df = pd.DataFrame({
        "Time": [120, 150, 200, 240, 310, 400, 450, 520, 600, 750],
        "Censor": [1, 1, 1, 0, 1, 1, 0, 1, 1, 0]
    })
    params = p.param_schema(variables="Time", censor_col="Censor", distribution="weibull")
    res = p.execute(df, params)
    assert len(res.tables) == 2
    assert res.plotly_figure is not None
    print("Distribution Analysis (Reliability): PASSED")


def test_life_data_regression():
    p = registry.get("reliability_life_data_regression")
    assert p is not None
    df = pd.DataFrame({
        "Hours": [150, 210, 320, 450, 550, 620, 780, 850, 950, 1100],
        "Failed": [1, 1, 1, 1, 0, 1, 0, 1, 1, 0],
        "Temp": [85, 85, 85, 75, 75, 75, 65, 65, 65, 65]
    })
    params = p.param_schema(response_time="Hours", censor_col="Failed", predictors=["Temp"], distribution="weibull")
    res = p.execute(df, params)
    assert len(res.tables) == 2
    print("Regression with Life Data: PASSED")


def test_response_optimizer():
    p = registry.get("doe_response_optimizer")
    assert p is not None
    df = pd.DataFrame({
        "Temp": [150, 150, 200, 200, 175, 175, 175],
        "Time": [30, 60, 30, 60, 45, 45, 45],
        "Yield": [82.5, 85.0, 91.2, 94.8, 90.1, 89.8, 90.5]
    })
    params = p.param_schema(responses=["Yield"], factors=["Temp", "Time"], goal="maximize")
    res = p.execute(df, params)
    assert len(res.tables) == 2
    assert "composite_desirability" in res.statistics
    print("Response Optimizer: PASSED")


def test_gage_rr_nested():
    p = registry.get("gage_rr_nested")
    assert p is not None
    df = pd.DataFrame({
        "Operator": ["Op1", "Op1", "Op1", "Op1", "Op2", "Op2", "Op2", "Op2", "Op3", "Op3", "Op3", "Op3"],
        "Part": ["P1", "P1", "P2", "P2", "P3", "P3", "P4", "P4", "P5", "P5", "P6", "P6"],
        "Measurement": [10.2, 10.4, 15.1, 15.3, 11.0, 11.2, 14.8, 14.9, 12.1, 12.3, 16.0, 16.2]
    })
    params = p.param_schema(part_column="Part", operator_column="Operator", measurement_data="Measurement", process_tolerance=10.0)
    res = p.execute(df, params)
    assert len(res.tables) == 2
    assert "ndc" in res.statistics
    print("Gage R&R (Nested): PASSED")


def test_gage_linearity_bias():
    p = registry.get("gage_linearity_bias")
    assert p is not None
    df = pd.DataFrame({
        "Master": [2.0, 2.0, 4.0, 4.0, 6.0, 6.0, 8.0, 8.0, 10.0, 10.0],
        "Measured": [2.05, 2.02, 4.08, 4.05, 6.12, 6.10, 8.15, 8.18, 10.22, 10.25]
    })
    params = p.param_schema(reference_values="Master", measurement_data="Measured")
    res = p.execute(df, params)
    assert len(res.tables) == 2
    assert "linearity" in res.statistics
    print("Gage Linearity and Bias: PASSED")


def test_capability_nonnormal():
    p = registry.get("capability_nonnormal")
    assert p is not None
    df = pd.DataFrame({
        "Process": [10.5, 12.3, 15.2, 18.0, 22.1, 25.4, 30.2, 35.8, 42.1, 50.0]
    })
    params = p.param_schema(data_column="Process", lsl=5.0, usl=60.0, distribution="weibull")
    res = p.execute(df, params)
    assert len(res.tables) == 3
    assert "ppk" in res.statistics
    print("Non-Normal Capability: PASSED")


def test_stepwise_regression():
    p = registry.get("regression_stepwise")
    assert p is not None
    np.random.seed(42)
    x1 = np.linspace(1, 10, 20)
    x2 = np.random.normal(0, 1, 20)
    x3 = x1 * 2 + np.random.normal(0, 0.5, 20)
    y = 3.0 + 2.5 * x1 - 1.2 * x2 + np.random.normal(0, 0.5, 20)
    df = pd.DataFrame({"Y": y, "X1": x1, "X2": x2, "X3": x3})
    params = p.param_schema(response="Y", predictors=["X1", "X2", "X3"], method="stepwise")
    res = p.execute(df, params)
    assert len(res.tables) == 3
    assert "selected_variables" in res.statistics
    print("Stepwise Regression: PASSED")


def test_kijima_grp():

    p = registry.get("reliability_kijima_grp")
    assert p is not None
    df = pd.DataFrame({
        "FailureTimes": [12.5, 28.0, 41.2, 59.0, 72.4, 88.1, 102.3, 115.0, 131.2, 145.8]
    })
    params = p.param_schema(event_times="FailureTimes", model_type="type1", restoration_mode="estimate", store_virtual_ages=True)
    res = p.execute(df, params)
    assert len(res.tables) == 3
    assert "beta" in res.statistics
    assert res.action_type == "worksheet_append_columns"
    print("Kijima GRP (Type I & II): PASSED")


if __name__ == "__main__":
    test_plugin_discovery()
    test_1sample_wilcoxon()
    test_mann_whitney()
    test_kruskal_wallis()
    test_moods_median()
    test_friedman()
    test_cross_tabulation()
    test_chisq_gof()
    test_power_sample_size()
    test_distribution_analysis()
    test_life_data_regression()
    test_response_optimizer()
    test_gage_rr_nested()
    test_gage_linearity_bias()
    test_capability_nonnormal()
    test_stepwise_regression()
    test_kijima_grp()
    print("\nALL 16/16 MINITAB EXTENSION & GRP TESTS PASSED PERFECTLY!")

