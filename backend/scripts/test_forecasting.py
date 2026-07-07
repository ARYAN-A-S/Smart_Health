import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def run_forecasting_tests():
    print("Testing ML Forecasting Engine on live server...")

    # 1. Trigger Model Retrain
    print("Triggering model training via API...")
    r = requests.post(f"{BASE_URL}/api/forecasting/retrain")
    assert r.status_code == 200, f"Retraining failed: {r.text}"
    retrain_res = r.json()
    print("[SUCCESS] Model retraining successful!")
    print("   - Metadata:", retrain_res["metadata"])

    # 2. Get status
    print("\nRetrieving model status...")
    r = requests.get(f"{BASE_URL}/api/forecasting/status")
    assert r.status_code == 200
    status_res = r.json()
    print("[SUCCESS] Model status:")
    print(f"   - Status: {status_res['status']}")
    print(f"   - Last Trained: {status_res['last_trained']}")
    print(f"   - RMSEs: {status_res['metrics']}")
    assert status_res['status'] == 'active'

    # 3. Retrieve Tokawade PHC (ID 7) Risk State
    # Tokawade PHC is a low-history, under-resourced centre. We prove it doesn't fail.
    print("\nRetrieving Tokawade PHC (ID 7) risk state with real ML forecasts...")
    r = requests.get(f"{BASE_URL}/api/centres/7/risk-state")
    assert r.status_code == 200, f"Failed to get risk state: {r.text}"
    risk_state = r.json()

    print("[SUCCESS] Retrieved risk state successfully!")
    print(f"   - Centre Name: {risk_state['centre_name']}")
    print(f"   - Predicted Footfall (Next 7 Days): {risk_state['predicted_footfall_next_7_days']}")
    print(f"   - Predicted Bed Demand (Next 7 Days): {risk_state['predicted_bed_demand_next_7_days']}")
    
    assert len(risk_state['predicted_footfall_next_7_days']) == 7, "Should have 7 days footfall forecast!"
    assert len(risk_state['predicted_bed_demand_next_7_days']) == 7, "Should have 7 days bed forecast!"

    print("\nStock Forecast Items:")
    for f in risk_state['stock_forecasts']:
        print(f"   - Drug: {f['drug_name']}")
        print(f"     - Current Stock: {f['current_stock']} units")
        print(f"     - Expected Days to Stockout: {f['predicted_days_to_stockout']} days")
        print(f"     - Uncertainty: [{f['uncertainty_lower']} to {f['uncertainty_upper']}] days")
        print(f"     - Reasoning: {f['reasoning']}")

        # Assertions
        assert f['predicted_days_to_stockout'] >= 0.0
        assert f['uncertainty_lower'] <= f['predicted_days_to_stockout'] <= f['uncertainty_upper'], \
            f"Uncertainty band check failed for {f['drug_name']}: {f['uncertainty_lower']} <= {f['predicted_days_to_stockout']} <= {f['uncertainty_upper']}"

    print("\n--- ALL FORECASTING ENGINE AND SIMULATION TESTS PASSED! ---")

if __name__ == "__main__":
    run_forecasting_tests()
