from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime

from app.models import get_db, Flag, Centre
from .schemas import FlagResponse, FlagCreate

router = APIRouter(prefix="/flags", tags=["Flags & Alerts"])

@router.post("/analyze", status_code=status.HTTP_200_OK)
def trigger_adequacy_analysis_endpoint(db: Session = Depends(get_db)):
    """
    Scans all centres for peer-based and IPHS-based adequacy flags (attendance, stockouts, occupancy).
    Generates new flags and updates resolved ones.
    """
    from app.services.flagging import run_adequacy_analysis
    try:
        run_adequacy_analysis(db)
        from app.services.activity import log_activity
        log_activity("analyze_adequacy", {
            "status": "success",
            "message": "Resource adequacy and peer underperformance analysis executed successfully for all centres."
        })
        return {
            "status": "success",
            "message": "Resource adequacy and peer underperformance analysis executed successfully for all centres."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run flagging analysis: {str(e)}"
        )

@router.get("", response_model=List[FlagResponse])
def list_flags(resolved: Optional[bool] = None, db: Session = Depends(get_db)):
    query = db.query(Flag)
    if resolved is not None:
        query = query.filter(Flag.resolved == resolved)
    return query.order_by(Flag.timestamp.desc()).all()

@router.post("", response_model=FlagResponse, status_code=status.HTTP_201_CREATED)
def create_flag(flag_data: FlagCreate, db: Session = Depends(get_db)):
    centre = db.query(Centre).filter(Centre.id == flag_data.centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")
        
    flag_dict = flag_data.model_dump()
    if not flag_dict.get("timestamp"):
        flag_dict["timestamp"] = datetime.datetime.utcnow()
        
    flag = Flag(**flag_dict)
    db.add(flag)
    db.commit()
    db.refresh(flag)
    return flag

@router.patch("/{flag_id}/resolve", response_model=FlagResponse)
def resolve_flag(flag_id: int, db: Session = Depends(get_db)):
    flag = db.query(Flag).filter(Flag.id == flag_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
        
    flag.resolved = True
    db.commit()
    db.refresh(flag)
    from app.services.activity import log_activity
    log_activity("resolve_flag", {
        "flag_id": flag.id,
        "centre_id": flag.centre_id,
        "flag_type": flag.flag_type,
        "triggering_metric": flag.triggering_metric,
        "details": f"Flag {flag.id} ({flag.triggering_metric}) resolved successfully"
    })
    return flag
