import os
import sys
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.plugins.loader import discover_and_load_plugins, registry

sample_data = [
    {"Obs": 10.2, "Defects": 3, "Size": 50, "Days": 12, "V1": 1.2, "V2": 3.4},
    {"Obs": 10.5, "Defects": 5, "Size": 50, "Days": 15, "V1": 1.4, "V2": 3.6},
    {"Obs": 9.8,  "Defects": 2, "Size": 50, "Days": 8,  "V1": 1.1, "V2": 3.2},
    {"Obs": 10.1, "Defects": 4, "Size": 50, "Days": 20, "V1": 1.3, "V2": 3.5},
    {"Obs": 10.4, "Defects": 1, "Size": 50, "Days": 11, "V1": 1.5, "V2": 3.7},
    {"Obs": 9.9,  "Defects": 6, "Size": 50, "Days": 14, "V1": 1.2, "V2": 3.3},
    {"Obs": 10.3, "Defects": 2, "Size": 50, "Days": 9,  "V1": 1.4, "V2": 3.6},
    {"Obs": 10.0, "Defects": 3, "Size": 50, "Days": 16, "V1": 1.3, "V2": 3.4},
    {"Obs": 10.6, "Defects": 4, "Size": 50, "Days": 18, "V1": 1.6, "V2": 3.8},
    {"Obs": 9.7,  "Defects": 2, "Size": 50, "Days": 7,  "V1": 1.0, "V2": 3.1},
]
df = pd.DataFrame(sample_data)


def run_plugin(plugin_id: str, params_dict: dict):
    plugin = registry.get(plugin_id)
    assert plugin is not None, f"Plugin {plugin_id} not found in registry!"
    params = plugin.param_schema.model_validate(params_dict)
    res = plugin.execute(df, params)
    assert res is not None
    print(f"  [PASS] {plugin_id}: '{res.title}' -> Tables: {len(res.tables)}, Chart: {bool(res.plotly_figure)}")


def main():
    print("Testing SPC Manifest and Executions...")
    discover_and_load_plugins("app.plugins.modules")
    manifest = registry.get_manifest()
    spc_plugins = [p for p in manifest if len(p.menu_path) >= 2 and p.menu_path[1] == "Control Charts"]
    print(f"Discovered {len(spc_plugins)} SPC Control Chart plugins:")
    for i, p in enumerate(spc_plugins, 1):
        print(f"  {i:2d}. {p.name} -> {' > '.join(p.menu_path)}")

    print("\nExecuting SPC Plugins:")
    # Subgroups
    run_plugin("xbar_r", {"measurement_col": "Obs", "subgroup_size": 2})
    run_plugin("xbar_s", {"measurement_col": "Obs", "subgroup_size": 2})
    run_plugin("xbar_only", {"measurement_col": "Obs", "subgroup_size": 2})
    run_plugin("r_chart", {"measurement_col": "Obs", "subgroup_size": 2})
    run_plugin("s_chart", {"measurement_col": "Obs", "subgroup_size": 2})
    run_plugin("zone_chart", {"measurement_col": "Obs", "subgroup_size": 2})

    # Individuals
    run_plugin("i_mr", {"measurement_col": "Obs"})
    run_plugin("z_mr", {"measurement_col": "Obs"})
    run_plugin("individual_only", {"measurement_col": "Obs"})
    run_plugin("mr_only", {"measurement_col": "Obs"})

    # Attributes
    run_plugin("p_chart", {"defectives_col": "Defects", "constant_size": 50})
    run_plugin("np_chart", {"defectives_col": "Defects", "subgroup_size": 50})
    run_plugin("c_chart", {"defects_col": "Defects"})
    run_plugin("u_chart", {"defects_col": "Defects", "constant_size": 1.0})
    run_plugin("laney_p_prime", {"defectives_col": "Defects", "constant_size": 50})
    run_plugin("laney_u_prime", {"defects_col": "Defects", "constant_size": 1.0})

    # Time-Weighted
    run_plugin("ewma", {"measurement_col": "Obs", "subgroup_size": 1, "weight": 0.2})
    run_plugin("cusum", {"measurement_col": "Obs", "subgroup_size": 1, "shift_size": 1.0, "decision_interval": 4.0})
    run_plugin("moving_average", {"measurement_col": "Obs", "subgroup_size": 1, "span": 3})

    # Multivariate
    run_plugin("t2_multivariate", {"variables": ["V1", "V2"], "alpha": 0.05})
    run_plugin("generalized_variance", {"variables": ["V1", "V2"], "subgroup_size": 5})

    # Rare Events
    run_plugin("g_chart", {"opportunities_col": "Days"})
    run_plugin("t_chart", {"time_col": "Days"})

    print("\nALL SPC CONTROL CHARTS TESTED AND PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
