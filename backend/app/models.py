import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _uuid() -> str:
    return str(uuid.uuid4())

class Enquiry(Base):
    __tablename__ = "enquiries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    #inbound data
    channel: Mapped[str] = mapped_column(String(20))
    customer_name: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    
    #processed by background task
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    #pending, processing, closed, escalated
    matched_sop: Mapped[str | None] = mapped_column(String(100), nullable=True)
    suggested_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now) 
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    events: Mapped[list["EnquiryEvent"]] = relationship("EnquiryEvent", back_populates="enquiry", order_by="EnquiryEvent.created_at")

class EnquiryEvent(Base):
    __tablename__ = "enquiry_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)

    enquiry_id: Mapped[str] = mapped_column(String, ForeignKey("enquiries.id"), nullable=False)

    event_type: Mapped[str] = mapped_column(String(50))

    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now) 

    enquiry: Mapped["Enquiry"] = relationship("Enquiry", back_populates="events")