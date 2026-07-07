import os
import sys
from sqlalchemy.orm import Session
from sqlalchemy import func

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.database import SessionLocal
from app.models.models import Centre, Drug, StockLog, Transfer
from app.services.forecasting import forecast_footfall_next_7_days, forecast_days_to_stockout

def debug():
    db = SessionLocal()
    try:
        centres = db.query(Centre).all()
        drugs = db.query(Drug).all()
        
        print("--- DEBUGGING SURPLUS & DEFICIT GROUPS ---")
        for drug in drugs:
            print(f"\nDrug: {drug.name} (Safety Stock: {drug.safety_stock_level})")
            
            for centre in centres:
                # Reliability check
                from app.services.anomaly import run_anomaly_analysis_for_centre
                reliability = run_anomaly_analysis_for_centre(db, centre.id)
                
                # Get current stock
                current_stock = db.query(func.sum(StockLog.quantity_change)).filter(
                    StockLog.centre_id == centre.id,
                    StockLog.drug_id == drug.id
                ).scalar() or 0

                # Get forecasts
                predicted_footfall = forecast_footfall_next_7_days(centre.id, db)
                days_to_stockout, _, _, _ = forecast_days_to_stockout(
                    centre_id=centre.id,
                    drug_id=drug.id,
                    current_stock=current_stock,
                    predicted_footfall_7=predicted_footfall,
                    db=db
                )
                
                # Classify
                status = "NORMAL"
                if reliability < 80.0:
                    status = f"UNRELIABLE ({reliability:.1f})"
                elif days_to_stockout < 7.0 or current_stock < drug.safety_stock_level:
                    target = int(drug.safety_stock_level * 1.5)
                    deficit_qty = max(0, target - current_stock)
                    status = f"DEFICIT (Qty: {deficit_qty}, Days: {days_to_stockout:.1f})"
                elif days_to_stockout > 14.0 and current_stock > (drug.safety_stock_level * 1.2):
                    surplus_qty = int(current_stock - (drug.safety_stock_level * 1.2))
                    status = f"SURPLUS (Qty: {surplus_qty}, Days: {days_to_stockout:.1f})"
                    
                print(f"   - {centre.name}: Stock: {current_stock} | Forecast Days: {days_to_stockout:.1f} | Class: {status}")

    finally:
        db.close()

if __name__ == "__main__":
    debug()
