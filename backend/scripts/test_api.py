import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("Testing connection to FastAPI at:", BASE_URL)
    
    # 1. Root check
    try:
        r = requests.get(f"{BASE_URL}/")
        r.raise_for_status()
        print("[SUCCESS] API Root:", r.json())
    except Exception as e:
        print(f"[FAIL] Could not connect to API: {e}")
        print("Please ensure the FastAPI server is running (e.g. uvicorn app.main:app --reload)")
        sys.exit(1)

    # 2. GET Centres
    r = requests.get(f"{BASE_URL}/api/centres")
    assert r.status_code == 200, "Failed to get centres"
    centres = r.json()
    print(f"[SUCCESS] Retrieved {len(centres)} centres.")
    for c in centres[:2]:
        print(f"   - Centre: {c['name']} ({c['type']})")

    # 3. GET Risk State
    centre_id = 7  # Tokawade PHC (Under-resourced)
    r = requests.get(f"{BASE_URL}/api/centres/{centre_id}/risk-state")
    assert r.status_code == 200, "Failed to get risk state"
    risk_state = r.json()
    print(f"[SUCCESS] Risk State for Centre {centre_id} ({risk_state['centre_name']}):")
    print(f"   - Data Reliability Score: {risk_state['data_reliability_score']}")
    print(f"   - Resource Adequacy Score: {risk_state['resource_adequacy_score']}")
    print(f"   - Reliability Reasons: {risk_state['reliability_reasons']}")
    print(f"   - Adequacy Reasons: {risk_state['adequacy_reasons']}")
    print(f"   - Paracetamol Forecast:")
    para_f = next((x for x in risk_state['stock_forecasts'] if x['drug_name'] == "Paracetamol"), None)
    if para_f:
        print(f"     - Current Stock: {para_f['current_stock']}")
        print(f"     - Days to Stockout: {para_f['predicted_days_to_stockout']}")
        print(f"     - Reasoning: {para_f['reasoning']}")

    # 4. Ingest Field Report (Footfall)
    # We will submit a footfall report for Kasara CHC (ID 2)
    payload = {
        "centre_id": 2,
        "report_type": "footfall",
        "source": "whatsapp",
        "reported_by": "anm_savita",
        "data": {"count": 142}
    }
    r = requests.post(f"{BASE_URL}/api/reports/submit", json=payload)
    assert r.status_code == 201, f"Failed to submit footfall report: {r.text}"
    print("[SUCCESS] Ingested footfall field report:", r.json())

    # 5. Verify log was recorded
    r = requests.get(f"{BASE_URL}/api/footfall?centre_id=2")
    assert r.status_code == 200
    logs = r.json()
    latest_log = logs[0]
    print(f"[SUCCESS] Verified recorded log: count={latest_log['count']}, source={latest_log['source']}, reporter={latest_log['reported_by']}")
    assert latest_log['count'] == 142
    assert latest_log['reported_by'] == "anm_savita"

    # 6. Ingest Stock Report (Consumption)
    # Deduct 50 tablets of IFA (Drug ID 5) from Shirgaon PHC (ID 4)
    payload_stock = {
        "centre_id": 4,
        "report_type": "stock",
        "source": "voice",
        "reported_by": "pharmacist_anil",
        "data": {
            "drug_id": 5,
            "quantity_change": -50
        }
    }
    r = requests.post(f"{BASE_URL}/api/reports/submit", json=payload_stock)
    assert r.status_code == 201, f"Failed to submit stock report: {r.text}"
    print("[SUCCESS] Ingested stock field report:", r.json())

    print("\n--- ALL CORE API CRUD AND INGESTION TESTS PASSED! ---")

if __name__ == "__main__":
    run_tests()
