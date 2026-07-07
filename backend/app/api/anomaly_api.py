from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.models import get_db, Centre
from app.services.anomaly import run_anomaly_analysis_for_centre

router = APIRouter(prefix="/anomaly", tags=["Data Trust & Anomaly Detection"])

@router.post("/analyze", status_code=status.HTTP_200_OK)
def trigger_anomaly_analysis(db: Session = Depends(get_db)):
    """
    Scans all centres for reporting anomalies, creates/resolves flags in the DB,
    and returns a summary of the current data-reliability scores.
    """
    centres = db.query(Centre).all()
    results = {}
    
    for centre in centres:
        reliability_score = run_anomaly_analysis_for_centre(db, centre.id)
        results[centre.name] = {
            "centre_id": centre.id,
            "data_reliability_score": reliability_score
        }
        
    return {
        "status": "success",
        "message": "Anomaly analysis executed successfully for all centres.",
        "results": results
    }

@router.get("/reliability-scores")
def get_reliability_scores(db: Session = Depends(get_db)):
    """
    Returns a mapping of centre IDs to their current calculated reliability scores.
    """
    centres = db.query(Centre).all()
    scores = {}
    for centre in centres:
        from app.models import Flag
        active_flags_count = db.query(Flag).filter(
            Flag.centre_id == centre.id,
            Flag.flag_type == "reliability",
            Flag.resolved == False
        ).count()
        scores[centre.id] = {
            "name": centre.name,
            "data_reliability_score": max(0.0, 100.0 - (active_flags_count * 30.0)),
            "active_flags_count": active_flags_count
        }
    return scores
