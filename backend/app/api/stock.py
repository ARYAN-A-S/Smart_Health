from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import datetime

from app.models import get_db, StockLog, Drug, Centre
from .schemas import StockLogResponse, StockLogCreate, DrugResponse, DrugCreate

router = APIRouter(prefix="/stock", tags=["Stock & Inventory"])

@router.get("/logs", response_model=List[StockLogResponse])
def list_stock_logs(
    centre_id: Optional[int] = None,
    drug_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(StockLog)
    if centre_id:
        query = query.filter(StockLog.centre_id == centre_id)
    if drug_id:
        query = query.filter(StockLog.drug_id == drug_id)
    return query.order_by(StockLog.timestamp.desc()).all()

@router.post("/logs", response_model=StockLogResponse, status_code=status.HTTP_201_CREATED)
def create_stock_log(log_data: StockLogCreate, db: Session = Depends(get_db)):
    # Check if centre and drug exist
    centre = db.query(Centre).filter(Centre.id == log_data.centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")
    drug = db.query(Drug).filter(Drug.id == log_data.drug_id).first()
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")

    # Double check if we are consuming more than available stock
    if log_data.quantity_change < 0:
        current_stock = db.query(func.sum(StockLog.quantity_change)).filter(
            StockLog.centre_id == log_data.centre_id,
            StockLog.drug_id == log_data.drug_id
        ).scalar() or 0
        if abs(log_data.quantity_change) > current_stock:
            raise HTTPException(
                status_code=400, 
                detail=f"Requested consumption quantity ({abs(log_data.quantity_change)}) exceeds current stock ({current_stock})"
            )

    log_dict = log_data.model_dump()
    if not log_dict.get("timestamp"):
        log_dict["timestamp"] = datetime.datetime.utcnow()
    
    log = StockLog(**log_dict)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

@router.get("/drugs", response_model=List[DrugResponse])
def list_drugs(db: Session = Depends(get_db)):
    return db.query(Drug).all()

@router.post("/drugs", response_model=DrugResponse, status_code=status.HTTP_201_CREATED)
def create_drug(drug_data: DrugCreate, db: Session = Depends(get_db)):
    existing = db.query(Drug).filter(Drug.name == drug_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Drug name already exists")
    drug = Drug(**drug_data.model_dump())
    db.add(drug)
    db.commit()
    db.refresh(drug)
    return drug

@router.get("/inventory/{centre_id}")
def get_inventory(centre_id: int, db: Session = Depends(get_db)):
    centre = db.query(Centre).filter(Centre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")
        
    drugs = db.query(Drug).all()
    inventory = []
    for d in drugs:
        current_stock = db.query(func.sum(StockLog.quantity_change)).filter(
            StockLog.centre_id == centre_id,
            StockLog.drug_id == d.id
        ).scalar() or 0
        inventory.append({
            "drug_id": d.id,
            "drug_name": d.name,
            "unit": d.unit,
            "current_stock": current_stock,
            "safety_stock_level": d.safety_stock_level,
            "is_low": current_stock < d.safety_stock_level
        })
    return {
        "centre_id": centre_id,
        "centre_name": centre.name,
        "inventory": inventory
    }
