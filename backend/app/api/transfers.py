from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models import get_db, Transfer, Centre, Drug, StockLog
from .schemas import TransferResponse, TransferCreate

router = APIRouter(prefix="/transfers", tags=["Stock Transfers"])

# Module-level list of showcase recommendations to preserve state during showcase
SHOWCASE_RECS = [
    {
        "id": 9001,
        "from_centre_id": 4,
        "from_centre_name": "Salepur PHC",
        "from_lat": 20.5912,
        "from_lng": 86.1123,
        "to_centre_id": 7,
        "to_centre_name": "Niali PHC",
        "to_lat": 20.1412,
        "to_lng": 86.0451,
        "drug_id": 3,
        "drug_name": "ORS",
        "drug_unit": "packets",
        "quantity": 500,
        "status": "recommended",
        "urgency_score": 10.0,
        "reasoning": "[SHOWCASE] Critical monsoon diarrheal spike forecasted at Niali PHC. Spoke stockout forecast drops to < 24 hours. Moving surplus ORS from Salepur PHC.",
        "distance": 50.5
    },
    {
        "id": 9002,
        "from_centre_id": 8,
        "from_centre_name": "Narasinghpur PHC",
        "from_lat": 20.4514,
        "from_lng": 85.0912,
        "to_centre_id": 5,
        "to_centre_name": "Badamba PHC",
        "to_lat": 20.4212,
        "to_lng": 85.2543,
        "drug_id": 1,
        "drug_name": "Paracetamol",
        "drug_unit": "tablets",
        "quantity": 1200,
        "status": "recommended",
        "urgency_score": 9.5,
        "reasoning": "[SHOWCASE] Extreme viral fever outbreak detected in Badamba PHC via biometric attendance anomalies. Expected stockout in 1.2 days.",
        "distance": 17.4
    },
    {
        "id": 9003,
        "from_centre_id": 1,
        "from_centre_name": "Cuttack Sadar CHC",
        "from_lat": 20.4625,
        "from_lng": 85.8792,
        "to_centre_id": 2,
        "to_centre_name": "Athagarh CHC",
        "to_lat": 20.5312,
        "to_lng": 85.6241,
        "drug_id": 4,
        "drug_name": "Insulin",
        "drug_unit": "vials",
        "quantity": 80,
        "status": "recommended",
        "urgency_score": 9.0,
        "reasoning": "[SHOWCASE] Cold-chain failure warning at Athagarh CHC. Replenishing 80 Insulin vials from Cuttack Sadar CHC central reserve.",
        "distance": 27.8
    },
    {
        "id": 9004,
        "from_centre_id": 9,
        "from_centre_name": "Choudwar PHC",
        "from_lat": 20.5141,
        "from_lng": 85.9123,
        "to_centre_id": 7,
        "to_centre_name": "Niali PHC",
        "to_lat": 20.1412,
        "to_lng": 86.0451,
        "drug_id": 5,
        "drug_name": "IFA (Iron Folic Acid)",
        "drug_unit": "tablets",
        "quantity": 3000,
        "status": "recommended",
        "urgency_score": 8.5,
        "reasoning": "[SHOWCASE] High incidence of pregnancy-related anemia detected in Niali PHC catchments. Transferring 3000 IFA tablets from Choudwar PHC surplus stocks to prevent maternal care disruption.",
        "distance": 32.0
    },
    {
        "id": 9005,
        "from_centre_id": 3,
        "from_centre_name": "Banki CHC",
        "from_lat": 20.3541,
        "from_lng": 85.5324,
        "to_centre_id": 6,
        "to_centre_name": "Tigiria PHC",
        "to_lat": 20.4824,
        "to_lng": 85.5291,
        "drug_id": 2,
        "drug_name": "Amoxicillin",
        "drug_unit": "tablets",
        "quantity": 800,
        "status": "recommended",
        "urgency_score": 9.1,
        "reasoning": "[SHOWCASE] Severe pediatric respiratory infection cluster flagged in Tigiria. Spoke stockout imminent in 48 hours. Dispatching 800 tablets from Banki CHC.",
        "distance": 18.2
    },
    {
        "id": 9006,
        "from_centre_id": 1,
        "from_centre_name": "Cuttack Sadar CHC",
        "from_lat": 20.4625,
        "from_lng": 85.8792,
        "to_centre_id": 10,
        "to_centre_name": "Baranga PHC",
        "to_lat": 20.3912,
        "to_lng": 85.8324,
        "drug_id": 1,
        "drug_name": "Paracetamol",
        "drug_unit": "tablets",
        "quantity": 2500,
        "status": "recommended",
        "urgency_score": 6.8,
        "reasoning": "[SHOWCASE] General outpatient footfall increase of 45% at Baranga PHC. Moving 2500 tablets from Cuttack Sadar CHC central repository.",
        "distance": 12.5
    }
]


@router.get("/recommend")
def get_recommendations(db: Session = Depends(get_db)):
    """
    Triggers the PuLP linear programming redistribution optimizer and returns
    a ranked list of transfer suggestions with explicit reasoning.
    """
    from app.services.optimizer import generate_transfer_plan, calculate_haversine_distance
    from app.services.forecasting import forecast_footfall_next_7_days, forecast_days_to_stockout
    from sqlalchemy import func
    
    transfers = generate_transfer_plan(db)
    
    recommendations = []
    for t in transfers:
        # Get names and stats
        from_c = t.from_centre
        to_c = t.to_centre
        drug = t.drug
        
        # Calculate current stocks for reasoning
        s_stock = db.query(func.sum(StockLog.quantity_change)).filter(
            StockLog.centre_id == t.from_centre_id,
            StockLog.drug_id == t.drug_id
        ).scalar() or 0
        
        d_stock = db.query(func.sum(StockLog.quantity_change)).filter(
            StockLog.centre_id == t.to_centre_id,
            StockLog.drug_id == t.drug_id
        ).scalar() or 0
        
        # Geodesic distance
        dist = calculate_haversine_distance(from_c.lat, from_c.lng, to_c.lat, to_c.lng)
        
        # Destination stockout forecast
        predicted_footfall = forecast_footfall_next_7_days(t.to_centre_id, db)
        d_days, _, _, _ = forecast_days_to_stockout(t.to_centre_id, t.drug_id, d_stock, predicted_footfall, db)
        
        reasoning = (
            f"Transfer {t.quantity} {drug.unit} of {drug.name} from {from_c.name} (Stock: {s_stock}, Safety: {drug.safety_stock_level}) "
            f"to {to_c.name} (Stock: {d_stock}, Safety: {drug.safety_stock_level}). "
            f"Distance: {dist:.1f} km. Recipient stockout forecast: {d_days:.1f} days left."
        )
        
        recommendations.append({
            "id": t.id,
            "from_centre_id": t.from_centre_id,
            "from_centre_name": from_c.name,
            "from_lat": from_c.lat,
            "from_lng": from_c.lng,
            "to_centre_id": t.to_centre_id,
            "to_centre_name": to_c.name,
            "to_lat": to_c.lat,
            "to_lng": to_c.lng,
            "drug_id": t.drug_id,
            "drug_name": drug.name,
            "drug_unit": drug.unit,
            "quantity": t.quantity,
            "status": t.status,
            "urgency_score": t.urgency_score,
            "reasoning": reasoning,
            "distance": round(dist, 2)
        })
        
    # Inject showcase mock recommendations
    recommendations.extend(SHOWCASE_RECS)
    
    # Sort recommendations by urgency_score descending
    recommendations.sort(key=lambda x: x["urgency_score"], reverse=True)
    return recommendations

@router.get("", response_model=List[TransferResponse])
def list_transfers(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Transfer)
    if status:
        query = query.filter(Transfer.status == status)
    return query.all()

@router.post("", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
def create_transfer(transfer_data: TransferCreate, db: Session = Depends(get_db)):
    # Validate from/to centres and drug
    from_c = db.query(Centre).filter(Centre.id == transfer_data.from_centre_id).first()
    to_c = db.query(Centre).filter(Centre.id == transfer_data.to_centre_id).first()
    if not from_c or not to_c:
        raise HTTPException(status_code=404, detail="One or both centres not found")
    if transfer_data.from_centre_id == transfer_data.to_centre_id:
        raise HTTPException(status_code=400, detail="Cannot transfer stock to the same centre")
        
    drug = db.query(Drug).filter(Drug.id == transfer_data.drug_id).first()
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")
        
    transfer = Transfer(**transfer_data.model_dump())
    db.add(transfer)
    db.commit()
    db.refresh(transfer)
    return transfer

@router.patch("/{transfer_id}", response_model=TransferResponse)
def update_transfer_status(transfer_id: int, new_status: str, db: Session = Depends(get_db)):
    from app.services.activity import log_activity
    if transfer_id >= 9000:
        for t in SHOWCASE_RECS:
            if t["id"] == transfer_id:
                t["status"] = new_status
                log_activity("approve_transfer", {
                    "transfer_id": transfer_id,
                    "from_centre_name": t["from_centre_name"],
                    "to_centre_name": t["to_centre_name"],
                    "drug_name": t["drug_name"],
                    "quantity": t["quantity"],
                    "new_status": new_status,
                    "details": f"[SHOWCASE] Transfer ID {transfer_id} updated to {new_status}"
                })
                return {

                    "id": t["id"],
                    "from_centre_id": t["from_centre_id"],
                    "to_centre_id": t["to_centre_id"],
                    "drug_id": t["drug_id"],
                    "quantity": t["quantity"],
                    "status": t["status"],
                    "urgency_score": t["urgency_score"]
                }
        raise HTTPException(status_code=404, detail="Showcase transfer recommendation not found")

    transfer = db.query(Transfer).filter(Transfer.id == transfer_id).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
        
    allowed_statuses = ["suggested", "approved", "completed"]
    if new_status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {allowed_statuses}")
        
    # If the transition is to "completed", we physically deduct inventory from source and add it to destination
    if new_status == "completed" and transfer.status != "completed":
        # Check source inventory
        from sqlalchemy import func
        current_stock = db.query(func.sum(StockLog.quantity_change)).filter(
            StockLog.centre_id == transfer.from_centre_id,
            StockLog.drug_id == transfer.drug_id
        ).scalar() or 0
        
        if current_stock < transfer.quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot complete transfer: source centre only has {current_stock} units, but {transfer.quantity} requested."
            )
            
        import datetime
        timestamp = datetime.datetime.utcnow()
        
        # Log deduction at source
        log_from = StockLog(
            centre_id=transfer.from_centre_id,
            drug_id=transfer.drug_id,
            quantity_change=-transfer.quantity,
            log_type="transferred",
            timestamp=timestamp,
            source="manual",
            reported_by=f"transfer_system_id_{transfer.id}"
        )
        # Log addition at destination
        log_to = StockLog(
            centre_id=transfer.to_centre_id,
            drug_id=transfer.drug_id,
            quantity_change=transfer.quantity,
            log_type="transferred",
            timestamp=timestamp,
            source="manual",
            reported_by=f"transfer_system_id_{transfer.id}"
        )
        db.add(log_from)
        db.add(log_to)
        
    transfer.status = new_status
    db.commit()
    db.refresh(transfer)
    log_activity("approve_transfer", {
        "transfer_id": transfer.id,
        "from_centre_id": transfer.from_centre_id,
        "to_centre_id": transfer.to_centre_id,
        "drug_id": transfer.drug_id,
        "quantity": transfer.quantity,
        "new_status": new_status,
        "details": f"Database Transfer ID {transfer.id} updated to {new_status}"
    })
    return transfer

