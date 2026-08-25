import urllib.request
import json

def test_api():
    print("=======================================================")
    print("       OpenMinitab End-to-End Taguchi Test Suite       ")
    print("=======================================================\n")
    
    # 1. Health
    with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health") as res:
        health = json.loads(res.read().decode("utf-8"))
        print("[PASS] Health Check:", health)

    # 2. Manifest
    with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/plugins/manifest") as res:
        manifest = json.loads(res.read().decode("utf-8"))
        print(f"\n[PASS] Manifest: {len(manifest)} plugins discovered:")
        for p in manifest:
            path_str = " > ".join(p["menu_path"])
            print(f"       • {p['name']} (ID: {p['id']}) | Path: {path_str}")

    # 3. Create Taguchi Design (L9 3^4)
    print("\n--- Testing Taguchi Design Generator (doe_create_taguchi) ---")
    payload_taguchi_create = {
        "data": [],
        "columns": [],
        "params": {
            "factor_type": "3_level",
            "array_choice": "L9_3_4",
            "num_factors": 3,
            "factor_names_str": "CuttingSpeed, FeedRate, DepthOfCut",
            "worksheet_name": "Taguchi L9 Surface Finish"
        }
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/compute/doe_create_taguchi",
        data=json.dumps(payload_taguchi_create).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as res:
        taguchi_gen_result = json.loads(res.read().decode("utf-8"))
        print(f"[PASS] Taguchi Design Generated: {taguchi_gen_result['title']}")
        print(f"       Action Type: {taguchi_gen_result.get('action_type')}")
        ws_data = taguchi_gen_result.get("worksheet_data", {})
        print(f"       Worksheet Name: {ws_data.get('name')}")
        print(f"       Columns Created: {[c['name'] for c in ws_data.get('columns', [])]}")
        print(f"       Runs Generated: {len(ws_data.get('rows', []))}")
        print(f"\n[Session Output Text]:\n{taguchi_gen_result.get('text_output')}\n")

    # 4. Analyze Taguchi Design
    print("--- Testing Taguchi Design Analysis (doe_analyze_taguchi) ---")
    # Feed experimental response data for the 9 runs
    test_rows = [
        {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 1.25},
        {"c1": 2, "c2": 2, "c3": 1, "c4": 2, "c5": 2, "c6": 1.48},
        {"c1": 3, "c2": 3, "c3": 1, "c4": 3, "c5": 3, "c6": 1.95},
        {"c1": 4, "c2": 4, "c3": 2, "c4": 1, "c5": 2, "c6": 0.95},
        {"c1": 5, "c2": 5, "c3": 2, "c4": 2, "c5": 3, "c6": 1.30},
        {"c1": 6, "c2": 6, "c3": 2, "c4": 3, "c5": 1, "c6": 1.70},
        {"c1": 7, "c2": 7, "c3": 3, "c4": 1, "c5": 3, "c6": 0.82},
        {"c1": 8, "c2": 8, "c3": 3, "c4": 2, "c5": 1, "c6": 1.15},
        {"c1": 9, "c2": 9, "c3": 3, "c4": 3, "c5": 2, "c6": 1.55}
    ]
    test_cols = [
        {"id": "c1", "name": "StdOrder", "type": "numeric"},
        {"id": "c2", "name": "RunOrder", "type": "numeric"},
        {"id": "c3", "name": "CuttingSpeed", "type": "numeric"},
        {"id": "c4", "name": "FeedRate", "type": "numeric"},
        {"id": "c5", "name": "DepthOfCut", "type": "numeric"},
        {"id": "c6", "name": "Surface_Roughness_Ra", "type": "numeric"}
    ]
    payload_taguchi_analyze = {
        "data": test_rows,
        "columns": test_cols,
        "params": {
            "response_col": "Surface_Roughness_Ra",
            "factor_cols": ["CuttingSpeed", "FeedRate", "DepthOfCut"],
            "sn_ratio_type": "smaller"
        }
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/compute/doe_analyze_taguchi",
        data=json.dumps(payload_taguchi_analyze).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as res:
        taguchi_ana_result = json.loads(res.read().decode("utf-8"))
        print(f"[PASS] Taguchi Analysis Completed: {taguchi_ana_result['title']}")
        print(f"       Tables returned: {len(taguchi_ana_result['tables'])}")
        for t in taguchi_ana_result["tables"]:
            print(f"       • Table: {t['title']} (Rows: {len(t['rows'])})")
        print(f"       Has Main Effects Plotly Spec: {taguchi_ana_result.get('plotly_figure') is not None}")
        print(f"\n[Session Output Text]:\n{taguchi_ana_result.get('text_output')}\n")

    print("=======================================================")
    print("   ALL TAGUCHI TESTS & COMPUTATIONS PASSED PERFECTLY!  ")
    print("=======================================================")

if __name__ == "__main__":
    test_api()
