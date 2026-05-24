from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Enquiry, EnquiryEvent
from app.logger import get_logger

logger = get_logger("breakout-assignment.tasks")

SOPS = [
    {
        "name": "Booking Enquiry",
        "keywords": ["book", "appointment", "schedule", "reserve", "slot", "availability"],
        "response": "Thank you for reaching out! We'd be happy to help you book an appointment. Our team will confirm your preferred time slot within 2 hours.",
    },
    {
        "name": "Pricing Question",
        "keywords": ["price", "pricing", "cost", "plan", "fee", "rate", "charge", "how much", "tariff"],
        "response": "Our pricing varies by plan. We offer Starter, Growth, and Enterprise tiers. A team member will share our full pricing guide with you shortly.",
    },
    {
        "name": "Complaint",
        "keywords": ["complaint", "unhappy", "frustrated", "disappointed", "angry", "issue", "problem", "terrible", "worst", "refund"],
        "response": "We're very sorry to hear about your experience. Your concern has been flagged as high priority and a senior team member will reach out to you within 1 hour.",
    },
    {
        "name": "After-Hours Message",
        "keywords": ["after hours", "closed", "weekend", "holiday", "not available", "office hours", "when do you open"],
        "response": "Thank you for your message! Our team is currently unavailable but will respond during business hours (Mon–Fri, 9am–6pm IST).",
    },
    {
        "name": "General Information",
        "keywords": ["information", "info", "details", "tell me", "explain", "how does", "what is", "learn more"],
        "response": "Thanks for your interest! One of our team members will reach out shortly with all the information you need.",
    },
]

def _match_sop(message: str) -> dict | None:
    lowered = message.lower()
    for sop in SOPS:
        if any(keyword in lowered for keyword in sop["keywords"]):
            return sop
    return None

def _add_event(db: Session, enquiry_id: str, event_type: str, detail: str | None = None):
    event = EnquiryEvent(enquiry_id=enquiry_id, event_type=event_type, detail=detail)
    db.add(event)
    db.commit()

def process_enquiry(enquiry_id: str):
    # Steps:
    #   1. Load the enquiry from DB
    #   2. Update status → processing
    #   3. Run SOP matching
    #   4. On match: update record, log success
    #   5. No match: auto-escalate, log escalation

    db: Session = SessionLocal()

    try:
        enquiry = db.get(Enquiry, enquiry_id)
        if not enquiry:
            logger.error(f"Enquiry with ID {enquiry_id} not found.")
            return
        
        enquiry.status = "processing"
        db.commit()
        _add_event(db, enquiry_id, "task_started", "SOP matching started")

        logger.info(
            "SOP matching started",
            extra={
                "enquiry_id": enquiry_id,
                "message_preview": enquiry.message[:100],
                "channel": enquiry.channel,
            },
        )

        matched = _match_sop(enquiry.message)

        if matched:
            enquiry.status = "sop_matched"
            enquiry.matched_sop = matched["name"]
            enquiry.suggested_response = matched["response"]
            db.commit()

            _add_event(db, enquiry_id, "sop_matched", f"Matched SOP: {matched['name']}")

            logger.info("SOP matched",
                extra={
                    "enquiry_id": enquiry_id,
                    "sop": matched["name"],
                    "event": "sop_matched",
                },)
        
        else:
            enquiry.status = "escalated"
            enquiry.escalation_reason = "No SOP matched the inbound message. Flagged for human review."
            db.commit()

            _add_event(db, enquiry_id, "auto_escalated", "No SOP matched. Auto-escalated for human review.")

            logger.warning("No SOP matched — auto-escalated",
                extra={"enquiry_id": enquiry_id, "event": "auto_escalated"},)
        
    except Exception as e:
        logger.error(
            "process_enquiry failed",
            extra={"enquiry_id": enquiry_id, "error": str(e)},
        )
        db.rollback()
    finally:
        db.close()