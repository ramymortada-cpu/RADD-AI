from __future__ import annotations
from typing import Optional
import uuid
from datetime import datetime

from pydantic import BaseModel


class MessageResponse(BaseModel):
    id: uuid.UUID
    sender_type: str
    content: str
    confidence: Optional[dict]
    source_passages: Optional[list]
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerSummary(BaseModel):
    id: uuid.UUID
    display_name: Optional[str]
    language: Optional[str]
    channel_type: str

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    id: uuid.UUID
    status: str
    intent: Optional[str]
    dialect: Optional[str]
    confidence_score: Optional[float]
    resolution_type: Optional[str]
    message_count: int
    first_message_at: Optional[datetime]
    last_message_at: Optional[datetime]
    customer: Optional[CustomerSummary] = None

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationSummary):
    messages: list[MessageResponse] = []
    assigned_user_id: Optional[uuid.UUID]


class ConversationList(BaseModel):
    items: list[ConversationSummary]
    total: int
    page: int
    page_size: int


class AgentReply(BaseModel):
    content: str
    resolve: bool = False   # If True, mark conversation resolved after sending
