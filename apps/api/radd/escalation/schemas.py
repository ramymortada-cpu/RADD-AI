from __future__ import annotations
from typing import Optional
import uuid
from datetime import datetime

from pydantic import BaseModel


class EscalationResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    conversation_id: uuid.UUID
    escalation_type: str
    reason: Optional[str]
    confidence_at_escalation: Optional[float]
    context_package: dict
    assigned_user_id: Optional[uuid.UUID]
    status: str
    rag_draft: Optional[str]
    accepted_at: Optional[datetime]
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class EscalationAccept(BaseModel):
    pass


class EscalationResolve(BaseModel):
    notes: Optional[str] = None
    send_message: Optional[str] = None   # Optional final message to customer


class EscalationQueue(BaseModel):
    items: list[EscalationResponse]
    total: int
