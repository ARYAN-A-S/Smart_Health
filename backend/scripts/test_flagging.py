import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def run_flagging_tests():
    print("Testing Underperformance Flagging on live server...")

    # 1. Trigger complete adequacy scan
    print("Triggering resource adequacy and underperformance scan...")
    r = requests.post(f"{BASE_URL}/api/flags/analyze")
    assert r.status_code == 200, f"Failed to run flagging analysis: {r.text}"
    print("[SUCCESS] Flagging analysis completed successfully.")

    # 2. Get active adequacy flags
    print("\nRetrieving active adequacy flags...")
    r = requests.get(f"{BASE_URL}/api/flags?resolved=false")
    assert r.status_code == 200, "Failed to get active flags"
    flags = r.json()
    adequacy_flags = [f for f in flags if f["flag_type"] == "adequacy"]
    print(f"[SUCCESS] Retrieved {len(adequacy_flags)} active adequacy flags:")
    for f in adequacy_flags:
        print(f"   - Centre ID {f['centre_id']} | Metric: {f['triggering_metric']} | Value: {f['value']} | Threshold: {f['threshold']}")

    # Assertions for Tokawade PHC (Under-resourced Centre Anomaly - ID 7)
    tokawade_flags = [f for f in adequacy_flags if f["centre_id"] == 7]
    assert len(tokawade_flags) >= 3, "Tokawade PHC (ID 7) should have multiple adequacy flags (absenteeism, overcrowding, stockouts)!"
    print("[SUCCESS] Tokawade PHC has been correctly flagged for multiple resource adequacy violations.")

    # Check for specific metrics on Tokawade
    absenteeism = next((f for f in tokawade_flags if f["triggering_metric"] == "doctor_absenteeism"), None)
    overcrowding = next((f for f in tokawade_flags if f["triggering_metric"] == "bed_overcrowding"), None)
    para_stockout = next((f for f in tokawade_flags if f["triggering_metric"] == "stockout_Paracetamol"), None)
    
    assert absenteeism is not None, "Tokawade lacks doctor absenteeism flag!"
    assert absenteeism["value"] < 40.0, f"Doctor attendance rate should be low (seeded ~26.7%). Got: {absenteeism['value']}"
    print(f"[SUCCESS] Doctor absenteeism correctly flagged (Rate: {absenteeism['value']}% < Target: {absenteeism['threshold']}%)")
    
    assert overcrowding is not None, "Tokawade lacks bed overcrowding flag!"
    assert overcrowding["value"] > 85.0, f"Bed occupancy level should be high (seeded ~91.6%). Got: {overcrowding['value']}"
    print(f"[SUCCESS] Bed overcrowding correctly flagged (Occupancy: {overcrowding['value']}% > Target: {overcrowding['threshold']}%)")

    assert para_stockout is not None, "Tokawade lacks Paracetamol stockout flag!"
    assert para_stockout["value"] > 10.0, f"Paracetamol stockout frequency should be high. Got: {para_stockout['value']}"
    print(f"[SUCCESS] Paracetamol stockout correctly flagged (Frequency: {para_stockout['value']}% > Target: {para_stockout['threshold']}%)")

    # 3. Retrieve Centre 7 (Tokawade) Risk State and verify separate scores
    print("\nRetrieving Tokawade PHC (ID 7) risk state...")
    r = requests.get(f"{BASE_URL}/api/centres/7/risk-state")
    assert r.status_code == 200
    tokawade_risk = r.json()
    print(f"[SUCCESS] Tokawade PHC Risk State Scores:")
    print(f"   - Data Reliability Score: {tokawade_risk['data_reliability_score']}")
    print(f"   - Resource Adequacy Score: {tokawade_risk['resource_adequacy_score']}")
    print(f"   - Adequacy Reasons: {tokawade_risk['adequacy_reasons']}")
    
    # Assert they are separate and correct
    assert tokawade_risk['data_reliability_score'] == 100.0, "Tokawade reporting is fully reliable! Reliability score should be perfect (100.0)."
    assert tokawade_risk['resource_adequacy_score'] <= 25.0, "Tokawade is severely under-resourced! Adequacy score should be penalized (<= 25.0)."
    print("[SUCCESS] Data Reliability and Resource Adequacy scores are correctly segregated and computed.")

    print("\n--- ALL UNDERPERFORMANCE FLAGGING AND PEER COMPARISON TESTS PASSED! ---")

if __name__ == "__main__":
    run_flagging_tests()
