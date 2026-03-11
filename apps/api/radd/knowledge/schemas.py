from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field


# ─── KB Documents ─────────────────────────────────────────────────────────────

ContentType = Literal["faq", "policy", "product_info", "general"]
DocumentStatus = Literal["draft", "review", "approved", "archived"]


class KBDocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=10)
    content_type: ContentType
    language: str = "ar"


class KBDocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    content_type: Optional[ContentType] = None
    status: Optional[DocumentStatus] = None


class KBDocumentResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    content_type: str
    status: str
    language: str
    version: int
    uploaded_by_user_id: uuid.UUID
    approved_by_user_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KBDocumentDetail(KBDocumentResponse):
    content: str
    chunk_count: int = 0


class KBDocumentList(BaseModel):
    items: list[KBDocumentResponse]
    total: int
    page: int
    page_size: int


# ─── KB Chunks ────────────────────────────────────────────────────────────────

class KBChunkResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    content: str
    chunk_index: int
    token_count: Optional[int]
    is_active: bool

    model_config = {"from_attributes": True}


# ─── Response Templates ───────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    intent_id: str = Field(..., max_length=50)
    dialect: Literal["gulf", "egyptian", "msa"]
    content: str = Field(..., min_length=5)
    parameters: list[dict] = []


class TemplateUpdate(BaseModel):
    content: Optional[str] = None
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    intent_id: str
    dialect: str
    content: str
    parameters: list
    is_active: bool
    usage_count: int

    model_config = {"from_attributes": True}
