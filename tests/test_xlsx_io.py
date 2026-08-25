import io
import requests

API = "http://127.0.0.1:8000/api/v1"

def test_xlsx_roundtrip():
    payload = {
        "title": "Quality_Study",
        "worksheets": [
            {
                "id": "ws-1",
                "name": "Machine_Outputs",
                "columns": [
                    {"id": "c1", "name": "Diameter", "type": "numeric"},
                    {"id": "c2", "name": "Hardness", "type": "numeric"},
                    {"id": "c3", "name": "Operator", "type": "text"}
                ],
                "rows": [
                    {"c1": 25.4, "c2": 62.1, "c3": "Alice"},
                    {"c1": 25.6, "c2": 61.8, "c3": "Bob"},
                    {"c1": 25.3, "c2": 63.0, "c3": "Charlie"},
                    {"c1": 25.5, "c2": None, "c3": "Alice"}
                ]
            }
        ]
    }

    # 1. Export XLSX
    r_exp = requests.post(f"{API}/project/xlsx/export", json=payload)
    assert r_exp.status_code == 200, f"Export failed: {r_exp.text}"
    xlsx_bytes = r_exp.content
    print(f"XLSX Export: SUCCESS ({len(xlsx_bytes)} bytes)")

    # 2. Import XLSX
    files = {"file": ("Quality_Study.xlsx", io.BytesIO(xlsx_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r_imp = requests.post(f"{API}/project/xlsx/import", files=files)
    assert r_imp.status_code == 200, f"Import failed: {r_imp.text}"
    data = r_imp.json()
    assert len(data["worksheets"]) == 1
    assert data["worksheets"][0]["name"] == "Machine_Outputs"
    assert len(data["worksheets"][0]["columns"]) == 3
    print(f"XLSX Import: SUCCESS ({len(data['worksheets'][0]['rows'])} rows imported)")

if __name__ == "__main__":
    test_xlsx_roundtrip()
    print("All Excel I/O tests passed successfully!")
