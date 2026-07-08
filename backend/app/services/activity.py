import os
import requests
import json
import threading
import datetime
from app.models.database import SessionLocal
from app.models.models import ActivityLog

def log_activity(action: str, details: dict):
    """
    Logs an action statefully to the local database activity_logs table
    and broadcasts the details via an asynchronous HTTP POST webhook if configured.
    """
    # 1. Save internally to the database
    db = SessionLocal()
    try:
        log_entry = ActivityLog(
            action=action,
            details=json.dumps(details),
            timestamp=datetime.datetime.utcnow()
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        print(f"Error logging activity internally: {e}")
    finally:
        db.close()

    # 2. Dispatch to the configured Webhook URL asynchronously (non-blocking)
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        def post_webhook():
            try:
                payload = {
                    "event": action,
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "data": details
                }
                headers = {"Content-Type": "application/json"}
                requests.post(webhook_url, json=payload, headers=headers, timeout=5)
            except Exception as e:
                # Silently log network dispatch failure
                print(f"Failed to dispatch activity webhook to {webhook_url}: {e}")

        threading.Thread(target=post_webhook, daemon=True).start()
