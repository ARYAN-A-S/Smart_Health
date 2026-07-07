from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime

from app.models import get_db, FootfallLog, Centre
from .schemas import FootfallLogResponse, FootfallLogCreate

router = APIRouter(prefix="/footfall", tags=["Footfall"])

@router.get("", response_model=List[FootfallLogResponse])
def list_footfall_logs(centre_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(FootfallLog)
    if centre_id:
        query = query.filter(FootfallLog.centre_id == centre_id)
    return query.order_by(FootfallLog.timestamp.desc()).all()

@router.post("", response_model=FootfallLogResponse, status_code=status.HTTP_201_CREATED)
def create_footfall_log(log_data: FootfallLogCreate, db: Session = Depends(get_db)):
    centre = db.query(Centre).filter(Centre.id == log_data.centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")
        
    log_dict = log_data.model_dump()
    if not log_dict.get("timestamp"):
        log_dict["timestamp"] = datetime.datetime.utcnow()
        
    log = FootfallLog(**log_dict)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
