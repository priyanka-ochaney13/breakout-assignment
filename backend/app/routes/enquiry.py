from fastapi import APIRouter, Depends, HTTPException, Path, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Enquiry, EnquiryEvent
from app.schemas import EnquiryCreate, EnquiryCreatedResponse, FollowUpRequest, FollowUpResponse, EscalationRequest, EscalationResponse, EventOut, HistoryResponse
from app.tasks import process_enquiry
from app.logger import get_logger

router = APIRouter(prefix="/enquiry", tags=["enquiry"])
logger = get_logger("app.routes.enquiry")

#post /enquiry
@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EnquiryCreatedResponse,
    summary="Create a new enquiry",
    description="Accepts an inbound customer message and returns a job ID immediately. SOP matching runs asynchronously in the background — poll `/enquiry/{id}/history` to track progress.",
)
def create_enquiry(
    payload: EnquiryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    enquiry = Enquiry(
        channel=payload.channel,
        customer_name=payload.customer_name,
        message=payload.message,
        status="pending",
    )
    db.add(enquiry)
    db.commit()
    db.refresh(enquiry)

    #log creation event
    db.add(EnquiryEvent(
        enquiry_id=enquiry.id,
        event_type="enquiry_created",
        detail=f"Received via {payload.channel} from {payload.customer_name}.",
    ))
    db.commit()

    logger.info(
        "Enquiry created",
        extra={
            "event": "enquiry_created",
            "enquiry_id": enquiry.id,
            "channel": payload.channel,
            "customer": payload.customer_name,
        },
    )

    background_tasks.add_task(process_enquiry, enquiry.id)

    return EnquiryCreatedResponse(
        job_id=enquiry.id,
        status=enquiry.status,
        message="Enquiry received. Processing in background.",
    )

#post /enquiry/{id}/follow-up
@router.post(
    "/{enquiry_id}/follow-up",
    response_model=FollowUpResponse,
    summary="Add a follow-up message to an existing enquiry",
    description="Schedules a follow-up reminder for the given enquiry.Only valid for enquiries that are not yet escalated or closed.",
)
def schedule_follow_up(
    enquiry_id: str = Path(..., description="enquiry job ID returned at creation"),
    payload: FollowUpRequest = ...,
    db: Session = Depends(get_db),
):
    enquiry = db.get(Enquiry, enquiry_id)
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    if enquiry.status in ["escalated", "closed"]:
        raise HTTPException(status_code=409, detail=f"Cannot schedule a follow-up on an enquiry with status '{enquiry.status}'")
    
    template_note = (
        f"Template: '{payload.message_template}'" if payload.message_template else "No template provided"
    )
    detail = f"Follow-up scheduled in {payload.delay_minutes} minute(s).{template_note}"
    
    db.add(EnquiryEvent(
        enquiry_id=enquiry_id,
        event_type="follow_up_scheduled",
        detail=detail,
    ))
    db.commit()

    logger.info(
        "Follow-up scheduled",
        extra={
            "event": "follow_up_scheduled",
            "enquiry_id": enquiry_id,
            "delay_minutes": payload.delay_minutes,
        },
    )

    return FollowUpResponse(
        enquiry_id=enquiry_id,
        scheduled_in_minutes=payload.delay_minutes,
        message="Follow-up scheduled successfully.",
    )

# post /enquiry/{id}/escalate
@router.post(
    "/{enquiry_id}/escalate",
    response_model=EscalationResponse,
    summary="Manually escalate an enquiry for human review",
    description="Manually escalate an enquiry for human review. This is intended for cases where the automated SOP matching did not yield a satisfactory result, or when a support agent determines that human intervention is necessary.",
)
def escalate_enquiry(
    enquiry_id: str = Path(..., description="enquiry job ID"),
    payload: EscalationRequest = ...,
    db: Session = Depends(get_db),
):
    enquiry = db.get(Enquiry, enquiry_id)
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    if enquiry.status == "closed":
        raise HTTPException(status_code=409, detail="Cannot escalate a closed enquiry")

    enquiry.status = "escalated"
    enquiry.escalation_reason = payload.reason
    db.commit()

    db.add(EnquiryEvent(
        enquiry_id=enquiry_id,
        event_type="manually_escalated",
        detail=f"Manually escalated for human review. Reason: {payload.reason}",
    ))
    db.commit()

    logger.warning(
        "Enquiry manually escalated",
        extra={
            "event": "manually_escalated",
            "enquiry_id": enquiry_id,
            "reason": payload.reason,
        },
    )

    return EscalationResponse(
        enquiry_id=enquiry_id,
        status="escalated",
        escalated_to="human_review",
        message="Enquiry escalated for human review.",
    )

# get /enquiry/{id}/history
@router.get(
    '/{enquiry_id}/history',
    response_model=HistoryResponse,
    summary="Get the event history of an enquiry",
    description="Retrieves the chronological event history of an enquiry, including status changes, SOP matching results, follow-up scheduling, and escalations. Useful for tracking the lifecycle of an enquiry and debugging the SOP matching process.",
)
def get_enquiry_history(
    enquiry_id: str = Path(..., description="enquiry job ID"),
    db: Session = Depends(get_db),
):
    enquiry = db.get(Enquiry, enquiry_id)
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    
    return HistoryResponse(
        enquiry_id=enquiry.id,
        customer_name=enquiry.customer_name,
        channel=enquiry.channel,
        message=enquiry.message,
        status=enquiry.status,
        matched_sop=enquiry.matched_sop,
        suggested_response=enquiry.suggested_response,
        escalation_reason=enquiry.escalation_reason,
        created_at=enquiry.created_at,
        updated_at=enquiry.updated_at,
        timeline=[EventOut.model_validate(e) for e in enquiry.events],
    )