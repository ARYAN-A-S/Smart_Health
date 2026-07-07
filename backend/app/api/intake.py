from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models import get_db, IntakeQueue
from app.services.intake_service import enqueue_and_process_message, retry_failed_intake_messages

router = APIRouter(prefix="/intake", tags=["Multilingual WhatsApp Intake"])

@router.post("/whatsapp")
def receive_whatsapp_webhook(
    From: str = Form(...),
    Body: Optional[str] = Form(None),
    MediaUrl0: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Twilio WhatsApp Sandbox Webhook endpoint.
    Accepts incoming message/media, translates via Bhashini NMT/ASR,
    queues, and commits the records.
    """
    queue_item = enqueue_and_process_message(db, sender=From, body=Body, media_url=MediaUrl0)
    
    return {
        "id": queue_item.id,
        "status": queue_item.status,
        "retry_count": queue_item.retry_count,
        "error_message": queue_item.error_message
    }

@router.post("/retry")
def trigger_retry_queue(db: Session = Depends(get_db)):
    """
    Triggers retry of failed intake messages.
    """
    stats = retry_failed_intake_messages(db)
    return stats

@router.get("/queue")
def list_intake_queue(db: Session = Depends(get_db)):
    """
    Lists logged reports from the intake queue.
    """
    return db.query(IntakeQueue).order_by(IntakeQueue.timestamp.desc()).all()
