import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Tuple, Dict, Any

from app.models import Centre, Drug, StockLog, FootfallLog, BedStatus, StaffAttendance, Flag

def calculate_centre_adequacy_metrics(db: Session, centre_id: int) -> Dict[str, Any]:
    """
    Computes performance metrics for a centre:
    1. Doctor attendance rate (% present on weekdays)
    2. Average bed occupancy ratio
    3. Stockout frequency (% of days with 0 units) per drug over 90 days
    """
    # 1. Doctor Attendance
    # Query attendance logs for doctors
    doctor_logs = db.query(StaffAttendance).filter(
        StaffAttendance.centre_id == centre_id,
        StaffAttendance.staff_role == "doctor"
    ).all()
    
    weekday_doctor_total = 0
    weekday_doctor_present = 0
    
    for log in doctor_logs:
        # Exclude Sundays for PHCs since they are closed
        is_phc = db.query(Centre.type).filter_by(id=centre_id).scalar() == "PHC"
        if is_phc and log.timestamp.weekday() == 6:
            continue
        weekday_doctor_total += 1
        if log.present:
            weekday_doctor_present += 1
            
    doc_rate = (weekday_doctor_present / weekday_doctor_total * 100.0) if weekday_doctor_total > 0 else 100.0

    # 2. Bed Occupancy Ratio
    bed_logs = db.query(BedStatus).filter_by(centre_id=centre_id).all()
    occupied_sum = 0
    total_sum = 0
    for log in bed_logs:
        occupied_sum += log.occupied_beds
        total_sum += log.total_beds
        
    avg_occupancy = (occupied_sum / total_sum) if total_sum > 0 else 0.0

    # 3. Stockout Frequency per Drug
    drugs = db.query(Drug).all()
    num_days = 90
    start_date = datetime.datetime.utcnow() - datetime.timedelta(days=num_days)
    
    stockout_frequencies = {}
    
    for drug in drugs:
        # Reconstruct inventory day-by-day
        # Get all stock logs for this centre and drug
        logs = db.query(StockLog).filter(
            StockLog.centre_id == centre_id,
            StockLog.drug_id == drug.id
        ).order_by(StockLog.timestamp.asc()).all()
        
        # Track cumulative stock over time
        stock_timeline = []
        running_stock = 0
        log_idx = 0
        
        for d in range(num_days):
            day_date = start_date + datetime.timedelta(days=d)
            # Add all transactions occurred on or before this day
            while log_idx < len(logs) and logs[log_idx].timestamp.date() <= day_date.date():
                running_stock += logs[log_idx].quantity_change
                log_idx += 1
            
            # Record if stocked out (<= 0) on this day
            stock_timeline.append(1 if running_stock <= 0 else 0)
            
        stockout_days = sum(stock_timeline)
        stockout_frequencies[drug.name] = (stockout_days / num_days * 100.0)

    return {
        "doctor_attendance_rate": doc_rate,
        "avg_bed_occupancy_ratio": avg_occupancy,
        "stockout_frequencies": stockout_frequencies
    }

def run_adequacy_analysis(db: Session):
    """
    Scans all centres, evaluates adequacy metrics against thresholds,
    and creates or resolves database flags.
    """
    centres = db.query(Centre).all()
    drugs = db.query(Drug).all()
    now = datetime.datetime.utcnow()

    for centre in centres:
        # Compute metrics
        metrics = calculate_centre_adequacy_metrics(db, centre.id)
        doc_rate = metrics["doctor_attendance_rate"]
        bed_ratio = metrics["avg_bed_occupancy_ratio"]
        stockout_freqs = metrics["stockout_frequencies"]

        # ----------------------------------------------------
        # 1. Doctor Absenteeism Flag (< 60%)
        # ----------------------------------------------------
        active_doc_flag = db.query(Flag).filter(
            Flag.centre_id == centre.id,
            Flag.flag_type == "adequacy",
            Flag.triggering_metric == "doctor_absenteeism",
            Flag.resolved == False
        ).first()

        if doc_rate < 60.0:
            if not active_doc_flag:
                flag = Flag(
                    centre_id=centre.id,
                    flag_type="adequacy",
                    triggering_metric="doctor_absenteeism",
                    value=round(doc_rate, 1),
                    threshold=60.0,
                    timestamp=now,
                    resolved=False
                )
                db.add(flag)
                print(f"Logged adequacy flag doctor_absenteeism for {centre.name}: {doc_rate:.1f}%")
            else:
                active_doc_flag.value = round(doc_rate, 1)
        else:
            if active_doc_flag:
                active_doc_flag.resolved = True
                print(f"Resolved adequacy flag doctor_absenteeism for {centre.name}.")

        # ----------------------------------------------------
        # 2. Bed Overcrowding Flag (> 85%)
        # ----------------------------------------------------
        active_bed_flag = db.query(Flag).filter(
            Flag.centre_id == centre.id,
            Flag.flag_type == "adequacy",
            Flag.triggering_metric == "bed_overcrowding",
            Flag.resolved == False
        ).first()

        bed_percentage = bed_ratio * 100.0
        if bed_percentage > 85.0:
            if not active_bed_flag:
                flag = Flag(
                    centre_id=centre.id,
                    flag_type="adequacy",
                    triggering_metric="bed_overcrowding",
                    value=round(bed_percentage, 1),
                    threshold=85.0,
                    timestamp=now,
                    resolved=False
                )
                db.add(flag)
                print(f"Logged adequacy flag bed_overcrowding for {centre.name}: {bed_percentage:.1f}%")
            else:
                active_bed_flag.value = round(bed_percentage, 1)
        else:
            if active_bed_flag:
                active_bed_flag.resolved = True
                print(f"Resolved adequacy flag bed_overcrowding for {centre.name}.")

        # ----------------------------------------------------
        # 3. Drug Stockouts Flags (> 15% frequency)
        # ----------------------------------------------------
        for drug in drugs:
            freq = stockout_freqs.get(drug.name, 0.0)
            active_stock_flag = db.query(Flag).filter(
                Flag.centre_id == centre.id,
                Flag.flag_type == "adequacy",
                Flag.triggering_metric == f"stockout_{drug.name}",
                Flag.resolved == False
            ).first()

            if freq > 10.0:
                if not active_stock_flag:
                    flag = Flag(
                        centre_id=centre.id,
                        flag_type="adequacy",
                        triggering_metric=f"stockout_{drug.name}",
                        value=round(freq, 1),
                        threshold=10.0,
                        timestamp=now,
                        resolved=False
                    )
                    db.add(flag)
                    print(f"Logged adequacy flag stockout_{drug.name} for {centre.name}: {freq:.1f}%")
                else:
                    active_stock_flag.value = round(freq, 1)
            else:
                if active_stock_flag:
                    active_stock_flag.resolved = True
                    print(f"Resolved adequacy flag stockout_{drug.name} for {centre.name}.")

    db.commit()

def get_resource_adequacy_score(db: Session, centre_id: int) -> Tuple[float, List[str]]:
    """
    Computes the resource adequacy score for a centre and compiles detailed reasons.
    Each active adequacy flag deducts 25 points.
    """
    # Force run checks to update flags dynamically
    run_adequacy_analysis(db)

    active_adequacy_flags = db.query(Flag).filter(
        Flag.centre_id == centre_id,
        Flag.flag_type == "adequacy",
        Flag.resolved == False
    ).all()

    # Calculate score
    score = 100.0 - (len(active_adequacy_flags) * 25.0)
    score = max(0.0, score)

    reasons = []
    for flag in active_adequacy_flags:
        if flag.triggering_metric == "doctor_absenteeism":
            reasons.append(f"Doctor Absenteeism: weekday doctor presence rate of {flag.value:.1f}% fell below target of {flag.threshold:.0f}%.")
        elif flag.triggering_metric == "bed_overcrowding":
            reasons.append(f"Bed Overcrowding: average occupancy level of {flag.value:.1f}% exceeded safety capacity threshold of {flag.threshold:.0f}%.")
        elif flag.triggering_metric.startswith("stockout_"):
            drug_name = flag.triggering_metric.replace("stockout_", "")
            reasons.append(f"Chronic Stockout: {drug_name} was depleted on {flag.value:.1f}% of days over the last 90 days (limit: {flag.threshold:.0f}%).")
        else:
            reasons.append(f"Resource adequacy issue: {flag.triggering_metric} triggered value {flag.value} (threshold {flag.threshold}).")

    if not reasons:
        reasons.append("Stock and staffing levels meet baseline requirements.")

    return score, reasons
