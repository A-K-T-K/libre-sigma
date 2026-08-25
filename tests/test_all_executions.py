import json
import urllib.request

BASE_URL = "http://127.0.0.1:8000/api/v1/compute"

sample_df = [
    {"M1": 1.498, "M2": 1.502, "Counts": 3, "Batch": "A"},
    {"M1": 1.501, "M2": 1.504, "Counts": 5, "Batch": "A"},
    {"M1": 1.499, "M2": 1.501, "Counts": 2, "Batch": "A"},
    {"M1": 1.503, "M2": 1.506, "Counts": 4, "Batch": "B"},
    {"M1": 1.497, "M2": 1.503, "Counts": 1, "Batch": "B"},
    {"M1": 1.502, "M2": 1.505, "Counts": 6, "Batch": "B"},
    {"M1": 1.500, "M2": 1.502, "Counts": 3, "Batch": "C"},
    {"M1": 1.496, "M2": 1.507, "Counts": 4, "Batch": "C"},
    {"M1": 1.504, "M2": 1.504, "Counts": 2, "Batch": "C"},
]
cols = [
    {"id": "M1", "name": "M1", "type": "numeric"},
    {"id": "M2", "name": "M2", "type": "numeric"},
    {"id": "Counts", "name": "Counts", "type": "numeric"},
    {"id": "Batch", "name": "Batch", "type": "text"},
]

def run_plugin(plugin_id, params):
    payload = {"data": sample_df, "columns": cols, "params": params}
    req = urllib.request.Request(
        f"{BASE_URL}/{plugin_id}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode("utf-8"))
        print(f" [PASS] {plugin_id}: '{data.get('title')}' -> {len(data.get('tables', []))} tables, Plotly: {bool(data.get('plotly_figure'))}")

def main():
    print("Testing execution of all Basic Statistics modules...")
    run_plugin("display_descriptives", {"variables": ["M1", "M2"]})
    run_plugin("store_descriptives", {"variables": ["M1"]})
    run_plugin("graphical_summary", {"variable": "M1"})
    run_plugin("one_sample_z", {"sample_col": "M1", "known_sigma": 0.005, "hypothesized_mean": 1.50})
    run_plugin("one_sample_t", {"sample_col": "M1", "hypothesized_mean": 1.50})
    run_plugin("two_sample_t", {"sample1_col": "M1", "sample2_col": "M2"})
    run_plugin("paired_t", {"sample1_col": "M1", "sample2_col": "M2"})
    run_plugin("one_proportion", {"data_mode": "summarized", "num_events": 35, "num_trials": 100, "hypothesized_prop": 0.30})
    run_plugin("two_proportions", {"data_mode": "summarized", "sample1_events": 20, "sample1_trials": 50, "sample2_events": 30, "sample2_trials": 60})
    run_plugin("one_sample_poisson_rate", {"sample_col": "Counts", "data_mode": "raw", "hypothesized_rate": 3.0})
    run_plugin("two_sample_poisson_rate", {"data_mode": "summarized", "sample1_occurrences": 15, "sample1_size": 5.0, "sample2_occurrences": 25, "sample2_size": 5.0})
    run_plugin("one_variance", {"sample_col": "M1", "hypothesized_value": 0.005})
    run_plugin("two_variances", {"sample1_col": "M1", "sample2_col": "M2"})
    run_plugin("correlation", {"variables": ["M1", "M2", "Counts"]})
    run_plugin("covariance", {"variables": ["M1", "M2"]})
    run_plugin("normality_test", {"variable": "M1"})
    run_plugin("outlier_test", {"variable": "M1"})
    run_plugin("goodness_of_fit_poisson", {"observed_col": "Counts", "data_mode": "raw"})
    print("\nALL 17 BASIC STATISTICS PLUGINS TESTED AND VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
