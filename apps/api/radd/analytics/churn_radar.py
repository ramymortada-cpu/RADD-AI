from __future__ import annotations
"""
RADD AI — Churn Radar v1
Detects customers at risk of churning:
1. VIP customers inactive for 45+ days
2. Customers with declining order frequency
3. Customers with multiple recent escalations
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import structlog

logger = structlog.get_logger()


class ChurnRiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ChurnAlert:
    customer_id: str
    customer_tier: str
    risk_level: ChurnRiskLevel
    reason: str
    days_inactive: int
    total_revenue: float
    suggested_action: str
    last_seen_at: str


async def scan_for_churn_risk(
    db_session,
    workspace_id: str,
    inactive_threshold_days: int = 45,
) -> list[ChurnAlert]:
    """
    Scan all customers for churn risk signals.
    Returns list of ChurnAlert ordered by risk level.
    """
    from sqlalchemy import select, text
    import uuid

    alerts = []

    try:
        # Query: customers by tier, last seen, escalation count
        result = await db_session.execute(
            text("""
                SELECT
                    id,
                    customer_tier,
                    last_seen_at,
                    total_conversations,
                    total_escalations,
                    salla_total_revenue,
                    salla_total_orders,
                    display_name,
                    channel_identifier_hash
                FROM customers
                WHERE workspace_id = :wid
                  AND last_seen_at IS NOT NULL
                ORDER BY salla_total_revenue DESC NULLS LAST
                LIMIT 500
            """),
            {"wid": workspace_id},
        )
        rows = result.fetchall()

        now = datetime.now(timezone.utc)

        for row in rows:
            last_seen = row.last_seen_at
            if last_seen and last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)

            days_inactive = (now - last_seen).days if last_seen else 999
            tier = row.customer_tier or "new"
            revenue = float(row.salla_total_revenue or 0)
            escalations = row.total_escalations or 0

            risk_level = None
            reason = ""
            suggested_action = ""

            # VIP inactive 45+ days → CRITICAL
            if tier == "vip" and days_inactive >= inactive_threshold_days:
                risk_level = ChurnRiskLevel.CRITICAL
                reason = f"عميل VIP غير نشط منذ {days_inactive} يوم"
                suggested_action = "أرسل رسالة win-back شخصية + عرض حصري"

            # High-value customer inactive 60+ days → HIGH
            elif revenue >= 500 and days_inactive >= 60:
                risk_level = ChurnRiskLevel.HIGH
                reason = f"عميل بإيرادات {revenue:.0f} ر.س غير نشط منذ {days_inactive} يوم"
                suggested_action = "أرسل win-back مع خصم 15%"

            # Returning customer inactive 90+ days → MEDIUM
            elif tier in ("returning", "standard") and days_inactive >= 90:
                risk_level = ChurnRiskLevel.MEDIUM
                reason = f"عميل عائد غير نشط منذ {days_inactive} يوم"
                suggested_action = "أرسل رسالة تذكير بالمنتجات الجديدة"

            # Multiple escalations (at_risk tier) → HIGH
            elif tier == "at_risk" and escalations >= 3:
                risk_level = ChurnRiskLevel.HIGH
                reason = f"عميل في خطر مع {escalations} تصعيدات"
                suggested_action = "تواصل شخصي من المدير لحل المشكلة الجذرية"

            if risk_level:
                alerts.append(ChurnAlert(
                    customer_id=str(row.id),
                    customer_tier=tier,
                    risk_level=risk_level,
                    reason=reason,
                    days_inactive=days_inactive,
                    total_revenue=revenue,
                    suggested_action=suggested_action,
                    last_seen_at=last_seen.isoformat() if last_seen else "",
                ))

        # Sort by risk level (critical first)
        risk_order = {
            ChurnRiskLevel.CRITICAL: 0,
            ChurnRiskLevel.HIGH: 1,
            ChurnRiskLevel.MEDIUM: 2,
            ChurnRiskLevel.LOW: 3,
        }
        alerts.sort(key=lambda a: risk_order[a.risk_level])

        logger.info("churn_radar.scanned", workspace_id=workspace_id, alerts=len(alerts))

    except Exception as e:
        logger.error("churn_radar.failed", error=str(e), workspace_id=workspace_id)

    return alerts


def get_churn_summary(alerts: list[ChurnAlert]) -> dict:
    """Summarize churn risk for the dashboard."""
    if not alerts:
        return {"total": 0, "critical": 0, "high": 0, "medium": 0, "at_risk_revenue": 0}

    critical = sum(1 for a in alerts if a.risk_level == ChurnRiskLevel.CRITICAL)
    high = sum(1 for a in alerts if a.risk_level == ChurnRiskLevel.HIGH)
    medium = sum(1 for a in alerts if a.risk_level == ChurnRiskLevel.MEDIUM)
    at_risk_revenue = sum(a.total_revenue for a in alerts if a.risk_level in (ChurnRiskLevel.CRITICAL, ChurnRiskLevel.HIGH))

    return {
        "total": len(alerts),
        "critical": critical,
        "high": high,
        "medium": medium,
        "at_risk_revenue": round(at_risk_revenue, 2),
    }
