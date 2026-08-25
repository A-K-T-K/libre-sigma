"""
Master Test Suite Runner for LibRE Sigma
Executes all 12 test suites covering all 122 statistical plugins and backend modules.
"""

import sys
import os
import subprocess
import time

TEST_SUITES = [
    ("Basic Statistics (18 plugins)", "test_basic_stats_plugins.py"),
    ("Analysis of Variance / ANOVA (9 plugins)", "test_anova_suite.py"),
    ("Regression & GLM (9 plugins)", "test_regression_suite.py"),
    ("DOE - Factorial Designs (8 plugins)", "test_doe_factorial.py"),
    ("DOE - Response Surface (RSM) (6 plugins)", "test_doe_rsm.py"),
    ("DOE - Mixture Designs (5 plugins)", "test_doe_mixture.py"),
    ("DOE - Taguchi Robust Designs (6 plugins)", "test_doe_taguchi.py"),
    ("Statistical Process Control / SPC (23 plugins)", "test_spc_plugins.py"),
    ("Quality Tools & Capability (13 plugins)", "test_quality_tools.py"),
    ("Multivariate Analysis (11 plugins)", "test_multivariate_suite.py"),
    ("Time Series & Forecasting (16 plugins)", "test_time_series_suite.py"),
    ("Minitab Extensions & Reliability (16 plugins)", "test_minitab_extensions.py"),
]

def main():
    print("=" * 80)
    print("  LibRE Sigma - Master Statistical Plugin Test Suite Execution")
    print("=" * 80)
    print(f"Total Test Suites: {len(TEST_SUITES)}\n")

    overall_start = time.time()
    passed_suites = 0
    failed_suites = []

    for name, script in TEST_SUITES:
        script_path = os.path.join(os.path.dirname(__file__), script)
        if not os.path.exists(script_path):
            print(f"[FAIL] {name}: Script {script} not found!")
            failed_suites.append((name, "File not found"))
            continue

        print(f"--> Running: {name} ({script})...")
        t0 = time.time()
        res = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
        elapsed = time.time() - t0

        if res.returncode == 0:
            print(f"    [PASS] Completed in {elapsed:.2f}s")
            passed_suites += 1
        else:
            print(f"    [FAIL] Returncode {res.returncode} in {elapsed:.2f}s")
            print(res.stderr or res.stdout)
            failed_suites.append((name, res.stderr or res.stdout))

    total_time = time.time() - overall_start
    print("\n" + "=" * 80)
    print(f"  RESULTS: {passed_suites}/{len(TEST_SUITES)} Test Suites Passed ({total_time:.2f}s)")
    print("=" * 80)

    if failed_suites:
        print("\nFailed Suites:")
        for name, err in failed_suites:
            print(f"  - {name}: {err[:200]}")
        sys.exit(1)
    else:
        print("\nALL 122 STATISTICAL PLUGINS ACROSS ALL 12 TEST SUITES PASSED PERFECTLY!")
        sys.exit(0)

if __name__ == "__main__":
    main()
