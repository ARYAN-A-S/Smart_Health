import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional

from app.models import Centre, Drug, StockLog, FootfallLog, BedStatus, StaffAttendance, Flag

def check_missing_reports(db: Session, centre_id: int, threshold_days: int = 3) -> Optional[Flag]:
    """
    Checks if a centre has failed to submit any reports in the last threshold_days.
    Generates a reliability flag if silent, or resolves it if reporting has resumed.
    """
    now = datetime.datetime.utcnow()
    cutoff = now - datetime.timedelta(days=threshold_days)

    # Find the most recent timestamp across all logs for this centre
    latest_footfall = db.query(func.max(FootfallLog.timestamp)).filter_by(centre_id=centre_id).scalar()
    latest_stock = db.query(func.max(StockLog.timestamp)).filter_by(centre_id=centre_id).scalar()
    latest_bed = db.query(func.max(BedStatus.timestamp)).filter_by(centre_id=centre_id).scalar()
    latest_att = db.query(func.max(StaffAttendance.timestamp)).filter_by(centre_id=centre_id).scalar()

    timestamps = [ts for ts in [latest_footfall, latest_stock, latest_bed, latest_att] if ts is not None]
    
    # If no history exists at all, we don't flag as missing reports (it's a new centre)
    if not timestamps:
        return None

    latest_report_time = max(timestamps)
    is_silent = latest_report_time < cutoff

    # Query for existing active missing_reports flag
    active_flag = db.query(Flag).filter(
        Flag.centre_id == centre_id,
        Flag.flag_type == "reliability",
        Flag.triggering_metric == "missing_reports",
        Flag.resolved == False
    ).first()

    if is_silent:
        days_silent = (now - latest_report_time).days
        if not active_flag:
            flag = Flag(
                centre_id=centre_id,
                flag_type="reliability",
                triggering_metric="missing_reports",
                value=float(days_silent),
                threshold=float(threshold_days),
                timestamp=now,
                resolved=False
            )
            db.add(flag)
            db.commit()
            print(f"Logged missing_reports flag for centre ID {centre_id}. Days silent: {days_silent}")
            return flag
        else:
            # Update value with current silent days
            active_flag.value = float(days_silent)
            db.commit()
    else:
        if active_flag:
            active_flag.resolved = True
            db.commit()
            print(f"Resolved missing_reports flag for centre ID {centre_id}.")
            
    return None

def check_consumption_vs_footfall(db: Session, centre_id: int, ratio_threshold: float = 6.0) -> List[Flag]:
    """
    Checks if a centre has implausible stock consumption relative to its patient footfall.
    Evaluates daily records in the last 15 days.
    """
    now = datetime.datetime.utcnow()
    cutoff_15 = now - datetime.timedelta(days=15)
    
    # Drug-specific thresholds mapping normal vs anomalous
    DRUG_RATIO_THRESHOLDS = {
        "Paracetamol": 12.0,
        "Amoxicillin": 6.0,
        "ORS": 4.0,
        "Insulin": 0.5,
        "IFA (Iron Folic Acid)": 8.0
    }
    
    # Find all drugs
    drugs = db.query(Drug).all()
    created_flags = []

    for drug in drugs:
        # Determine specific threshold for this drug
        drug_threshold = DRUG_RATIO_THRESHOLDS.get(drug.name, ratio_threshold)

        # We query daily consumption and footfall in the last 15 days
        # To do this robustly, we retrieve all consumption logs and group them by date
        # (SQLite allows strftime('%Y-%m-%d', timestamp))
        stock_daily = db.query(
            func.strftime("%Y-%m-%d", StockLog.timestamp).label("date"),
            func.sum(StockLog.quantity_change).label("consumption")
        ).filter(
            StockLog.centre_id == centre_id,
            StockLog.drug_id == drug.id,
            StockLog.quantity_change < 0,
            StockLog.timestamp >= cutoff_15
        ).group_by("date").all()

        stock_map = {item.date: abs(item.consumption) for item in stock_daily}

        footfall_daily = db.query(
            func.strftime("%Y-%m-%d", FootfallLog.timestamp).label("date"),
            func.sum(FootfallLog.count).label("footfall")
        ).filter(
            FootfallLog.centre_id == centre_id,
            FootfallLog.timestamp >= cutoff_15
        ).group_by("date").all()

        footfall_map = {item.date: item.footfall for item in footfall_daily}

        # Check for daily anomalies
        anomalous_days_count = 0
        max_ratio = 0.0
        
        for date, consumption in stock_map.items():
            footfall = footfall_map.get(date, 0)
            if footfall > 0:
                ratio = consumption / float(footfall)
                if ratio > drug_threshold:
                    anomalous_days_count += 1
                    max_ratio = max(max_ratio, ratio)

        # Query existing active flag for this drug consumption anomaly
        active_flag = db.query(Flag).filter(
            Flag.centre_id == centre_id,
            Flag.flag_type == "reliability",
            Flag.triggering_metric == f"consumption_vs_footfall_{drug.name}",
            Flag.resolved == False
        ).first()

        # If we have anomalous days, create a flag
        if anomalous_days_count >= 3:  # flag if anomalous on at least 3 days in the last 15
            if not active_flag:
                flag = Flag(
                    centre_id=centre_id,
                    flag_type="reliability",
                    triggering_metric=f"consumption_vs_footfall_{drug.name}",
                    value=round(max_ratio, 2),
                    threshold=drug_threshold,
                    timestamp=now,
                    resolved=False
                )
                db.add(flag)
                db.commit()
                print(f"Logged consumption mismatch flag for centre ID {centre_id}, drug {drug.name}. Ratio: {max_ratio:.2f}")
                created_flags.append(flag)
            else:
                active_flag.value = round(max_ratio, 2)
                db.commit()
        else:
            if active_flag:
                active_flag.resolved = True
                db.commit()
                print(f"Resolved consumption mismatch flag for centre ID {centre_id}, drug {drug.name}.")
                
    return created_flags

def check_attendance_vs_reporting(db: Session, centre_id: int) -> Optional[Flag]:
    """
    Checks for attendance-reporting inconsistency:
    If staff are marked present, but zero daily reports are submitted (implying false presence reporting).
    Evaluates the last 7 days.
    """
    now = datetime.datetime.utcnow()
    cutoff_7 = now - datetime.timedelta(days=7)
    
    # We query attendance logs where staff is present
    attendance_days = db.query(
        func.strftime("%Y-%m-%d", StaffAttendance.timestamp).label("date")
    ).filter(
        StaffAttendance.centre_id == centre_id,
        StaffAttendance.present == True,
        StaffAttendance.timestamp >= cutoff_7
    ).group_by("date").all()
    
    attendance_dates = {item.date for item in attendance_days}
    if not attendance_dates:
        return None
        
    # Get dates with reporting activity
    footfall_dates = {
        item.date for item in db.query(func.strftime("%Y-%m-%d", FootfallLog.timestamp).label("date"))
        .filter(FootfallLog.centre_id == centre_id, FootfallLog.timestamp >= cutoff_7).all()
    }
    
    stock_dates = {
        item.date for item in db.query(func.strftime("%Y-%m-%d", StockLog.timestamp).label("date"))
        .filter(StockLog.centre_id == centre_id, StockLog.timestamp >= cutoff_7).all()
    }
    
    reported_dates = footfall_dates.union(stock_dates)
    
    # Inconsistent dates: present in attendance but zero logs submitted
    inconsistent_dates = attendance_dates.difference(reported_dates)
    
    active_flag = db.query(Flag).filter(
        Flag.centre_id == centre_id,
        Flag.flag_type == "reliability",
        Flag.triggering_metric == "attendance_vs_reporting",
        Flag.resolved == False
    ).first()
    
    if len(inconsistent_dates) >= 3:  # 3 or more days of false presence reporting
        if not active_flag:
            flag = Flag(
                centre_id=centre_id,
                flag_type="reliability",
                triggering_metric="attendance_vs_reporting",
                value=float(len(inconsistent_dates)),
                threshold=3.0,
                timestamp=now,
                resolved=False
            )
            db.add(flag)
            db.commit()
            print(f"Logged attendance_vs_reporting flag for centre ID {centre_id}. Days mismatched: {len(inconsistent_dates)}")
            return flag
        else:
            active_flag.value = float(len(inconsistent_dates))
            db.commit()
    else:
        if active_flag:
            active_flag.resolved = True
            db.commit()
            print(f"Resolved attendance_vs_reporting flag for centre ID {centre_id}.")
            
    return None

def run_anomaly_analysis_for_centre(db: Session, centre_id: int) -> float:
    """
    Runs all anomaly checks for a centre, generates or resolves flags,
    and returns the calculated Data-Reliability Score (0 to 100).
    """
    # 1. Run checks
    check_missing_reports(db, centre_id, threshold_days=3)
    check_consumption_vs_footfall(db, centre_id, ratio_threshold=6.0)
    check_attendance_vs_reporting(db, centre_id)
    
    # 2. Query active reliability flags
    active_reliability_flags_count = db.query(Flag).filter(
        Flag.centre_id == centre_id,
        Flag.flag_type == "reliability",
        Flag.resolved == False
    ).count()
    
    # 3. Calculate score: deduct 30 points per reliability flag
    score = 100.0 - (active_reliability_flags_count * 30.0)
    return max(0.0, score)
