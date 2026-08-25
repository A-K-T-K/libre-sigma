import time
import requests
import numpy as np

API = "http://127.0.0.1:8000/api/v1"

print("=" * 60)
print("COMPREHENSIVE BACKEND THROUGHPUT & EDGE CASE TEST SUITE")
print("=" * 60)

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} -- {detail}")

# 1. Health check
r = requests.get(f"{API}/health")
check("Backend online", r.status_code == 200 and r.json().get("status") == "online")

# 2. Test compute with large dataset (1,000 rows, 5 columns)
print("\n[Test 1] Large Dataset Compute Throughput")
np.random.seed(42)
large_rows = [
    {"c1": float(x), "c2": float(y), "c3": f"Group_{i%3}"}
    for i, (x, y) in enumerate(zip(np.random.normal(50, 10, 1000), np.random.normal(100, 15, 1000)))
]

payload_large = {
    "data": large_rows,
    "columns": [
        {"id": "c1", "name": "Measurement1"},
        {"id": "c2", "name": "Measurement2"},
        {"id": "c3", "name": "Category"}
    ],
    "params": {
        "variables": ["Measurement1", "Measurement2"]
    }
}

t0 = time.perf_counter()
r2 = requests.post(f"{API}/compute/display_descriptives", json=payload_large)
t_elapsed = (time.perf_counter() - t0) * 1000
check("1000-row Descriptive Stats returns 200", r2.status_code == 200, f"status={r2.status_code}: {r2.text[:200]}")
check(f"High throughput response time ({t_elapsed:.1f}ms < 1500ms)", t_elapsed < 1500, f"took {t_elapsed:.1f}ms")

if r2.status_code == 200:
    res = r2.json()
    check("Tables returned", len(res.get("tables", [])) > 0)

# 3. Edge Case: Missing values, blanks, asterisks
print("\n[Test 2] Edge Cases: Missing Values, Blanks & Asterisks")
payload_missing = {
    "data": [
        {"c1": "", "c2": "*"},
        {"c1": None, "c2": "NaN"},
        {"c1": 25.4, "c2": 60.1},
        {"c1": 26.1, "c2": 61.2},
        {"c1": 25.8, "c2": 59.8}
    ],
    "columns": [
        {"id": "c1", "name": "Dimension"},
        {"id": "c2", "name": "Hardness"}
    ],
    "params": {
        "variables": ["Dimension"]
    }
}

r3 = requests.post(f"{API}/compute/display_descriptives", json=payload_missing)
check("Missing values handled cleanly (200 OK)", r3.status_code == 200, f"got {r3.status_code}: {r3.text[:200]}")

# 4. Edge Case: Empty data payload
print("\n[Test 3] Edge Case: Empty Data")
payload_empty = {
    "data": [],
    "columns": [{"id": "c1", "name": "EmptyCol"}],
    "params": {"variables": ["EmptyCol"]}
}
r4 = requests.post(f"{API}/compute/display_descriptives", json=payload_empty)
check("Empty data returns handled response or error", r4.status_code in [200, 400])

# 5. ANOVA / Two-sample t-test
print("\n[Test 4] Hypothesis Testing Throughput (2-Sample t)")
payload_t = {
    "data": [
        {"c1": 10.2, "c2": 14.5},
        {"c1": 11.1, "c2": 15.1},
        {"c1": 10.8, "c2": 14.8},
        {"c1": 10.5, "c2": 15.3},
        {"c1": 11.0, "c2": 14.9}
    ],
    "columns": [
        {"id": "c1", "name": "SampleA"},
        {"id": "c2", "name": "SampleB"}
    ],
    "params": {
        "sample1_col": "SampleA",
        "sample2_col": "SampleB",
        "assume_equal_variances": False
    }
}
r5 = requests.post(f"{API}/compute/two_sample_t", json=payload_t)
check("2-Sample t-test returns 200", r5.status_code == 200, f"got {r5.status_code}: {r5.text[:200]}")


print("\n" + "=" * 60)
print(f"RESULTS: {passed} PASSED / {failed} FAILED")
print("=" * 60)
if failed == 0:
    print("ALL BACKEND THROUGHPUT TESTS PASSED!\n")
else:
    exit(1)
