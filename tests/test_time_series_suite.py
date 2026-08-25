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


def run_tests():
    print("Discovering and loading plugins...")
    discover_and_load_plugins("app.plugins.modules")
    
    plugins = registry.all()
    print(f"Total registered plugins: {len(plugins)}")
    
    # Generate synthetic time series data
    np.random.seed(42)
    n = 60
    t = np.arange(1, n + 1)
    # Trend + 12-period Seasonality + Noise
    trend = 100.0 + 1.5 * t
    seasonal = 20.0 * np.sin(2 * np.pi * t / 12)
    noise = np.random.normal(0, 3, n)
    series_y = trend + seasonal + noise
    series_x = 50.0 + 0.8 * t + np.random.normal(0, 2, n)
    groups = ["Batch-1" if i < 30 else "Batch-2" for i in range(n)]

    df = pd.DataFrame({
        "Passengers": series_y,
        "Cargo": series_x,
        "Group": groups,
        "Index_t": t
    })

    ts_plugin_ids = [
        "ts_plot",
        "ts_trend_analysis",
        "ts_decomposition",
        "ts_moving_average",
        "ts_single_exp_smoothing",
        "ts_double_exp_smoothing",
        "ts_winters_method",
        "ts_differences",
        "ts_lag",
        "ts_autocorrelation",
        "ts_partial_autocorrelation",
        "ts_cross_correlation",
        "ts_box_cox",
        "ts_adf_test",
        "ts_auto_arima",
        "ts_arima"
    ]

    test_params = {
        "ts_plot": {"variables": ["Passengers", "Cargo"], "plot_type": "simple"},
        "ts_trend_analysis": {"variable": "Passengers", "model_type": "linear", "generate_forecasts": True, "n_forecasts": 6, "store_fits": True, "store_forecasts": True},
        "ts_decomposition": {"variable": "Passengers", "seasonal_length": 12, "model_type": "multiplicative", "n_forecasts": 6, "store_trend": True},
        "ts_moving_average": {"variable": "Passengers", "ma_length": 3, "center_ma": False, "generate_forecasts": True, "n_forecasts": 4},
        "ts_single_exp_smoothing": {"variable": "Passengers", "weight_type": "optimize", "generate_forecasts": True, "n_forecasts": 6, "store_smoothed": True},
        "ts_double_exp_smoothing": {"variable": "Passengers", "weight_type": "optimize", "generate_forecasts": True, "n_forecasts": 6},
        "ts_winters_method": {"variable": "Passengers", "seasonal_length": 12, "method_type": "multiplicative", "weight_type": "optimize", "generate_forecasts": True, "n_forecasts": 6},
        "ts_differences": {"variable": "Passengers", "diff_order": 1, "store_column_name": "Diff_Pass"},
        "ts_lag": {"variable": "Passengers", "lag_length": 1, "store_column_name": "Lag_Pass"},
        "ts_autocorrelation": {"variable": "Passengers", "lag_mode": "default", "confidence_level": 95.0, "store_acf": True},
        "ts_partial_autocorrelation": {"variable": "Passengers", "lag_mode": "default", "method": "ywadjusted", "store_pacf": True},
        "ts_cross_correlation": {"first_series_x": "Passengers", "second_series_y": "Cargo", "lag_mode": "default", "store_ccf": True},
        "ts_box_cox": {"variable": "Passengers", "lambda_mode": "optimal", "store_column_name": "BC_Pass"},
        "ts_adf_test": {"variable": "Passengers", "regression_type": "c", "lag_criterion": "AIC"},
        "ts_auto_arima": {"variable": "Passengers", "information_criterion": "aic", "seasonal_periodicity": 12, "n_forecasts": 6, "stepwise": True},
        "ts_arima": {"variable": "Passengers", "p": 1, "d": 1, "q": 1, "P": 0, "D": 0, "Q": 0, "S": 12, "generate_forecasts": True, "n_forecasts": 6}
    }

    print("\n--- Running Time Series Plugin Tests ---")
    success_count = 0
    for pid in ts_plugin_ids:
        plugin = registry.get(pid)
        if not plugin:
            print(f"FAILED: Plugin '{pid}' not found in registry!")
            continue

        params_obj = plugin.param_schema(**test_params[pid])
        try:
            res = plugin.execute(df, params_obj)
            assert res.title, "Missing title in AnalysisResult"
            assert res.text_output, "Missing text_output in AnalysisResult"
            assert len(res.tables) > 0, "Missing tables in AnalysisResult"
            print(f"  [PASS] {plugin.name:<32} (ID: {pid:<25}) Tables: {len(res.tables)}, Plot: {'Yes' if res.plotly_figure else 'No'}, Action: {res.action_type or 'None'}")
            success_count += 1
        except Exception as e:
            print(f"  [FAIL] {plugin.name} (ID: {pid}): {e}")
            import traceback
            traceback.print_exc()

    print(f"\nCompleted: {success_count}/{len(ts_plugin_ids)} tests passed.")
    if success_count == len(ts_plugin_ids):
        print("ALL 16 TIME SERIES PLUGINS PASSED!")
    else:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
