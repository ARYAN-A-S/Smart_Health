import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def run_anomaly_tests():
    print("Testing Anomaly Layer & Data Trust on live server...")

    # 1. Trigger complete anomaly scan
    print("Triggering anomaly scan...")
    r = requests.post(f"{BASE_URL}/api/anomaly/analyze")
    assert r.status_code == 200, f"Failed to run anomaly analysis: {r.text}"
    scan_res = r.json()
    print("[SUCCESS] Scan response:")
    for name, stats in scan_res["results"].items():
        print(f"   - {name}: Data Reliability Score = {stats['data_reliability_score']}")

    # 2. Get active flags
    print("\nRetrieving active reliability flags...")
    r = requests.get(f"{BASE_URL}/api/flags?resolved=false")
    assert r.status_code == 200, "Failed to get active flags"
    flags = r.json()
    reliability_flags = [f for f in flags if f["flag_type"] == "reliability"]
    print(f"[SUCCESS] Retrieved {len(reliability_flags)} active reliability flags:")
    for f in reliability_flags:
        print(f"   - Centre ID {f['centre_id']} | Metric: {f['triggering_metric']} | Value: {f['value']} | Threshold: {f['threshold']}")

    # Assertions for Wada PHC (Silent Centre Anomaly - ID 5)
    wada_flags = [f for f in reliability_flags if f["centre_id"] == 5 and f["triggering_metric"] == "missing_reports"]
    assert len(wada_flags) > 0, "Wada PHC (ID 5) should have a missing_reports reliability flag!"
    print("[SUCCESS] Wada PHC has been correctly flagged for missing reports (silent centre).")

    # Assertions for Murbad PHC (High Consumption Anomaly - ID 6)
    murbad_flags = [f for f in reliability_flags if f["centre_id"] == 6 and "consumption_vs_footfall_Amoxicillin" in f["triggering_metric"]]
    assert len(murbad_flags) > 0, "Murbad PHC (ID 6) should have an Amoxicillin consumption mismatch reliability flag!"
    print("[SUCCESS] Murbad PHC has been correctly flagged for implausible Amoxicillin consumption-to-footfall ratio.")

    # 3. Retrieve Centre 5 (Wada) Risk State
    print("\nRetrieving Wada PHC (ID 5) risk state...")
    r = requests.get(f"{BASE_URL}/api/centres/5/risk-state")
    assert r.status_code == 200
    wada_risk = r.json()
    print(f"[SUCCESS] Wada PHC Data Reliability Score: {wada_risk['data_reliability_score']}")
    print(f"   - Reasons: {wada_risk['reliability_reasons']}")
    assert wada_risk['data_reliability_score'] < 100, "Wada's reliability score should be penalized!"

    # 4. Retrieve Centre 6 (Murbad) Risk State
    print("\nRetrieving Murbad PHC (ID 6) risk state...")
    r = requests.get(f"{BASE_URL}/api/centres/6/risk-state")
    assert r.status_code == 200
    murbad_risk = r.json()
    print(f"[SUCCESS] Murbad PHC Data Reliability Score: {murbad_risk['data_reliability_score']}")
    print(f"   - Reasons: {murbad_risk['reliability_reasons']}")
    assert murbad_risk['data_reliability_score'] < 100, "Murbad's reliability score should be penalized!"

    # 5. Retrieve Centre 4 (Shirgaon) Risk State (Normal)
    print("\nRetrieving Shirgaon PHC (ID 4) risk state (Normal peer control)...")
    r = requests.get(f"{BASE_URL}/api/centres/4/risk-state")
    assert r.status_code == 200
    shirgaon_risk = r.json()
    print(f"[SUCCESS] Shirgaon PHC Data Reliability Score: {shirgaon_risk['data_reliability_score']}")
    print(f"   - Reasons: {shirgaon_risk['reliability_reasons']}")
    assert shirgaon_risk['data_reliability_score'] == 100.0, "Shirgaon PHC reliability score should be perfect (100.0)!"

    print("\n--- ALL ANOMALY DETECTION AND DATA TRUST TESTS PASSED! ---")

if __name__ == "__main__":
    run_anomaly_tests()
