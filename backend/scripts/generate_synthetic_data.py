import os
import sys
import datetime
import random
from sqlalchemy.orm import Session

# Add backend directory to path to enable app imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.database import Base, engine, SessionLocal
from app.models.models import (
    Centre,
    Drug,
    StockLog,
    FootfallLog,
    BedStatus,
    StaffAttendance,
    User
)

def create_db_tables():
    print("Dropping existing tables...")
    Base.metadata.drop_all(bind=engine)
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

def seed_data():
    db: Session = SessionLocal()
    try:
        print("Seeding centres...")
        centres_data = [
            # 3 CHCs (Cuttack Sadar CHC is Main Hub, Athagarh and Banki are Spoke CHCs)
            {"name": "Cuttack Sadar CHC", "type": "CHC", "lat": 20.4625, "lng": 85.8792, "population_served": 120000, "tier_classification": "urban"},
            {"name": "Athagarh CHC", "type": "CHC", "lat": 20.5312, "lng": 85.6241, "population_served": 85000, "tier_classification": "rural"},
            {"name": "Banki CHC", "type": "CHC", "lat": 20.3541, "lng": 85.5324, "population_served": 95000, "tier_classification": "rural"},
            # 7 PHCs spread across Cuttack district
            {"name": "Salepur PHC", "type": "PHC", "lat": 20.5912, "lng": 86.1123, "population_served": 15000, "tier_classification": "rural"},
            {"name": "Badamba PHC", "type": "PHC", "lat": 20.4212, "lng": 85.2543, "population_served": 18000, "tier_classification": "rural"}, # Anomaly 1: Silent Centre
            {"name": "Tigiria PHC", "type": "PHC", "lat": 20.4824, "lng": 85.5291, "population_served": 12000, "tier_classification": "rural"}, # Anomaly 2: High Consumption
            {"name": "Niali PHC", "type": "PHC", "lat": 20.1412, "lng": 86.0451, "population_served": 14000, "tier_classification": "tribal"}, # Anomaly 3: Under-resourced
            {"name": "Narasinghpur PHC", "type": "PHC", "lat": 20.4514, "lng": 85.0912, "population_served": 11000, "tier_classification": "tribal"},
            {"name": "Choudwar PHC", "type": "PHC", "lat": 20.5141, "lng": 85.9123, "population_served": 22000, "tier_classification": "urban"},
            {"name": "Baranga PHC", "type": "PHC", "lat": 20.3912, "lng": 85.8324, "population_served": 25000, "tier_classification": "urban"},
        ]
        
        centres = []
        for c in centres_data:
            centre = Centre(**c)
            db.add(centre)
            centres.append(centre)
        db.commit()
        
        # Reload centres to get IDs
        for c in centres:
            db.refresh(c)
        print(f"Seeded {len(centres)} centres.")

        print("Seeding drugs...")
        drugs_data = [
            {"name": "Paracetamol", "unit": "tablets", "safety_stock_level": 1000},
            {"name": "Amoxicillin", "unit": "tablets", "safety_stock_level": 500},
            {"name": "ORS", "unit": "packets", "safety_stock_level": 300},
            {"name": "Insulin", "unit": "vials", "safety_stock_level": 50},
            {"name": "IFA (Iron Folic Acid)", "unit": "tablets", "safety_stock_level": 800},
        ]
        drugs = []
        for d in drugs_data:
            drug = Drug(**d)
            db.add(drug)
            drugs.append(drug)
        db.commit()
        
        for d in drugs:
            db.refresh(d)
        print(f"Seeded {len(drugs)} drugs.")

        print("Seeding users...")
        users_data = [
            {"name": "District Administrator", "role": "district_admin", "centre_id": None, "phone_number": "+919000000000"},
            {"name": "Salepur Staff", "role": "field_staff", "centre_id": centres[3].id, "phone_number": "+919111111111"},
            {"name": "ANM Lata (Salepur)", "role": "asha_anm", "centre_id": centres[3].id, "phone_number": "+919999999991"},
            {"name": "ANM Savita (Badamba)", "role": "asha_anm", "centre_id": centres[4].id, "phone_number": "+919999999992"},
            {"name": "ANM Rekha (Tigiria)", "role": "asha_anm", "centre_id": centres[5].id, "phone_number": "+919999999993"},
            {"name": "ANM Geeta (Niali)", "role": "asha_anm", "centre_id": centres[6].id, "phone_number": "+919999999994"},
        ]
        for u in users_data:
            user = User(**u)
            db.add(user)
        db.commit()
        print("Seeded baseline users.")

        # History parameters
        num_days = 90
        start_date = datetime.datetime.utcnow() - datetime.timedelta(days=num_days)
        random.seed(42)  # For reproducible synthetic data

        # Track inventory levels in memory to simulate logical consumption
        # initial stock levels
        inventory = {}
        for c in centres:
            inventory[c.id] = {
                drugs[0].id: 4000, # Paracetamol
                drugs[1].id: 2000, # Amoxicillin
                drugs[2].id: 1200, # ORS
                drugs[3].id: 150,  # Insulin
                drugs[4].id: 3000, # IFA
            }

        # Seed initial stock logs (Day 0 - opening stock)
        print("Seeding initial opening stock...")
        for c in centres:
            for d in drugs:
                qty = inventory[c.id][d.id]
                log = StockLog(
                    centre_id=c.id,
                    drug_id=d.id,
                    quantity_change=qty,
                    log_type="received",
                    timestamp=start_date - datetime.timedelta(seconds=1),
                    source="manual",
                    reported_by="system_init"
                )
                db.add(log)
        db.commit()

        print("Generating 90-day time-series history...")
        stock_logs_count = 0
        footfall_logs_count = 0
        bed_status_count = 0
        attendance_count = 0

        # Loop daily
        for day in range(num_days):
            current_day_date = start_date + datetime.timedelta(days=day)
            is_sunday = current_day_date.weekday() == 6
            is_saturday = current_day_date.weekday() == 5

            # Monsoon period is between day 45 and day 75
            is_monsoon = 45 <= day <= 75

            # Every 15 days there is a periodic replenishment delivery
            is_delivery_day = (day > 0 and day % 15 == 0)

            for c in centres:
                # ----------------------------------------------------
                # ANOMALY 1: Badamba PHC (index 4) stops reporting for the last 12 days
                # ----------------------------------------------------
                if c.name == "Badamba PHC" and day >= (num_days - 12):
                    continue  # Skip log generation (simulating offline/non-reporting)

                # Define reporter names
                reporters = ["dr_kumar", "nurse_anita", "pharmacist_anil"]
                reporter = random.choice(reporters)

                # 1. Footfall Logs
                # Baseline footfall
                if c.type == "CHC":
                    base_footfall = random.randint(60, 110)
                else:
                    base_footfall = random.randint(15, 35)

                # Adjust for Tier
                if c.tier_classification == "urban":
                    base_footfall = int(base_footfall * 1.25)
                elif c.tier_classification == "tribal":
                    base_footfall = int(base_footfall * 0.8)

                # Weekend adjustments
                if is_sunday:
                    footfall_count_day = random.randint(2, 6) # minimal emergency visits
                elif is_saturday:
                    footfall_count_day = int(base_footfall * 0.6)
                else:
                    footfall_count_day = base_footfall

                # Monsoon seasonal spike
                if is_monsoon and not is_sunday:
                    footfall_count_day = int(footfall_count_day * random.uniform(1.5, 2.1))

                # Save footfall log
                f_log = FootfallLog(
                    centre_id=c.id,
                    count=footfall_count_day,
                    timestamp=current_day_date + datetime.timedelta(hours=17), # reported in the evening
                    source="manual" if random.random() < 0.85 else "whatsapp",
                    reported_by=reporter
                )
                db.add(f_log)
                footfall_logs_count += 1

                # 2. Staff Attendance
                # CHCs have 24/7 staff, so staff always present. PHCs might close on Sundays.
                roles = ["doctor", "nurse", "pharmacist"]
                for role in roles:
                    if is_sunday:
                        present = False if c.type == "PHC" else True
                    else:
                        # Default 95% attendance
                        present = random.random() < 0.95

                        # ----------------------------------------------------
                        # ANOMALY 3: Niali PHC (index 6) - Under-resourced
                        # Doctor attendance rate is low (30% present on weekdays), Nurse is 65%
                        # ----------------------------------------------------
                        if c.name == "Niali PHC":
                            if role == "doctor":
                                present = random.random() < 0.30
                            elif role == "nurse":
                                present = random.random() < 0.65

                    att = StaffAttendance(
                        centre_id=c.id,
                        staff_role=role,
                        present=present,
                        timestamp=current_day_date + datetime.timedelta(hours=9), # marked in the morning
                        reported_by="system_biometric" if random.random() < 0.7 else "manual"
                    )
                    db.add(att)
                    attendance_count += 1

                # 3. Bed Status
                total_beds = 30 if c.type == "CHC" else 6
                
                # Anomaly 3: Niali PHC has high occupancy (5 or 6 beds filled)
                if c.name == "Niali PHC":
                    occupied_beds = random.choice([5, 6])
                else:
                    # Normal occupancy depends on footfall
                    occ_ratio = min(0.9, (footfall_count_day / 150.0) + random.uniform(0.1, 0.4))
                    if is_sunday:
                        occ_ratio = random.uniform(0.1, 0.3)
                    occupied_beds = min(total_beds, int(total_beds * occ_ratio))
                    if occupied_beds < 0:
                        occupied_beds = 0

                b_status = BedStatus(
                    centre_id=c.id,
                    total_beds=total_beds,
                    occupied_beds=occupied_beds,
                    timestamp=current_day_date + datetime.timedelta(hours=18)
                )
                db.add(b_status)
                bed_status_count += 1

                # 4. Stock Deliveries (replenishment)
                # Deliveries occur every 15 days
                # ANOMALY 3: Niali PHC (Centre 7) deliveries after day 30 are missing/skipped
                skip_delivery = False
                if c.name == "Niali PHC" and day > 30:
                    skip_delivery = True

                if is_delivery_day and not skip_delivery:
                    replenish_amounts = {
                        drugs[0].id: 3000, # Paracetamol
                        drugs[1].id: 1500, # Amoxicillin
                        drugs[2].id: 1000, # ORS
                        drugs[3].id: 150,  # Insulin
                        drugs[4].id: 2500, # IFA
                    }
                    for d in drugs:
                        qty = replenish_amounts[d.id]
                        inventory[c.id][d.id] += qty
                        s_log = StockLog(
                            centre_id=c.id,
                            drug_id=d.id,
                            quantity_change=qty,
                            log_type="received",
                            timestamp=current_day_date + datetime.timedelta(hours=8), # delivered morning
                            source="manual",
                            reported_by="district_supply_chain"
                        )
                        db.add(s_log)
                        stock_logs_count += 1

                # 5. Stock Consumption (daily)
                # Daily consumption is driven by footfall
                for d in drugs:
                    # Normal consumption model based on footfall
                    if d.name == "Paracetamol":
                        # 70% of visitors need Paracetamol, 10 tablets each
                        consumed = int(footfall_count_day * 0.70 * random.randint(6, 12))
                    elif d.name == "Amoxicillin":
                        # 30% of visitors need Amoxicillin, 10 tablets each
                        consumed = int(footfall_count_day * 0.30 * random.randint(8, 12))
                        
                        # ----------------------------------------------------
                        # ANOMALY 2: Tigiria PHC (index 5) - High Consumption
                        # Overwrite to high flat range (300-450 tablets/day) in last 15 days
                        # ----------------------------------------------------
                        if c.name == "Tigiria PHC" and day >= (num_days - 15):
                            consumed = random.randint(300, 450)

                    elif d.name == "ORS":
                        # 40% of visitors get ORS, 2 packets each
                        consumed = int(footfall_count_day * 0.40 * random.randint(2, 3))
                    elif d.name == "Insulin":
                        # 4% of visitors need insulin, 1 vial each
                        consumed = int(footfall_count_day * 0.04 * 1)
                    elif d.name == "IFA (Iron Folic Acid)":
                        # 15% of visitors need IFA, 30 tablets each
                        consumed = int(footfall_count_day * 0.15 * 30)
                    else:
                        consumed = random.randint(5, 15)

                    # Check inventory availability (cannot consume more than we have)
                    current_stock = inventory[c.id][d.id]
                    if consumed > current_stock:
                        consumed = current_stock  # stockout occurs
                    
                    inventory[c.id][d.id] -= consumed

                    # Record consumption log
                    if consumed > 0:
                        # Log source distribution
                        src = "manual"
                        if random.random() < 0.15:
                            src = "whatsapp"
                        elif random.random() < 0.05:
                            src = "voice"
                        
                        s_log = StockLog(
                            centre_id=c.id,
                            drug_id=d.id,
                            quantity_change=-consumed,
                            log_type="consumed",
                            timestamp=current_day_date + datetime.timedelta(hours=19), # logged at night
                            source=src,
                            reported_by=reporter
                        )
                        db.add(s_log)
                        stock_logs_count += 1

            # Commit periodically to keep memory usage low
            if day % 10 == 0:
                db.commit()

        db.commit()
        print(f"Generated:")
        print(f"  - {stock_logs_count} stock log records")
        print(f"  - {footfall_logs_count} footfall log records")
        print(f"  - {bed_status_count} bed status records")
        print(f"  - {attendance_count} attendance records")
        print("Data generation complete and saved.")

    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    create_db_tables()
    seed_data()
