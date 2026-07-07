import re
import datetime
from sqlalchemy.orm import Session
from typing import Dict, Any
from app.models import Centre, Drug, StockLog, FootfallLog, BedStatus, StaffAttendance, User, IntakeQueue

# Devanagari numerals to English numerals
DEVANAGARI_TO_ENG = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
}

# Marathi/Hindi drug names and fields mappings to English
TRANSLATION_MAP = {
    # Drugs
    "पॅरासिटामॉल": "Paracetamol",
    "पैरासिटामॉल": "Paracetamol",
    "अमोक्सिसिलिन": "Amoxicillin",
    "ओआरएस": "ORS",
    "इंसुलिन": "Insulin",
    "आयएफए": "IFA",
    # Fields / Reports
    "फूटफॉल": "footfall",
    "मरीज": "footfall",
    "रुग्ण": "footfall",
    "बेड": "beds",
    "खाटा": "beds",
    "उपस्थिती": "attendance",
    "हजेरी": "attendance",
    "स्टॉक": "stock",
    "साठा": "stock",
    "उपस्थित": "present",
    "डॉक्टर": "doctor",
    "चिकित्सक": "doctor"
}

def translate_devanagari_numbers(text: str) -> str:
    for dev, eng in DEVANAGARI_TO_ENG.items():
        text = text.replace(dev, eng)
    return text

def parse_and_translate_report(text: str) -> dict:
    """
    Simulates Bhashini translation (NMT) and text normalization.
    Parses strings like:
      - "पॅरासिटामॉल ५००" -> {"type": "stock", "drug_name": "Paracetamol", "value": 500}
      - "फूटफॉल ३०" -> {"type": "footfall", "value": 30}
      - "बेड ५" -> {"type": "beds", "value": 5}
      - "डॉक्टर उपस्थित" -> {"type": "attendance", "role": "doctor", "present": True}
    """
    # Normalize Devanagari numerals
    text = translate_devanagari_numbers(text)
    
    # Translate vocabulary words
    for dev_word, eng_word in TRANSLATION_MAP.items():
        # Case insensitive/regex substitution
        text = re.sub(dev_word, eng_word, text, flags=re.IGNORECASE)
        
    text_lower = text.lower()
    
    # Regular expression parsing rules
    # 1. Attendance check (e.g. "attendance doctor present" or "attendance उपस्थित")
    if "attendance" in text_lower or "present" in text_lower or "absent" in text_lower:
        role = "doctor" if "doctor" in text_lower or "वैद्यकीय" in text_lower else "nurse"
        present = False if "absent" in text_lower or "अनुपस्थित" in text_lower or "नाही" in text_lower else True
        return {"type": "attendance", "role": role, "present": present}
        
    # 2. Footfall check (e.g. "footfall 30")
    footfall_match = re.search(r'footfall\s*(\d+)', text_lower)
    if footfall_match:
        return {"type": "footfall", "value": int(footfall_match.group(1))}
        
    # 3. Beds check (e.g. "beds 5" or "occupied beds 5")
    beds_match = re.search(r'beds\s*(\d+)', text_lower)
    if beds_match:
        return {"type": "beds", "value": int(beds_match.group(1))}
        
    # 4. Stock check (e.g. "Paracetamol 500" or "stock Paracetamol 500")
    for drug_name in ["Paracetamol", "Amoxicillin", "ORS", "Insulin", "IFA"]:
        pattern = rf'{drug_name.lower()}\s*(\d+)'
        match = re.search(pattern, text_lower)
        if match:
            return {"type": "stock", "drug_name": drug_name, "value": int(match.group(1))}
            
    # Try generic pattern "stock <drug> <qty>"
    stock_pattern = r'stock\s+([a-zA-Z\s]+)\s+(\d+)'
    match = re.search(stock_pattern, text_lower)
    if match:
        raw_drug = match.group(1).strip().capitalize()
        # Find closest match in drug list
        for drug_name in ["Paracetamol", "Amoxicillin", "ORS", "Insulin", "IFA"]:
            if raw_drug in drug_name or drug_name in raw_drug:
                return {"type": "stock", "drug_name": drug_name, "value": int(match.group(2))}

    # Unrecognized format
    raise ValueError(f"Could not parse incoming WhatsApp message format: '{text}'")

def process_intake_message(db: Session, sender: str, body: str, media_url: str = None) -> str:
    """
    Unified WhatsApp report intake handler.
    1. Simulates ASR if audio URL is provided.
    2. Runs Bhashini translation / parsing.
    3. Identifies sender's health centre.
    4. Submits operational metrics to the database.
    """
    raw_text = body or ""
    
    # 1. Simulate Voice ASR if voice note media URL is provided
    if media_url:
        # Check URL or name for simulated transcription
        if "marathi_voice" in media_url:
            raw_text = "मराठी रिपोर्ट: फूटफॉल ३० आणि पॅरासिटामॉल ५००"
        elif "hindi_voice_stock" in media_url:
            raw_text = "पैरासिटामॉल ५००"
        elif "hindi_voice_footfall" in media_url:
            raw_text = "मरीज ३०"
        elif "hindi_voice_beds" in media_url:
            raw_text = "बेड ७"
        elif "hindi_voice_attendance" in media_url:
            raw_text = "डॉक्टर उपस्थित"
        elif "hindi_voice" in media_url:
            raw_text = "बेड ७"
        else:
            raw_text = "फूटफॉल ४५" # default transcription fallback
            
    # 2. Identify Centre via phone number matching
    phone = sender.replace("whatsapp:", "").strip()
    user = db.query(User).filter(User.phone_number == phone).first()
    if not user or not user.centre_id:
        raise ValueError(f"Sender '{phone}' is not registered as a field staff user in the system.")
        
    centre_id = user.centre_id
    now = datetime.datetime.utcnow()
    
    # 3. Parse report
    parsed = parse_and_translate_report(raw_text)
    
    # 4. Ingest parsed metrics
    report_type = parsed["type"]
    if report_type == "footfall":
        log = FootfallLog(centre_id=centre_id, count=parsed["value"], timestamp=now, source="whatsapp", reported_by=user.name)
        db.add(log)
    elif report_type == "beds":
        # Get total beds from centre type (CHC = 30, PHC = 6)
        centre = db.query(Centre).filter_by(id=centre_id).first()
        total_beds = 30 if centre.type == "CHC" else 6
        log = BedStatus(centre_id=centre_id, total_beds=total_beds, occupied_beds=parsed["value"], timestamp=now)
        db.add(log)
    elif report_type == "attendance":
        log = StaffAttendance(centre_id=centre_id, staff_role=parsed["role"], present=parsed["present"], timestamp=now, reported_by=user.name)
        db.add(log)
    elif report_type == "stock":
        drug = db.query(Drug).filter(Drug.name == parsed["drug_name"]).first()
        if not drug:
            raise ValueError(f"Drug '{parsed['drug_name']}' not found in the database.")
        
        # Calculate current stock to determine net quantity change
        from sqlalchemy import func
        curr_stock = db.query(func.sum(StockLog.quantity_change)).filter(
            StockLog.centre_id == centre_id,
            StockLog.drug_id == drug.id
        ).scalar() or 0
        
        change = parsed["value"] - curr_stock
        log = StockLog(centre_id=centre_id, drug_id=drug.id, quantity_change=change, log_type="whatsapp_report", timestamp=now, source="whatsapp", reported_by=user.name)
        db.add(log)
        
    db.commit()
    return f"Report processed: {parsed}"

def enqueue_and_process_message(db: Session, sender: str, body: str, media_url: str = None) -> IntakeQueue:
    """
    Logs message to queue, attempts immediate processing. If processing fails,
    marks status as 'failed' to be retried by the background queue loop.
    """
    queue_item = IntakeQueue(
        sender=sender,
        message_body=body,
        media_url=media_url,
        status="pending",
        retry_count=0
    )
    db.add(queue_item)
    db.commit()
    db.refresh(queue_item)
    
    try:
        # Attempt immediate execution
        res_msg = process_intake_message(db, sender, body, media_url)
        queue_item.status = "processed"
        queue_item.error_message = res_msg
    except Exception as e:
        queue_item.status = "failed"
        queue_item.error_message = str(e)
        
    db.commit()
    db.refresh(queue_item)
    return queue_item

def retry_failed_intake_messages(db: Session) -> Dict[str, Any]:
    """
    Scans the database intake queue, retrying any messages with status='failed'
    up to 3 total retry attempts.
    """
    failed_items = db.query(IntakeQueue).filter(
        IntakeQueue.status == "failed",
        IntakeQueue.retry_count < 3
    ).all()
    
    retried_count = 0
    success_count = 0
    
    for item in failed_items:
        item.retry_count += 1
        try:
            res_msg = process_intake_message(db, item.sender, item.message_body, item.media_url)
            item.status = "processed"
            item.error_message = res_msg
            success_count += 1
        except Exception as e:
            item.error_message = str(e)
            
        db.commit()
        retried_count += 1
        
    return {
        "retried": retried_count,
        "successful": success_count,
        "remaining_failed": len(db.query(IntakeQueue).filter(IntakeQueue.status == "failed", IntakeQueue.retry_count < 3).all())
    }
