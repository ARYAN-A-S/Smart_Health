from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import datetime

from app.models import get_db, Centre, Drug, StockLog, FootfallLog, BedStatus, StaffAttendance
from .schemas import ReportSubmitRequest

router = APIRouter(prefix="/reports", tags=["Report Submission Ingestion"])

@router.post("/submit", status_code=status.HTTP_201_CREATED)
def submit_report(request: ReportSubmitRequest, db: Session = Depends(get_db)):
    # 1. Validate centre exists
    centre = db.query(Centre).filter(Centre.id == request.centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail=f"Centre with ID {request.centre_id} not found")

    timestamp = datetime.datetime.utcnow()

    # 2. Process based on report type
    report_type = request.report_type.lower()
    
    if report_type == "stock":
        # Required keys: drug_id, quantity_change
        data = request.data
        if "drug_id" not in data or "quantity_change" not in data:
            raise HTTPException(status_code=400, detail="Stock report requires 'drug_id' and 'quantity_change'")
            
        drug_id = data["drug_id"]
        qty_change = data["quantity_change"]
        
        # Check drug exists
        drug = db.query(Drug).filter(Drug.id == drug_id).first()
        if not drug:
            raise HTTPException(status_code=404, detail=f"Drug with ID {drug_id} not found")
            
        log_type = data.get("log_type")
        if not log_type:
            log_type = "consumed" if qty_change < 0 else "received"
            
        log = StockLog(
            centre_id=request.centre_id,
            drug_id=drug_id,
            quantity_change=qty_change,
            log_type=log_type,
            timestamp=timestamp,
            source=request.source,
            reported_by=request.reported_by
        )
        db.add(log)
        db.commit()
        return {"status": "success", "message": "Stock log recorded", "log_id": log.id}
        
    elif report_type == "footfall":
        # Required keys: count
        data = request.data
        if "count" not in data:
            raise HTTPException(status_code=400, detail="Footfall report requires 'count'")
            
        count = data["count"]
        log = FootfallLog(
            centre_id=request.centre_id,
            count=count,
            timestamp=timestamp,
            source=request.source,
            reported_by=request.reported_by
        )
        db.add(log)
        db.commit()
        return {"status": "success", "message": "Footfall log recorded", "log_id": log.id}
        
    elif report_type == "bed":
        # Required keys: total_beds, occupied_beds
        data = request.data
        if "total_beds" not in data or "occupied_beds" not in data:
            raise HTTPException(status_code=400, detail="Bed status report requires 'total_beds' and 'occupied_beds'")
            
        total = data["total_beds"]
        occupied = data["occupied_beds"]
        
        if occupied > total:
            raise HTTPException(status_code=400, detail="Occupied beds cannot exceed total beds")
            
        log = BedStatus(
            centre_id=request.centre_id,
            total_beds=total,
            occupied_beds=occupied,
            timestamp=timestamp
        )
        db.add(log)
        db.commit()
        return {"status": "success", "message": "Bed status recorded", "log_id": log.id}
        
    elif report_type == "attendance":
        # Required keys: staff_role, present
        data = request.data
        if "staff_role" not in data or "present" not in data:
            raise HTTPException(status_code=400, detail="Attendance report requires 'staff_role' and 'present'")
            
        role = data["staff_role"]
        present = bool(data["present"])
        
        log = StaffAttendance(
            centre_id=request.centre_id,
            staff_role=role,
            present=present,
            timestamp=timestamp,
            reported_by=request.reported_by
        )
        db.add(log)
        db.commit()
        return {"status": "success", "message": "Staff attendance recorded", "log_id": log.id}
        
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid report_type '{request.report_type}'. Must be one of: 'stock', 'footfall', 'bed', 'attendance'"
        )
