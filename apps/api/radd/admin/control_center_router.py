"""RADD AI — Control Center (#14) + KB Management (#15) + Template Editor (#18)
من RADD_Complete_Implementation_v2."""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from radd.auth.middleware import CurrentUser, require_reviewer
from radd.config import settings
from radd.db.models import Conversation, Customer, EscalationEvent, Message, Workspace
from radd.db.session import get_db_session
from radd.limiter import limiter

logger = logging.getLogger("radd.admin.control_center")

# === #14: CONTROL CENTER ===
control_router = APIRouter(prefix="/control-center", tags=["Control Center"])


class AutomationStatus(BaseModel):
    is_active: bool
    paused_at: datetime | None = None
    paused_by: str | None = None


@control_router.get("/decisions")
@limiter.limit(settings.default_rate_limit)
async def get_ai_decisions(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    limit: int = Query(50, ge=1, le=100),
):
    """سجل قرارات الـ AI — last 50 system messages with resolution data."""
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(Message, Conversation, Customer)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .join(Customer, Conversation.customer_id == Customer.id)
            .where(
                Message.workspace_id == current.workspace_id,
                Message.sender_type == "system",
                Conversation.resolution_type.isnot(None),
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        rows = result.all()

    decisions = []
    for msg, conv, cust in rows:
        was_escalated = conv.resolution_type in ("escalated_hard", "escalated_soft")
        decisions.append({
            "message_id": str(msg.id),
            "conversation_id": str(conv.id),
            "customer_phone_hash": cust.channel_identifier_hash or "",
            "intent": conv.intent or "other",
            "confidence_score": float(conv.confidence_score) if conv.confidence_score else 0,
            "resolution_path": conv.resolution_type or "",
            "response_preview": (msg.content or "")[:100],
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
            "was_escalated": was_escalated,
        })
    return {"decisions": decisions}


@control_router.get("/stats")
@limiter.limit(settings.default_rate_limit)
async def get_control_center_stats(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    """Today's counts: total_auto, total_escalated, total_soft, automation_rate."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    async with get_db_session(current.workspace_id) as db:
        # total_auto: conversations resolved automatically today
        auto_result = await db.execute(
            select(func.count()).where(
                Conversation.workspace_id == current.workspace_id,
                Conversation.last_message_at >= today_start,
                Conversation.resolution_type.in_(["auto_template", "auto_rag"]),
            )
        )
        total_auto = auto_result.scalar_one() or 0

        # total_escalated: escalated (hard + soft) today
        esc_result = await db.execute(
            select(func.count()).where(
                Conversation.workspace_id == current.workspace_id,
                Conversation.last_message_at >= today_start,
                Conversation.resolution_type.in_(["escalated_hard", "escalated_soft"]),
            )
        )
        total_escalated = esc_result.scalar_one() or 0

        # total_soft: soft escalations today
        soft_result = await db.execute(
            select(func.count()).where(
                Conversation.workspace_id == current.workspace_id,
                Conversation.last_message_at >= today_start,
                Conversation.resolution_type == "escalated_soft",
            )
        )
        total_soft = soft_result.scalar_one() or 0

    total_resolved = total_auto + total_escalated
    automation_rate = round(total_auto / total_resolved * 100, 1) if total_resolved else 100.0

    return {
        "total_auto": total_auto,
        "total_escalated": total_escalated,
        "total_soft": total_soft,
        "automation_rate": automation_rate,
    }


@control_router.post("/pause-automation")
@limiter.limit(settings.default_rate_limit)
async def pause_automation(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    """إيقاف الأتمتة مؤقتاً."""
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(Workspace).where(Workspace.id == current.workspace_id)
        )
        ws = result.scalar_one_or_none()
        if not ws:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Workspace not found")
        ws_settings = dict(ws.settings or {})
        ws_settings["automation_paused"] = True
        ws.settings = ws_settings
    return {"status": "paused"}


@control_router.post("/resume-automation")
@limiter.limit(settings.default_rate_limit)
async def resume_automation(request: Request, current: Annotated[CurrentUser, Depends(require_reviewer)]):
    """استئناف الأتمتة."""
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(Workspace).where(Workspace.id == current.workspace_id)
        )
        ws = result.scalar_one_or_none()
        if not ws:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Workspace not found")
        ws_settings = dict(ws.settings or {})
        ws_settings["automation_paused"] = False
        ws.settings = ws_settings
    return {"status": "active"}


@control_router.get("/pending-reviews")
@limiter.limit(settings.default_rate_limit)
async def get_pending_reviews(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    limit: int = Query(20, ge=1, le=100),
):
    """الردود المعلقة للمراجعة — escalation_events where status=pending."""
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(EscalationEvent)
            .where(
                EscalationEvent.workspace_id == current.workspace_id,
                EscalationEvent.status == "pending",
            )
            .order_by(EscalationEvent.created_at.asc())
            .limit(limit)
        )
        events = result.scalars().all()

    now = datetime.now(UTC)
    items = []
    for ev in events:
        ctx = ev.context_package or {}
        summary = ctx.get("summary", "")
        minutes_waiting = 0
        if ev.created_at:
            delta = now - ev.created_at.replace(tzinfo=UTC) if ev.created_at.tzinfo is None else ev.created_at
            minutes_waiting = int(delta.total_seconds() / 60)
        items.append({
            "escalation_id": str(ev.id),
            "conversation_id": str(ev.conversation_id),
            "reason": ev.reason or "unknown",
            "confidence_at_escalation": float(ev.confidence_at_escalation) if ev.confidence_at_escalation else None,
            "context_package_summary": summary,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
            "minutes_waiting": minutes_waiting,
        })
    return {"pending_reviews": items}


@control_router.post("/approve-review/{message_id}")
@limiter.limit(settings.default_rate_limit)
async def approve_review(
    request: Request,
    message_id: str,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    modified_text: str | None = None,
):
    return {"approved": message_id, "modified": modified_text is not None}


@control_router.post("/reject-review/{message_id}")
@limiter.limit(settings.default_rate_limit)
async def reject_review(
    request: Request,
    message_id: str,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    return {"rejected": message_id}


# === #15: KB MANAGEMENT ===
kb_manage_router = APIRouter(prefix="/knowledge/manage", tags=["KB Management"])


@kb_manage_router.get("/gaps")
@limiter.limit(settings.default_rate_limit)
async def get_kb_gaps(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    days: int = Query(7, ge=1, le=90),
):
    """فجوات قاعدة المعرفة — أسئلة متكررة بدون إجابة."""
    return {"message": "KB gaps - integrate", "days": days}


@kb_manage_router.post("/suggest-content")
@limiter.limit(settings.default_rate_limit)
async def suggest_content(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    topic: str = "",
):
    """اقتراح محتوى من AI لموضوع معين."""
    return {"message": f"AI suggestion for '{topic}' - integrate with OpenAI"}


@kb_manage_router.get("/health")
@limiter.limit(settings.default_rate_limit)
async def kb_health(request: Request, current: Annotated[CurrentUser, Depends(require_reviewer)]):
    """فحص صحة قاعدة المعرفة."""
    return {"message": "KB health check - integrate"}


# === #18: TEMPLATE EDITOR ===
templates_router = APIRouter(prefix="/templates", tags=["Template Editor"])


class TemplateCreate(BaseModel):
    intent: str
    dialect: str = "gulf"
    content: str
    variables: list[str] = []


@templates_router.get("/")
@limiter.limit(settings.default_rate_limit)
async def list_templates(request: Request, current: Annotated[CurrentUser, Depends(require_reviewer)]):
    """قائمة القوالب — من radd.pipeline.templates."""
    from radd.pipeline.templates import TEMPLATES

    items = []
    for intent, dialects in TEMPLATES.items():
        for dialect, content in dialects.items():
            items.append({"intent": intent, "dialect": dialect, "content": content})
    return {"templates": items}


@templates_router.post("/")
@limiter.limit(settings.default_rate_limit)
async def create_template(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    t: TemplateCreate,
):
    """إنشاء قالب — integrate with DB أو config."""
    return {"created": t.model_dump()}


class TemplatePreview(BaseModel):
    content: str = ""
    variables: dict = {}


@templates_router.post("/preview")
@limiter.limit(settings.default_rate_limit)
async def preview_template(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    body: TemplatePreview,
):
    """معاينة القالب مع متغيرات."""
    result = body.content
    for k, v in body.variables.items():
        result = result.replace(f"{{{k}}}", str(v))
    return {"preview": result}
