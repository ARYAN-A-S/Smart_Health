from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime

from app.models import get_db, BedStatus, Centre
from .schemas import BedStatusResponse, BedStatusCreate

router = APIRouter(prefix="/beds", tags=["Beds Occupancy"])

@router.get("", response_model=List[BedStatusResponse])
def list_bed_status_logs(centre_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(BedStatus)
    if centre_id:
        query = query.filter(BedStatus.centre_id == centre_id)
    return query.order_by(BedStatus.timestamp.desc()).all()

@router.post("", response_model=BedStatusResponse, status_code=status.HTTP_201_CREATED)
def create_bed_status(log_data: BedStatusCreate, db: Session = Depends(get_db)):
    centre = db.query(Centre).filter(Centre.id == log_data.centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")
        
    if log_data.occupied_beds > log_data.total_beds:
        raise HTTPException(status_code=400, detail="Occupied beds cannot exceed total beds")
        
    log_dict = log_data.model_dump()
    if not log_dict.get("timestamp"):
        log_dict["timestamp"] = datetime.datetime.utcnow()
        
    log = BedStatus(**log_dict)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

@router.get("/current")
def get_current_bed_status(db: Session = Depends(get_db)):
    """
    Retrieves the latest occupied beds count and total beds capacity for all centres.
    """
    centres = db.query(Centre).all()
    results = []
    
    for c in centres:
        latest = db.query(BedStatus).filter(BedStatus.centre_id == c.id)\
            .order_by(BedStatus.timestamp.desc()).first()
        
        total = 30 if c.type == "CHC" else 6
        occupied = 0
        if latest:
            total = latest.total_beds
            occupied = latest.occupied_beds
            
        results.append({
            "centre_id": c.id,
            "centre_name": c.name,
            "total_beds": total,
            "occupied_beds": occupied
        })
        
    return results

# In-memory database of external referral hospitals for showcase
HOSPITALS_DATA = [
    {
        "id": 1,
        "name": "SCB Medical College & Hospital",
        "distance": 1.2,
        "contact": "+91-671-2414088",
        "type": "Government Tertiary Care & Referral Hospital",
        "beds": {
            "icu": {"total": 85, "occupied": 73},
            "ventilator": {"total": 30, "occupied": 26},
            "oxygen": {"total": 200, "occupied": 155},
            "general": {"total": 600, "occupied": 458}
        }
    },
    {
        "id": 2,
        "name": "AIIMS Bhubaneswar",
        "distance": 28.0,
        "contact": "+91-674-2476789",
        "type": "National Referral & Research Institute",
        "beds": {
            "icu": {"total": 120, "occupied": 92},
            "ventilator": {"total": 50, "occupied": 38},
            "oxygen": {"total": 300, "occupied": 212},
            "general": {"total": 800, "occupied": 490}
        }
    },
    {
        "id": 3,
        "name": "City Hospital Cuttack",
        "distance": 3.5,
        "contact": "+91-671-2301144",
        "type": "District General Hospital",
        "beds": {
            "icu": {"total": 20, "occupied": 17},
            "ventilator": {"total": 8, "occupied": 7},
            "oxygen": {"total": 60, "occupied": 46},
            "general": {"total": 150, "occupied": 105}
        }
    },
    {
        "id": 4,
        "name": "Capital Hospital Bhubaneswar",
        "distance": 26.0,
        "contact": "+91-674-2391983",
        "type": "State Capital General Hospital",
        "beds": {
            "icu": {"total": 50, "occupied": 35},
            "ventilator": {"total": 20, "occupied": 14},
            "oxygen": {"total": 180, "occupied": 128},
            "general": {"total": 400, "occupied": 220}
        }
    }
]

@router.get("/hospitals")
def get_referral_hospitals():
    """
    Returns the list of external referral hospitals with detailed bed occupancy.
    """
    return HOSPITALS_DATA

@router.post("/hospitals/{hospital_id}/refer")
def refer_patient(hospital_id: int, bed_type: str):
    """
    Simulates referring a patient to a referral hospital, reserving a bed.
    """
    for h in HOSPITALS_DATA:
        if h["id"] == hospital_id:
            if bed_type not in h["beds"]:
                raise HTTPException(status_code=400, detail="Invalid bed type")
            
            bed_info = h["beds"][bed_type]
            if bed_info["occupied"] >= bed_info["total"]:
                raise HTTPException(status_code=400, detail=f"No available {bed_type} beds in this hospital")
            
            bed_info["occupied"] += 1
            return {
                "status": "success",
                "message": f"Patient referred successfully to {h['name']}. One {bed_type} bed reserved.",
                "hospital": h
            }
            
    raise HTTPException(status_code=404, detail="Hospital not found")

