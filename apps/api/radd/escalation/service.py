"""
Escalation service.
Builds context packages, creates escalation events, manages agent queue.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from radd.db.models import (
    AuditLog,
    Conversation,
    Customer,
    EscalationEvent,
    Message,
)
from radd.pipeline.orchestrator import PipelineResult

logger = structlog.get_logger()


async def get_pending_escalations_count(db: AsyncSession, workspace_id: uuid.UUID) -> int:
    """Count pending escalations for a workspace."""
    result = await db.execute(
        select(func.count(EscalationEvent.id)).where(
            EscalationEvent.workspace_id == workspace_id,
            EscalationEvent.status == "pending",
        )
    )
    return result.scalar() or 0

# Escalation reason classifier
REASON_MAP = {
    "low_confidence": lambda r: r.confidence < 0.60,
    "soft_confidence": lambda r: 0.60 <= r.confidence < 0.85,
    "unknown_intent": lambda r: r.intent == "other",
}


async def build_context_package(
    db: AsyncSession,
    conversation: Conversation,
    customer: Customer,
    pipeline_result: PipelineResult,
    recent_message_count: int = 5,
) -> dict:
    """
    Build the context package passed to the agent.
    Contains everything needed to handle the escalation without reading back.
    """
    # Fetch recent messages
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(recent_message_count)
    )
    recent_messages = [
        {
            "sender_type": m.sender_type,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "confidence": m.confidence,
        }
        for m in reversed(msg_result.scalars().all())
    ]

    # Infer KB gaps from what the pipeline couldn't answer
    kb_gaps = []
    if pipeline_result.intent == "other":
        kb_gaps.append("intent_not_recognized")
    if pipeline_result.confidence_breakdown.get("retrieval", 1.0) < 0.50:
        kb_gaps.append("no_relevant_kb_content")
    if pipeline_result.confidence_breakdown.get("verify", 1.0) < 0.60:
        kb_gaps.append("response_not_grounded")

    return {
        "summary": _generate_summary(recent_messages, pipeline_result),
        "recent_messages": recent_messages,
        "customer_info": {
            "id": str(customer.id),
            "display_name": customer.display_name or "عميل",
            "language": customer.language or "ar",
            "channel_type": customer.channel_type,
        },
        "detected_intent": pipeline_result.intent,
        "detected_dialect": pipeline_result.dialect,
        "confidence_scores": pipeline_result.confidence_breakdown,
        "kb_gaps": kb_gaps,
        "source_passages": pipeline_result.source_passages[:3] if pipeline_result.source_passages else [],
    }


def _generate_summary(recent_messages: list[dict], pipeline_result: PipelineResult) -> str:
    """One-line Arabic summary for agent notification."""
    last_customer_msg = next(
        (m["content"] for m in reversed(recent_messages) if m["sender_type"] == "customer"),
        "",
    )
    intent_label = {
        "greeting": "تحية",
        "order_status": "استفسار طلب",
        "shipping": "استفسار شحن",
        "return_policy": "طلب إرجاع",
        "store_hours": "مواعيد",
        "other": "استفسار عام",
    }.get(pipeline_result.intent, "استفسار")

    confidence_pct = int(pipeline_result.confidence * 100)
    return f"{intent_label} — ثقة {confidence_pct}% — \"{last_customer_msg[:60]}\""


async def create_escalation(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    customer: Customer,
    pipeline_result: PipelineResult,
    trigger_message_id: uuid.UUID | None = None,
) -> EscalationEvent:
    """Create an escalation event and update conversation status."""
    context_package = await build_context_package(db, conversation, customer, pipeline_result)

    escalation_type = (
        "soft" if pipeline_result.resolution_type == "escalated_soft" else "hard"
    )

    # Determine reason
    reason = "low_confidence"
    if pipeline_result.intent == "other":
        reason = "unknown_intent"
    elif escalation_type == "soft":
        reason = "soft_confidence"

    event = EscalationEvent(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        trigger_message_id=trigger_message_id,
        escalation_type=escalation_type,
        reason=reason,
        confidence_at_escalation=pipeline_result.confidence,
        context_package=context_package,
        status="pending",
        rag_draft=pipeline_result.rag_draft,
    )
    db.add(event)

    # Update conversation status
    conversation.status = "waiting_agent"

    # Audit
    db.add(AuditLog(
        workspace_id=workspace_id,
        action="escalation.created",
        entity_type="escalation_event",
        entity_id=event.id,
        details={
            "type": escalation_type,
            "reason": reason,
            "confidence": pipeline_result.confidence,
            "intent": pipeline_result.intent,
        },
    ))

    await db.flush()
    logger.info(
        "escalation.created",
        type=escalation_type,
        reason=reason,
        conversation_id=str(conversation.id),
        confidence=pipeline_result.confidence,
    )
    return event


async def accept_escalation(
    db: AsyncSession,
    event: EscalationEvent,
    agent_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> EscalationEvent:
    event.status = "accepted"
    event.assigned_user_id = agent_id
    event.accepted_at = datetime.now(UTC)

    # Also assign conversation
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == event.conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if conv:
        conv.assigned_user_id = agent_id

    db.add(AuditLog(
        workspace_id=workspace_id,
        user_id=agent_id,
        action="escalation.accepted",
        entity_type="escalation_event",
        entity_id=event.id,
    ))
    await db.flush()
    return event


async def resolve_escalation(
    db: AsyncSession,
    event: EscalationEvent,
    agent_id: uuid.UUID,
    workspace_id: uuid.UUID,
    notes: str | None = None,
) -> EscalationEvent:
    event.status = "resolved"
    event.resolved_at = datetime.now(UTC)
    event.resolution_notes = notes

    # Mark conversation resolved
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == event.conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if conv:
        conv.status = "resolved"
        conv.resolved_at = datetime.now(UTC)

    db.add(AuditLog(
        workspace_id=workspace_id,
        user_id=agent_id,
        action="escalation.resolved",
        entity_type="escalation_event",
        entity_id=event.id,
        details={"notes": notes or ""},
    ))
    await db.flush()
    return event
