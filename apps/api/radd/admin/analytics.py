from __future__ import annotations

"""
KPI calculations for the admin dashboard.
8 KPI cards:
  1. active_conversations      — conversations with status='active' right now
  2. automation_rate           — % resolved by AI (no agent) in last 24h
  3. avg_response_time_seconds — median system response time, last 24h
  4. escalation_rate           — % conversations escalated, last 24h
  5. csat_score                — placeholder (no CSAT collection yet)
  6. messages_today            — total messages received today
  7. pending_escalations       — escalations with status='pending' right now
  8. hallucination_rate        — % RAG responses with verify_confidence < 0.70
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from radd.db.models import AuditLog, Conversation, EscalationEvent, Message


async def get_kpis(db: AsyncSession, workspace_id: uuid.UUID) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = now - timedelta(hours=24)

    # 1. Active conversations
    active_result = await db.execute(
        select(func.count()).where(
            Conversation.workspace_id == workspace_id,
            Conversation.status == "active",
        )
    )
    active_conversations = active_result.scalar_one()

    # 2. Automation rate (last 24h — resolved without agent)
    auto_result = await db.execute(
        select(func.count()).where(
            Conversation.workspace_id == workspace_id,
            Conversation.last_message_at >= yesterday,
            Conversation.resolution_type.in_(["auto_template", "auto_rag"]),
        )
    )
    auto_count = auto_result.scalar_one()

    total_resolved_result = await db.execute(
        select(func.count()).where(
            Conversation.workspace_id == workspace_id,
            Conversation.last_message_at >= yesterday,
            Conversation.status.in_(["resolved", "active"]),
        )
    )
    total_resolved = total_resolved_result.scalar_one() or 1
    automation_rate = round(auto_count / total_resolved * 100, 1)

    # 3. Avg response time — gap between customer message and system reply (last 24h)
    # Approximation: use message pairs in same conversation
    try:
        rt_result = await db.execute(
            text("""
                SELECT AVG(EXTRACT(EPOCH FROM (s.created_at - c.created_at))) AS avg_seconds
                FROM messages c
                JOIN messages s ON
                    s.conversation_id = c.conversation_id
                    AND s.sender_type = 'system'
                    AND s.created_at > c.created_at
                    AND s.created_at < c.created_at + INTERVAL '5 minutes'
                WHERE c.workspace_id = :wid
                  AND c.sender_type = 'customer'
                  AND c.created_at >= :since
            """),
            {"wid": str(workspace_id), "since": yesterday},
        )
        avg_rt = rt_result.scalar()
        avg_response_time_seconds = round(float(avg_rt), 1) if avg_rt else 0.0
    except Exception:
        avg_response_time_seconds = 0.0

    # 4. Escalation rate (last 24h)
    esc_result = await db.execute(
        select(func.count()).where(
            Conversation.workspace_id == workspace_id,
            Conversation.last_message_at >= yesterday,
            Conversation.resolution_type.in_(["escalated_hard", "escalated_soft"]),
        )
    )
    esc_count = esc_result.scalar_one()
    escalation_rate = round(esc_count / total_resolved * 100, 1)

    # 5. CSAT score — placeholder until CSAT collection is implemented
    csat_score = None

    # 6. Messages today
    msgs_today_result = await db.execute(
        select(func.count()).where(
            Message.workspace_id == workspace_id,
            Message.created_at >= today_start,
            Message.sender_type == "customer",
        )
    )
    messages_today = msgs_today_result.scalar_one()

    # 7. Pending escalations
    pending_result = await db.execute(
        select(func.count()).where(
            EscalationEvent.workspace_id == workspace_id,
            EscalationEvent.status == "pending",
        )
    )
    pending_escalations = pending_result.scalar_one()

    # 8. Hallucination rate proxy — RAG responses with low verify confidence (last 24h)
    try:
        hallu_result = await db.execute(
            text("""
                SELECT
                    COUNT(*) FILTER (
                        WHERE (confidence->>'verify')::float < 0.70
                    ) AS low_verify,
                    COUNT(*) AS total_rag
                FROM messages
                WHERE workspace_id = :wid
                  AND sender_type = 'system'
                  AND confidence IS NOT NULL
                  AND confidence ? 'verify'
                  AND created_at >= :since
            """),
            {"wid": str(workspace_id), "since": yesterday},
        )
        row = hallu_result.fetchone()
        if row and row.total_rag > 0:
            hallucination_rate = round(row.low_verify / row.total_rag * 100, 1)
        else:
            hallucination_rate = 0.0
    except Exception:
        hallucination_rate = 0.0

    return {
        "active_conversations": active_conversations,
        "automation_rate": automation_rate,
        "avg_response_time_seconds": avg_response_time_seconds,
        "escalation_rate": escalation_rate,
        "csat_score": csat_score,
        "messages_today": messages_today,
        "pending_escalations": pending_escalations,
        "hallucination_rate": hallucination_rate,
        "computed_at": now.isoformat(),
    }
