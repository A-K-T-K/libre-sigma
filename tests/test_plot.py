import json
import urllib.request

def test_doe_plot():
    # Fetch sample data and run doe_analyze_taguchi
    payload = {
        "data": [
            {"CuttingSpeed": 1, "FeedRate": 1, "DepthOfCut": 1, "Surface_Roughness_Ra": 1.15},
            {"CuttingSpeed": 1, "FeedRate": 2, "DepthOfCut": 2, "Surface_Roughness_Ra": 1.45},
            {"CuttingSpeed": 1, "FeedRate": 3, "DepthOfCut": 3, "Surface_Roughness_Ra": 2.08},
            {"CuttingSpeed": 2, "FeedRate": 1, "DepthOfCut": 2, "Surface_Roughness_Ra": 0.95},
            {"CuttingSpeed": 2, "FeedRate": 2, "DepthOfCut": 3, "Surface_Roughness_Ra": 1.30},
            {"CuttingSpeed": 2, "FeedRate": 3, "DepthOfCut": 1, "Surface_Roughness_Ra": 1.70},
            {"CuttingSpeed": 3, "FeedRate": 1, "DepthOfCut": 3, "Surface_Roughness_Ra": 0.92},
            {"CuttingSpeed": 3, "FeedRate": 2, "DepthOfCut": 1, "Surface_Roughness_Ra": 1.18},
            {"CuttingSpeed": 3, "FeedRate": 3, "DepthOfCut": 2, "Surface_Roughness_Ra": 1.42},
        ],
        "columns": [
            {"id": "CuttingSpeed", "name": "CuttingSpeed", "type": "numeric"},
            {"id": "FeedRate", "name": "FeedRate", "type": "numeric"},
            {"id": "DepthOfCut", "name": "DepthOfCut", "type": "numeric"},
            {"id": "Surface_Roughness_Ra", "name": "Surface_Roughness_Ra", "type": "numeric"},
        ],
        "params": {
            "response_col": "Surface_Roughness_Ra",
            "factor_cols": ["CuttingSpeed", "FeedRate", "DepthOfCut"],
            "sn_ratio_type": "smaller"
        }
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/compute/doe_analyze_taguchi",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as res:
        result = json.loads(res.read().decode("utf-8"))
        fig = result.get("plotly_figure")
        print("Plotly Figure Present:", fig is not None)
        if fig:
            print("Traces:", len(fig.get("data", [])))
            for tr in fig.get("data", []):
                print("  Trace:", tr.get("name"), "xaxis:", tr.get("xaxis"), "x:", tr.get("x"), "y:", tr.get("y"))
            print("Layout Annotations:", len(fig.get("layout", {}).get("annotations", [])))
            print("Layout Shapes:", len(fig.get("layout", {}).get("shapes", [])))
            print("Layout X Axes:", [k for k in fig.get("layout", {}).keys() if "xaxis" in k])

if __name__ == "__main__":
    test_doe_plot()
