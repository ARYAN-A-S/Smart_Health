from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime

from app.models import get_db, StaffAttendance, Centre
from .schemas import StaffAttendanceResponse, StaffAttendanceCreate

router = APIRouter(prefix="/attendance", tags=["Staff Attendance"])

@router.get("", response_model=List[StaffAttendanceResponse])
def list_attendance_logs(
    centre_id: Optional[int] = None, 
    role: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    query = db.query(StaffAttendance)
    if centre_id:
        query = query.filter(StaffAttendance.centre_id == centre_id)
    if role:
        query = query.filter(StaffAttendance.staff_role == role)
    return query.order_by(StaffAttendance.timestamp.desc()).all()

@router.post("", response_model=StaffAttendanceResponse, status_code=status.HTTP_201_CREATED)
def create_attendance_log(log_data: StaffAttendanceCreate, db: Session = Depends(get_db)):
    centre = db.query(Centre).filter(Centre.id == log_data.centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")
        
    log_dict = log_data.model_dump()
    if not log_dict.get("timestamp"):
        log_dict["timestamp"] = datetime.datetime.utcnow()
        
    log = StaffAttendance(**log_dict)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
