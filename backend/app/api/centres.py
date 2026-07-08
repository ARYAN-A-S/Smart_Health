from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import datetime

from app.models import get_db, Centre, Drug, StockLog, Flag
from .schemas import CentreResponse, CentreCreate, CentreRiskStateResponse, StockForecastItem, FlagResponse

router = APIRouter(prefix="/centres", tags=["Centres"])

@router.get("", response_model=List[CentreResponse])
def list_centres(db: Session = Depends(get_db)):
    return db.query(Centre).all()

@router.get("/{centre_id}", response_model=CentreResponse)
def get_centre(centre_id: int, db: Session = Depends(get_db)):
    centre = db.query(Centre).filter(Centre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")
    return centre

@router.post("", response_model=CentreResponse, status_code=status.HTTP_201_CREATED)
def create_centre(centre_data: CentreCreate, db: Session = Depends(get_db)):
    existing = db.query(Centre).filter(Centre.name == centre_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Centre name already exists")
    centre = Centre(**centre_data.model_dump())
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return centre

@router.get("/{centre_id}/risk-state", response_model=CentreRiskStateResponse)
def get_centre_risk_state(centre_id: int, db: Session = Depends(get_db)):
    centre = db.query(Centre).filter(Centre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")

    # Get active (unresolved) flags
    active_flags = db.query(Flag).filter(
        Flag.centre_id == centre_id,
        Flag.resolved == False
    ).all()

    # Import forecasting services (M5)
    from app.services.forecasting import (
        forecast_footfall_next_7_days,
        forecast_beds_next_7_days,
        forecast_days_to_stockout
    )

    # 1. Forecast footfall for next 7 days
    predicted_footfall = forecast_footfall_next_7_days(centre_id, db)

    # 2. Forecast bed occupancy for next 7 days
    predicted_beds = forecast_beds_next_7_days(centre_id, predicted_footfall, db)

    # 3. Forecast stockout per drug
    drugs = db.query(Drug).all()
    stock_forecasts = []

    for drug in drugs:
        current_stock = db.query(func.sum(StockLog.quantity_change)).filter(
            StockLog.centre_id == centre_id,
            StockLog.drug_id == drug.id
        ).scalar() or 0

        days_to_stockout, lower_days, upper_days, reasoning = forecast_days_to_stockout(
            centre_id=centre_id,
            drug_id=drug.id,
            current_stock=current_stock,
            predicted_footfall_7=predicted_footfall,
            db=db
        )

        stock_forecasts.append(StockForecastItem(
            drug_id=drug.id,
            drug_name=drug.name,
            current_stock=current_stock,
            safety_stock_level=drug.safety_stock_level,
            predicted_days_to_stockout=days_to_stockout,
            uncertainty_lower=lower_days,
            uncertainty_upper=upper_days,
            reasoning=reasoning
        ))

    # Retrieve reliability reasons from active reliability flags (read-only, prevents DB locks)
    reliability_reasons = []
    reliability_flags = db.query(Flag).filter(
        Flag.centre_id == centre_id,
        Flag.flag_type == "reliability",
        Flag.resolved == False
    ).all()
    reliability_score = max(0.0, 100.0 - (len(reliability_flags) * 30.0))

    
    for flag in reliability_flags:
        if flag.triggering_metric == "missing_reports":
            reliability_reasons.append(f"Silent Centre: Stopped reporting for {flag.value:.0f} days (threshold: {flag.threshold:.0f} days).")
        elif flag.triggering_metric.startswith("consumption_vs_footfall"):
            drug_name = flag.triggering_metric.replace("consumption_vs_footfall_", "")
            reliability_reasons.append(f"Consumption Mismatch: {drug_name} consumption ratio reached {flag.value:.1f}/patient (threshold: {flag.threshold:.1f}).")
        elif flag.triggering_metric == "attendance_vs_reporting":
            reliability_reasons.append(f"Attendance Inconsistency: Biometric presence claims but zero reporting on {flag.value:.0f} days.")
        else:
            reliability_reasons.append(f"Reliability Flag ({flag.triggering_metric}): value {flag.value} (threshold {flag.threshold}).")
            
    if not reliability_reasons:
        reliability_reasons.append("No active data reliability flags. Reporting history appears consistent.")
    
    # Integrate real Resource Adequacy score calculation (M7)
    from app.services.flagging import get_resource_adequacy_score
    adequacy_score, adequacy_reasons = get_resource_adequacy_score(db, centre_id)

    # Already predicted above using ML models

    return CentreRiskStateResponse(
        centre_id=centre_id,
        centre_name=centre.name,
        data_reliability_score=reliability_score,
        resource_adequacy_score=adequacy_score,
        reliability_reasons=reliability_reasons,
        adequacy_reasons=adequacy_reasons,
        stock_forecasts=stock_forecasts,
        predicted_footfall_next_7_days=predicted_footfall,
        predicted_bed_demand_next_7_days=predicted_beds,
        active_flags=[FlagResponse.model_validate(f) for f in active_flags]
    )
