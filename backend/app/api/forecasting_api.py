from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.models import get_db
from app.services.forecasting import retrain_models, load_models

router = APIRouter(prefix="/forecasting", tags=["ML Forecasting Engine"])

@router.post("/retrain", status_code=status.HTTP_200_OK)
def trigger_retraining(db: Session = Depends(get_db)):
    """
    Triggers a pooled model retraining task across all historical logs.
    Saves new Gradient Boosting model files to disk.
    """
    try:
        metadata = retrain_models(db)
        return {
            "status": "success",
            "message": "Model retraining completed successfully.",
            "metadata": metadata
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrain models: {str(e)}"
        )

@router.get("/status")
def get_forecasting_status():
    """
    Returns the last training run details and model parameters.
    """
    ff, cons, bed, meta = load_models()
    if meta is None:
        return {
            "status": "inactive",
            "message": "Models have not been trained yet. Trigger /api/forecasting/retrain to initialize."
        }
    return {
        "status": "active",
        "last_trained": meta.get("last_trained"),
        "metrics": {
            "footfall_model_rmse": meta.get("footfall_model_rmse"),
            "consumption_model_rmse": meta.get("consumption_model_rmse"),
            "bed_model_rmse": meta.get("bed_model_rmse")
        }
    }
