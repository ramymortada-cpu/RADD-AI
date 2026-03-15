"""
RADD AI — Revenue Attribution Engine
Killer Feature #3: "رَدّ يثبت لك كم كسبك"

يتتبع 3 أنواع إيراد:
1. بيعة مُنسبة: عميل تواصل → رَدّ أجاب → اشترى خلال 24 ساعة
2. إرجاع مُنع: عميل طلب إرجاع → رَدّ عرض بديل → قبل
3. سلة مسترجعة: عميل ترك سلة → رَدّ تابع → اكتمل الطلب
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger("radd.revenue")


class RevenueEventType(Enum):
    ASSISTED_SALE = "assisted_sale"          # عميل سأل → رَدّ أجاب → اشترى
    RETURN_PREVENTED = "return_prevented"     # عميل طلب إرجاع → رَدّ أنقذ البيعة
    CART_RECOVERED = "cart_recovered"         # سلة متروكة → رَدّ تابع → اكتمل
    UPSELL = "upsell"                        # رَدّ اقترح منتج أعلى → العميل اشترى


@dataclass
class RevenueEvent:
    workspace_id: str
    customer_id: str
    conversation_id: str
    event_type: RevenueEventType
    amount: float
    currency: str = "SAR"
    order_id: str | None = None
    details: dict | None = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class RevenueSummary:
    """ملخص الإيرادات — يُعرض في Dashboard و Morning Briefing"""
    period: str  # "today", "this_week", "this_month"
    total_attributed: float
    assisted_sales: float
    assisted_sales_count: int
    returns_prevented: float
    returns_prevented_count: int
    carts_recovered: float
    carts_recovered_count: int
    subscription_cost: float
    roi_multiple: float  # total_attributed / subscription_cost


# ──────────────────────────────────────────────
# Revenue Tracking
# ──────────────────────────────────────────────

async def track_revenue_event(
    db_session,
    event: RevenueEvent,
) -> None:
    """Record a revenue attribution event."""
    from sqlalchemy import text

    await db_session.execute(
        text("""
            INSERT INTO revenue_events
            (workspace_id, customer_id, conversation_id, event_type, amount, currency, order_id, details, created_at)
            VALUES (:wid, :cid, :conv_id, :type, :amount, :currency, :order_id, :details, :created_at)
        """),
        {
            "wid": event.workspace_id,
            "cid": event.customer_id,
            "conv_id": event.conversation_id,
            "type": event.event_type.value,
            "amount": event.amount,
            "currency": event.currency,
            "order_id": event.order_id,
            "details": str(event.details) if event.details else None,
            "created_at": event.created_at,
        },
    )

    # Update customer's total attributed revenue
    await db_session.execute(
        text("""
            UPDATE customers
            SET total_attributed_revenue = COALESCE(total_attributed_revenue, 0) + :amount
            WHERE id = :cid
        """),
        {"amount": event.amount, "cid": event.customer_id},
    )

    await db_session.commit()
    logger.info(f"Revenue event: {event.event_type.value} = {event.amount} {event.currency}")


# ──────────────────────────────────────────────
# Revenue Summary — للـ Dashboard و Morning Briefing
# ──────────────────────────────────────────────

async def get_revenue_summary(
    db_session,
    workspace_id: str,
    period: str = "this_month",
    subscription_cost: float = 499.0,
) -> RevenueSummary:
    """Get revenue attribution summary for dashboard."""
    from sqlalchemy import text

    period_filter = _get_period_filter(period)

    result = await db_session.execute(
        text(f"""
            SELECT
                COALESCE(SUM(amount_sar), 0) as total,
                COALESCE(SUM(amount_sar) FILTER(WHERE event_type = 'assisted_sale'), 0) as sales,
                COUNT(*) FILTER(WHERE event_type = 'assisted_sale') as sales_count,
                COALESCE(SUM(amount_sar) FILTER(WHERE event_type = 'return_prevented'), 0) as returns,
                COUNT(*) FILTER(WHERE event_type = 'return_prevented') as returns_count,
                COALESCE(SUM(amount_sar) FILTER(WHERE event_type = 'cart_recovered'), 0) as carts,
                COUNT(*) FILTER(WHERE event_type = 'cart_recovered') as carts_count
            FROM revenue_events
            WHERE workspace_id = :wid
            AND created_at >= {period_filter}
        """),
        {"wid": workspace_id},
    )

    row = result.fetchone()
    total = float(row.total) if row else 0

    return RevenueSummary(
        period=period,
        total_attributed=total,
        assisted_sales=float(row.sales) if row else 0,
        assisted_sales_count=row.sales_count if row else 0,
        returns_prevented=float(row.returns) if row else 0,
        returns_prevented_count=row.returns_count if row else 0,
        carts_recovered=float(row.carts) if row else 0,
        carts_recovered_count=row.carts_count if row else 0,
        subscription_cost=subscription_cost,
        roi_multiple=round(total / subscription_cost, 1) if subscription_cost > 0 else 0,
    )


def format_revenue_for_briefing(summary: RevenueSummary) -> str:
    """Format revenue summary for Morning Briefing WhatsApp message."""
    if summary.total_attributed == 0:
        return ""

    lines = [f"💰 إيرادات مُنسبة لرَدّ ({summary.period}):"]

    if summary.assisted_sales > 0:
        lines.append(f"  🛒 {summary.assisted_sales_count} بيعة بقيمة ر.س {summary.assisted_sales:,.0f}")

    if summary.returns_prevented > 0:
        lines.append(f"  🛡️ {summary.returns_prevented_count} إرجاع مُنع بقيمة ر.س {summary.returns_prevented:,.0f}")

    if summary.carts_recovered > 0:
        lines.append(f"  🛒 {summary.carts_recovered_count} سلة مسترجعة بقيمة ر.س {summary.carts_recovered:,.0f}")

    lines.append("  ─────────────")
    lines.append(f"  إجمالي: ر.س {summary.total_attributed:,.0f} ({summary.roi_multiple}x العائد على الاشتراك)")

    return "\n".join(lines)


async def record_revenue_event(
    workspace_id: str,
    event_type: str,
    order_id: str,
    order_value: float,
    source: str = "",
    customer_id: str | None = None,
    conversation_id: str | None = None,
) -> None:
    """
    Record a revenue attribution event (e.g. cart_recovered).
    Used by webhooks when customer completes purchase after cart recovery funnel.
    """
    import uuid

    from radd.db.models import RevenueEvent
    from radd.db.session import get_db_session

    try:
        ws_uuid = uuid.UUID(workspace_id)
        cust_uuid = uuid.UUID(customer_id) if customer_id else None
        conv_uuid = uuid.UUID(conversation_id) if conversation_id else None

        async with get_db_session(ws_uuid) as db:
            rev_event = RevenueEvent(
                workspace_id=ws_uuid,
                customer_id=cust_uuid,
                conversation_id=conv_uuid,
                event_type=event_type,
                amount_sar=order_value,
                order_id=order_id,
                metadata_={"source": source} if source else {},
            )
            db.add(rev_event)
            await db.flush()
        logger.info("Revenue event: %s = %s SAR (order=%s)", event_type, order_value, order_id)
    except Exception as e:
        logger.warning("Revenue attribution failed: %s", e)
        raise


def _get_period_filter(period: str) -> str:
    filters = {
        "today": "CURRENT_DATE",
        "yesterday": "CURRENT_DATE - INTERVAL '1 day'",
        "this_week": "DATE_TRUNC('week', CURRENT_DATE)",
        "this_month": "DATE_TRUNC('month', CURRENT_DATE)",
    }
    return filters.get(period, filters["this_month"])
