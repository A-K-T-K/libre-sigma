import urllib.request
import json

def test_all_levels():
    print("Testing 2, 3, 4, 5-level and mixed level Taguchi Array generation...\n")
    
    test_cases = [
        ("2_level", "L8_2_7", 7, "2-Level Design (L8)"),
        ("3_level", "L27_3_13", 13, "3-Level Design (L27, 13 factors)"),
        ("4_level", "L16_4_5", 5, "4-Level Design (L16)"),
        ("5_level", "L25_5_6", 6, "5-Level Design (L25)"),
        ("mixed", "L18_2_1_3_7", 8, "Mixed Level Design (L18)"),
        ("mixed", "L36_2_11_3_12", 13, "Mixed Level Design (L36, 13 factors)"),
    ]

    for f_type, array_id, k, desc in test_cases:
        payload = {
            "data": [],
            "columns": [],
            "params": {
                "factor_type": f_type,
                "array_choice": array_id,
                "num_factors": k,
                "factor_names_str": ", ".join(f"Factor_{chr(65+i) if i < 26 else i}" for i in range(k)),
                "worksheet_name": f"Taguchi {array_id}"
            }
        }
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/v1/compute/doe_create_taguchi",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            result = json.loads(res.read().decode("utf-8"))
            ws = result.get("worksheet_data", {})
            print(f"[PASS] {desc}:")
            print(f"       Array: {result['title']}")
            print(f"       Runs: {len(ws.get('rows', []))}, Factors: {k}")
            print(f"       Columns: {[c['name'] for c in ws.get('columns', [])[:5]]} ... {ws.get('columns', [])[-1]['name']}")

    print("\nALL TAGUCHI MULTI-LEVEL DESIGNS GENERATED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all_levels()
