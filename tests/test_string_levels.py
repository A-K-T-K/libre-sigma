import json
import urllib.request

def test_string_levels():
    print("Testing Taguchi analysis with text/string factor level names (Low, Medium, High)...")
    payload = {
        "data": [
            {"Speed": "Low", "Feed": "Low", "Doc": "Low", "Ra": 1.15},
            {"Speed": "Low", "Feed": "Med", "Doc": "Med", "Ra": 1.45},
            {"Speed": "Low", "Feed": "High", "Doc": "High", "Ra": 2.08},
            {"Speed": "Med", "Feed": "Low", "Doc": "Med", "Ra": 0.95},
            {"Speed": "Med", "Feed": "Med", "Doc": "High", "Ra": 1.30},
            {"Speed": "Med", "Feed": "High", "Doc": "Low", "Ra": 1.70},
            {"Speed": "High", "Feed": "Low", "Doc": "High", "Ra": 0.92},
            {"Speed": "High", "Feed": "Med", "Doc": "Low", "Ra": 1.18},
            {"Speed": "High", "Feed": "High", "Doc": "Med", "Ra": 1.42},
        ],
        "columns": [
            {"id": "Speed", "name": "Speed", "type": "text"},
            {"id": "Feed", "name": "Feed", "type": "text"},
            {"id": "Doc", "name": "Doc", "type": "text"},
            {"id": "Ra", "name": "Ra", "type": "numeric"},
        ],
        "params": {
            "response_col": "Ra",
            "factor_cols": ["Speed", "Feed", "Doc"],
            "sn_ratio_type": "larger"
        }
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/compute/doe_analyze_taguchi",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as res:
        result = json.loads(res.read().decode("utf-8"))
        print("[PASS] Analysis completed successfully with string levels!")
        print("Title:", result["title"])
        print("Num Figures:", len(result.get("plotly_figures", [])))
        for t in result["tables"]:
            print(f"Table '{t['title']}': {len(t['rows'])} rows")
            for r in t['rows']:
                print(" ", r)

if __name__ == "__main__":
    test_string_levels()
