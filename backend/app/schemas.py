from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

#enquiry
class EnquiryCreate(BaseModel):
    channel: Literal['email', 'call', 'whatsapp'] = Field(None, description="The channel through which the enquiry was made")
    customer_name: str = Field(..., min_length=1, max_length=255, description="Full name of the customer.")
    message: str = Field(..., min_length=1, description="The content of the enquiry.")
    model_config = {
        "json_schema_extra": {
            "example": {
                "channel": "email",
                "customer_name": "Priyanka Ochaney",
                "message": "I have a question about your product."
            }
        }   
    }

class EnquiryCreatedResponse(BaseModel):
    job_id: str = Field(..., description="Unique ID for this enquiry. Use it for all follow-up calls")
    status: str = Field(..., description="Initial status — always 'pending' at creation time.")
    message: str
    model_config = {
        "json_schema_extra": {
            "example": {
                job_id: "123e4567-e89b-12d3-a456-426614174000",
                status: "pending",
                message: "Enquiry received. Processing in background."
            }
        }
    }

#follow-up
class FollowUpRequest(BaseModel):
    delay_minutes: int = Field(..., ge=1, le=10080, description="Delay in minutes before the follow-up is made.")
    message_template: Optional[str] = Field(None, description="Optional custom message template for the follow-up.")
    model_config = {
        "json_schema_extra": {
            "example": {
                "delay_minutes": 30,
                "message_template": "Hello {customer_name}, just following up on your enquiry."
            }
        }
    }

class FollowUpResponse(BaseModel):
    enquiry_id: str
    scheduled_time: datetime
    message: str
    model_config = {
        "json_schema_extra": {
            "example": {
                "enquiry_id": "123e4567-e89b-12d3-a456-426614174000",
                "scheduled_in_minutes": 30,
                "message": "Follow-up scheduled successfully."
            }
        }
    }

#escalation
class EscalationRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Reason for escalation.")
    model_config = {
        "json_schema_extra": {
            "example": {
                "reason": "Customer is very upset and demands to speak to a manager."
            }
        }
    }

class EscalationResponse(BaseModel):
    enquiry_id: str
    escalated_to: str
    message: str
    status: str
    model_config = {
        "json_schema_extra": {
            "example": {
                "enquiry_id": "123e4567-e89b-12d3-a456-426614174000",
                "escalated_to": "manager",
                "message": "Enquiry escalated to manager successfully.",
                "status": "escalated"
            }
        }
    }

#history
class EventOut(BaseModel):
    id: str
    event_type: str
    detail: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}

class HistoryResponse(BaseModel):
    enquiry_id: str
    customer_name: str
    channel: str
    message: str
    status: str
    matched_sop: Optional[str]
    suggested_response: Optional[str]
    escalation_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    timeline: list[EventOut]

    model_config = {"from_attributes": True}

#health
class HealthResponse(BaseModel):
    status: str
    database: str
    environment: str