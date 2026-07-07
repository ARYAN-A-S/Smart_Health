import os
import sys
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.database import SessionLocal, DATABASE_URL
from app.models.models import (
    Centre,
    Drug,
    StockLog,
    FootfallLog,
    BedStatus,
    StaffAttendance,
    User
)

def run_verification():
    print(f"Connecting to database: {DATABASE_URL}")
    db: Session = SessionLocal()
    try:
        print("\n--- TABLE RECORD COUNTS ---")
        print(f"Centres: {db.query(Centre).count()}")
        print(f"Drugs: {db.query(Drug).count()}")
        print(f"Stock Logs: {db.query(StockLog).count()}")
        print(f"Footfall Logs: {db.query(FootfallLog).count()}")
        print(f"Bed Status Records: {db.query(BedStatus).count()}")
        print(f"Staff Attendance Records: {db.query(StaffAttendance).count()}")
        print(f"Users: {db.query(User).count()}")

        print("\n--- CENTRES LIST ---")
        for c in db.query(Centre).all():
            print(f"ID {c.id}: {c.name} ({c.type}) | Pop: {c.population_served} | Tier: {c.tier_classification} | Lat: {c.lat}, Lng: {c.lng}")

        print("\n--- DRUGS LIST ---")
        for d in db.query(Drug).all():
            print(f"ID {d.id}: {d.name} ({d.unit}) | Safety Stock: {d.safety_stock_level}")

        print("\n--- VERIFYING ANOMALIES ---")

        # 1. Wada PHC (Silent Centre)
        # Wada PHC should have stopped reporting in the last 12 days.
        print("\n1. Wada PHC (Silent Centre Anomaly):")
        wada = db.query(Centre).filter_by(name="Wada PHC").first()
        if wada:
            cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=12)
            recent_logs = db.query(FootfallLog).filter(
                FootfallLog.centre_id == wada.id,
                FootfallLog.timestamp >= cutoff
            ).count()
            total_logs = db.query(FootfallLog).filter_by(centre_id=wada.id).count()
            print(f"   Total Wada Footfall Logs: {total_logs}")
            print(f"   Wada Footfall Logs in the last 12 days (cutoff: {cutoff.strftime('%Y-%m-%d')}): {recent_logs}")
            if recent_logs == 0:
                print("   [SUCCESS] Wada PHC is completely silent in the last 12 days.")
            else:
                print("   [WARNING] Wada PHC has recent logs.")

        # 2. Murbad PHC (High Consumption Anomaly)
        # Implausible consumption-vs-footfall ratio for Amoxicillin in the last 15 days
        print("\n2. Murbad PHC (High Consumption Anomaly):")
        murbad = db.query(Centre).filter_by(name="Murbad PHC").first()
        amoxicillin = db.query(Drug).filter_by(name="Amoxicillin").first()
        if murbad and amoxicillin:
            cutoff_15 = datetime.datetime.utcnow() - datetime.timedelta(days=15)
            
            # Recent stats
            recent_cons = db.query(func.sum(StockLog.quantity_change)).filter(
                StockLog.centre_id == murbad.id,
                StockLog.drug_id == amoxicillin.id,
                StockLog.quantity_change < 0,
                StockLog.timestamp >= cutoff_15
            ).scalar() or 0
            
            recent_footfall = db.query(func.sum(FootfallLog.count)).filter(
                FootfallLog.centre_id == murbad.id,
                FootfallLog.timestamp >= cutoff_15
            ).scalar() or 0
            
            # Older stats
            old_cons = db.query(func.sum(StockLog.quantity_change)).filter(
                StockLog.centre_id == murbad.id,
                StockLog.drug_id == amoxicillin.id,
                StockLog.quantity_change < 0,
                StockLog.timestamp < cutoff_15
            ).scalar() or 0
            
            old_footfall = db.query(func.sum(FootfallLog.count)).filter(
                FootfallLog.centre_id == murbad.id,
                FootfallLog.timestamp < cutoff_15
            ).scalar() or 0
            
            recent_ratio = abs(recent_cons) / (recent_footfall if recent_footfall > 0 else 1)
            old_ratio = abs(old_cons) / (old_footfall if old_footfall > 0 else 1)
            
            print(f"   Last 15 days Amoxicillin consumption: {abs(recent_cons)} units | Footfall: {recent_footfall} | Ratio: {recent_ratio:.2f} per patient")
            print(f"   Prior days Amoxicillin consumption: {abs(old_cons)} units | Footfall: {old_footfall} | Ratio: {old_ratio:.2f} per patient")
            if recent_ratio > old_ratio * 3:
                print(f"   [SUCCESS] Confirmed anomalous consumption-to-footfall ratio spike! (Recent: {recent_ratio:.2f} vs Old: {old_ratio:.2f})")
            else:
                print("   [WARNING] Consumption ratio spike not detected.")

        # 3. Tokawade PHC (Under-resourced Centre Anomaly)
        # Doctor attendance low, bed occupancy high, frequent stockouts
        print("\n3. Tokawade PHC (Under-resourced Centre Anomaly):")
        tokawade = db.query(Centre).filter_by(name="Tokawade PHC").first()
        paracetamol = db.query(Drug).filter_by(name="Paracetamol").first()
        ors = db.query(Drug).filter_by(name="ORS").first()
        if tokawade:
            # Attendance
            total_doc_days = db.query(StaffAttendance).filter_by(centre_id=tokawade.id, staff_role="doctor").count()
            present_doc_days = db.query(StaffAttendance).filter_by(centre_id=tokawade.id, staff_role="doctor", present=True).count()
            doc_rate = (present_doc_days / total_doc_days * 100) if total_doc_days > 0 else 0
            print(f"   Doctor Attendance Rate: {doc_rate:.1f}% ({present_doc_days}/{total_doc_days} days present)")
            
            # Beds
            avg_occupancy = db.query(func.avg(BedStatus.occupied_beds)).filter_by(centre_id=tokawade.id).scalar() or 0
            print(f"   Average Bed Occupancy: {avg_occupancy:.1f} beds occupied out of 6 total beds")
            
            # Stockout verification (Paracetamol)
            # Find current stock (cumulative quantity changes)
            if paracetamol:
                para_stock = db.query(func.sum(StockLog.quantity_change)).filter_by(centre_id=tokawade.id, drug_id=paracetamol.id).scalar() or 0
                print(f"   Current Paracetamol stock: {para_stock} units")
            if ors:
                ors_stock = db.query(func.sum(StockLog.quantity_change)).filter_by(centre_id=tokawade.id, drug_id=ors.id).scalar() or 0
                print(f"   Current ORS stock: {ors_stock} units")
                
            if doc_rate < 40 and avg_occupancy >= 4.8 and (para_stock <= 0 or ors_stock <= 0):
                print("   [SUCCESS] Tokawade PHC exhibits clear under-resourcing markers.")
            else:
                print("   [WARNING] Under-resourcing markers not fully present.")

    finally:
        db.close()

if __name__ == "__main__":
    run_verification()
