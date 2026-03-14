"""
RADD AI — Revenue Attribution API
===================================
واجهة API لميزة "إثبات الإيرادات" — الميزة التي ستبيع المنتج.
تربط المحادثات الآلية بالإيرادات المتولدة.

الملف: apps/api/radd/admin/revenue.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

logger = logging.getLogger("radd.admin.revenue")
router = APIRouter(prefix="/revenue", tags=["Revenue Attribution"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RevenueSummary(BaseModel):
    """ملخص الإيرادات المنسوبة لـ RADD."""
    period: str  # "today", "7d", "30d"
    total_revenue_sar: float  # إجمالي الإيرادات المنسوبة
    conversations_that_sold: int  # عدد المحادثات التي أدت لبيع
    total_auto_conversations: int  # إجمالي المحادثات الآلية
    conversion_rate: float  # نسبة التحويل
    avg_order_value_sar: float  # متوسط قيمة الطلب
    top_intents: list[dict]  # أكثر النوايا إنتاجاً للإيرادات
    comparison_vs_previous: float  # نسبة التغيير مقارنة بالفترة السابقة


class RevenueEvent(BaseModel):
    """حدث إيرادات واحد — ربط محادثة بطلب."""
    conversation_id: str
    order_id: str
    order_value_sar: float
    customer_id: str
    intent: str
    resolution_type: str  # auto_template, auto_rag
    timestamp: datetime


class RevenueKPI(BaseModel):
    """بطاقة KPI للإيرادات — تُعرض في الصفحة الرئيسية."""
    radd_revenue_today_sar: float
    radd_revenue_month_sar: float
    conversations_to_sales_rate: float
    money_saved_vs_agents_sar: float  # التوفير مقارنة بتوظيف موظفين


# ---------------------------------------------------------------------------
# Revenue Attribution Logic
# ---------------------------------------------------------------------------

async def calculate_revenue_attribution(
    db_session,
    workspace_id: str,
    period_days: int = 30,
) -> RevenueSummary:
    """
    يحسب الإيرادات المنسوبة لـ RADD.

    المنطق:
    1. نجد كل المحادثات الآلية (auto_template + auto_rag) في الفترة
    2. نربطها بالطلبات عبر customer_id + time window (24 ساعة)
    3. إذا عميل تحدث مع RADD ثم اشترى خلال 24 ساعة → الإيراد يُنسب لـ RADD
    """
    from sqlalchemy import text

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=period_days)
    prev_start = start_date - timedelta(days=period_days)

    # --- Current Period ---
    query = text("""
        WITH auto_conversations AS (
            SELECT DISTINCT c.id, c.customer_id, c.last_message_at, c.intent
            FROM conversations c
            WHERE c.workspace_id = :workspace_id
            AND c.resolution_type IN ('auto_template', 'auto_rag')
            AND c.last_message_at BETWEEN :start_date AND :end_date
        ),
        attributed_orders AS (
            -- هذا يعتمد على وجود جدول orders من تكامل Salla
            -- TODO: ربط مع Salla API أو جدول محلي
            SELECT 1 as placeholder
        )
        SELECT
            COUNT(*) as total_auto_conversations,
            0 as conversations_that_sold,
            0 as total_revenue_sar,
            0 as avg_order_value_sar
        FROM auto_conversations
    """)

    result = await db_session.execute(query, {
        "workspace_id": workspace_id,
        "start_date": start_date,
        "end_date": end_date,
    })
    row = result.fetchone()

    total_auto = row[0] if row else 0
    sold = row[1] if row else 0
    revenue = row[2] if row else 0.0
    avg_value = row[3] if row else 0.0

    # --- نسبة التحويل ---
    conversion_rate = (sold / total_auto * 100) if total_auto > 0 else 0.0

    # --- أكثر النوايا إنتاجاً ---
    intent_query = text("""
        SELECT c.intent, COUNT(*) as count
        FROM conversations c
        WHERE c.workspace_id = :workspace_id
        AND c.resolution_type IN ('auto_template', 'auto_rag')
        AND c.last_message_at BETWEEN :start_date AND :end_date
        GROUP BY c.intent
        ORDER BY count DESC
        LIMIT 5
    """)
    intent_result = await db_session.execute(intent_query, {
        "workspace_id": workspace_id,
        "start_date": start_date,
        "end_date": end_date,
    })
    top_intents = [
        {"intent": row[0], "count": row[1]}
        for row in intent_result.fetchall()
    ]

    period_label = f"{period_days}d"

    return RevenueSummary(
        period=period_label,
        total_revenue_sar=revenue,
        conversations_that_sold=sold,
        total_auto_conversations=total_auto,
        conversion_rate=round(conversion_rate, 1),
        avg_order_value_sar=avg_value,
        top_intents=top_intents,
        comparison_vs_previous=0.0,  # TODO: حساب الفترة السابقة
    )


async def calculate_savings(
    db_session,
    workspace_id: str,
    agent_monthly_cost_sar: float = 4000.0,
    messages_per_agent_per_day: int = 100,
) -> dict:
    """
    يحسب التوفير مقارنة بتوظيف موظفين.

    الحساب:
    - عدد الرسائل الآلية × تكلفة الموظف لكل رسالة = المبلغ الموفر
    """
    from sqlalchemy import text

    # عدد الرسائل الآلية هذا الشهر
    query = text("""
        SELECT COUNT(*)
        FROM messages m
        JOIN conversations c ON m.conversation_id = c.id
        WHERE c.workspace_id = :workspace_id
        AND m.sender_type = 'system'
        AND m.created_at >= date_trunc('month', CURRENT_DATE)
    """)
    result = await db_session.execute(query, {"workspace_id": workspace_id})
    auto_messages = result.scalar() or 0

    # تكلفة الموظف لكل رسالة
    cost_per_message = agent_monthly_cost_sar / (messages_per_agent_per_day * 22)  # 22 يوم عمل

    # المبلغ الموفر
    savings = auto_messages * cost_per_message

    # عدد الموظفين المكافئ
    equivalent_agents = auto_messages / (messages_per_agent_per_day * 22) if auto_messages > 0 else 0

    return {
        "auto_messages_this_month": auto_messages,
        "cost_per_message_sar": round(cost_per_message, 2),
        "total_savings_sar": round(savings, 0),
        "equivalent_agents": round(equivalent_agents, 1),
        "agent_monthly_cost_sar": agent_monthly_cost_sar,
    }


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.get("/summary")
async def get_revenue_summary(
    period: str = "30d",
    # db_session=Depends(get_db_session),
    # workspace_id=Depends(get_current_workspace),
):
    """يرجع ملخص الإيرادات المنسوبة."""
    period_days = {"today": 1, "7d": 7, "30d": 30, "90d": 90}.get(period, 30)
    # TODO: uncomment dependencies when integrating
    # return await calculate_revenue_attribution(db_session, workspace_id, period_days)
    return {"message": "Revenue attribution endpoint - integrate with DB session"}


@router.get("/savings")
async def get_savings():
    """يرجع حساب التوفير مقارنة بالموظفين."""
    # TODO: uncomment dependencies when integrating
    return {"message": "Savings calculation endpoint - integrate with DB session"}


@router.get("/kpi")
async def get_revenue_kpi():
    """بطاقة KPI للصفحة الرئيسية."""
    # TODO: integrate
    return RevenueKPI(
        radd_revenue_today_sar=0.0,
        radd_revenue_month_sar=0.0,
        conversations_to_sales_rate=0.0,
        money_saved_vs_agents_sar=0.0,
    )
