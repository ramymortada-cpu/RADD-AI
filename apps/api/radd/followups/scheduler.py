from __future__ import annotations
"""
RADD AI — Smart Follow-ups & Post-Purchase Check-in
Schedules and sends follow-up messages:
1. Abandoned Sales (inquiry but no purchase after 2 hours)
2. Post-Purchase Check-in (delivery confirmation after 3 days)
3. Win-back (VIP inactive for 45+ days)
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
import structlog

logger = structlog.get_logger()


# ──────────────────────────────────────────────
# Follow-up Message Templates
# ──────────────────────────────────────────────

FOLLOWUP_TEMPLATES = {
    "abandoned_sale": {
        "gulf": "هلا مرة ثانية! بعد تواصلك معنا، لا يزال {product_name} متاحاً. تبي تكمل طلبك؟",
        "egyptian": "أهلاً تاني! {product_name} لسه متاح. تكمل طلبك؟",
        "msa": "مرحباً مجدداً! {product_name} لا يزال متاحاً. هل تود استكمال طلبك؟",
    },
    "abandoned_sale_discount": {
        "gulf": "هلا! ما بعد طلبت {product_name}؟ عندنا خصم 10% لك اليوم فقط — كود: RADD10 🎁",
        "egyptian": "أهلاً! لسه مش طلبت {product_name}؟ عندنا خصم 10% ليك النهارده بس — كود: RADD10 🎁",
        "msa": "مرحباً! لم تكمل طلب {product_name} بعد. خصم 10% لك اليوم فقط — الكود: RADD10 🎁",
    },
    "post_purchase": {
        "gulf": "هلا! وصلك طلبك؟ نتمنى تكون راضي. أي ملاحظة نحن هنا 😊",
        "egyptian": "أهلاً! وصلك طلبك؟ نأمل إنك راضي. أي ملاحظة احنا هنا 😊",
        "msa": "مرحباً! هل وصل طلبك؟ نأمل أن تكون راضياً. نحن هنا لأي استفسار 😊",
    },
    "win_back": {
        "gulf": "وحشتنا يا {customer_name}! مدة ما شفناك. عندنا وصلات جديدة تناسبك 🌟",
        "egyptian": "وحشتنا يا {customer_name}! فترة مش شايفينك. عندنا حاجات جديدة هتعجبك 🌟",
        "msa": "نشتاق إليك يا {customer_name}! مضى وقت منذ آخر زيارة. لدينا منتجات جديدة تهمك 🌟",
    },
}


async def schedule_abandoned_sale_followup(
    db_session,
    workspace_id: str,
    conversation_id: str,
    customer_id: str,
    product_name: str = "",
    delay_minutes: int = 120,
) -> dict:
    """Schedule a follow-up for abandoned sales conversation."""
    from radd.db.models import FollowUpQueue
    import uuid

    scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
    template = FOLLOWUP_TEMPLATES["abandoned_sale"]["gulf"].format(
        product_name=product_name or "المنتج"
    )

    followup = FollowUpQueue(
        workspace_id=uuid.UUID(workspace_id),
        conversation_id=uuid.UUID(conversation_id),
        customer_id=uuid.UUID(customer_id),
        scheduled_at=scheduled_at,
        message_template=template,
        status="pending",
    )
    db_session.add(followup)
    await db_session.flush()

    logger.info(
        "followup.scheduled",
        type="abandoned_sale",
        workspace_id=workspace_id,
        scheduled_at=scheduled_at.isoformat(),
    )
    return {"scheduled": True, "followup_id": str(followup.id), "at": scheduled_at.isoformat()}


async def schedule_post_purchase_checkin(
    db_session,
    workspace_id: str,
    conversation_id: str,
    customer_id: str,
    dialect: str = "gulf",
    delay_days: int = 3,
) -> dict:
    """Schedule a post-purchase check-in."""
    from radd.db.models import FollowUpQueue
    import uuid

    scheduled_at = datetime.now(timezone.utc) + timedelta(days=delay_days)
    template = FOLLOWUP_TEMPLATES["post_purchase"][dialect]

    followup = FollowUpQueue(
        workspace_id=uuid.UUID(workspace_id),
        conversation_id=uuid.UUID(conversation_id),
        customer_id=uuid.UUID(customer_id),
        scheduled_at=scheduled_at,
        message_template=template,
        status="pending",
    )
    db_session.add(followup)
    await db_session.flush()

    logger.info("followup.scheduled", type="post_purchase", workspace_id=workspace_id)
    return {"scheduled": True, "followup_id": str(followup.id), "at": scheduled_at.isoformat()}


async def process_due_followups(db_session, workspace_id: str) -> list[dict]:
    """
    Find and process all due follow-up messages.
    Called by the APScheduler worker every 10 minutes.
    Returns list of processed follow-ups.
    """
    from sqlalchemy import select
    from radd.db.models import FollowUpQueue, Customer, Conversation
    import uuid

    now = datetime.now(timezone.utc)

    result = await db_session.execute(
        select(FollowUpQueue, Customer)
        .join(Customer, Customer.id == FollowUpQueue.customer_id)
        .where(
            FollowUpQueue.workspace_id == uuid.UUID(workspace_id),
            FollowUpQueue.status == "pending",
            FollowUpQueue.scheduled_at <= now,
        )
        .limit(50)
    )

    processed = []
    rows = result.all()

    for followup, customer in rows:
        try:
            # Mark as sent
            followup.status = "sent"

            processed.append({
                "followup_id": str(followup.id),
                "customer_id": str(customer.id),
                "message": followup.message_template,
                "type": "followup",
            })

            logger.info(
                "followup.processed",
                followup_id=str(followup.id),
                workspace_id=workspace_id,
            )
        except Exception as e:
            logger.error("followup.process_failed", error=str(e))

    await db_session.flush()
    return processed


async def get_followup_stats(db_session, workspace_id: str) -> dict:
    """Get follow-up statistics for the dashboard."""
    from sqlalchemy import select, func
    from radd.db.models import FollowUpQueue
    import uuid

    result = await db_session.execute(
        select(
            FollowUpQueue.status,
            func.count(FollowUpQueue.id).label("count"),
        )
        .where(FollowUpQueue.workspace_id == uuid.UUID(workspace_id))
        .group_by(FollowUpQueue.status)
    )

    stats = {"pending": 0, "sent": 0, "cancelled": 0, "total": 0}
    for row in result.all():
        stats[row.status] = row.count
        stats["total"] += row.count

    return stats
