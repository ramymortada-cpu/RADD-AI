"""
Revenue Dashboard API — Shows the value RADD generates for the merchant.

The most important page in the product: proves ROI.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from radd.auth.middleware import CurrentUser, require_admin
from radd.db.models import RevenueEvent, Workspace
from radd.db.session import get_db_session

logger = logging.getLogger("radd.admin.revenue")

router = APIRouter(prefix="/revenue", tags=["revenue"])


# ─── Response Schemas ───


class RevenueStats(BaseModel):
    total_attributed: float = 0.0
    assisted_sales: float = 0.0
    carts_recovered: float = 0.0
    returns_prevented: float = 0.0
    subscription_cost: float = 499.0
    roi_multiplier: float = 0.0
    events_count: int = 0


class RevenueEventItem(BaseModel):
    id: str
    event_type: str
    order_id: str
    order_value: float
    created_at: str
    source: str = ""


class RevenueDashboardResponse(BaseModel):
    stats: RevenueStats
    recent_events: list[RevenueEventItem]
    period_days: int


# ─── Endpoint ───


@router.get("/dashboard", response_model=RevenueDashboardResponse)
async def get_revenue_dashboard(
    days: int = 30,
    current: Annotated[CurrentUser, Depends(require_admin)] = None,
):
    """
    Get revenue attribution data for the merchant dashboard.

    This is THE page that proves ROI and drives renewals.
    """
    workspace_id = current.workspace_id
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with get_db_session(workspace_id) as db:
        result = await db.execute(
            select(RevenueEvent)
            .where(
                RevenueEvent.workspace_id == workspace_id,
                RevenueEvent.created_at >= since,
            )
            .order_by(RevenueEvent.created_at.desc())
            .limit(50)
        )
        rows = result.scalars().all()

        # Get subscription cost from workspace
        ws_result = await db.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        ws = ws_result.scalar_one_or_none()
        subscription_cost = float(ws.subscription_price_sar) if ws and ws.subscription_price_sar else 499.0

        # Calculate stats
        assisted_sales = sum(r.amount_sar for r in rows if r.event_type == "assisted_sale")
        carts_recovered = sum(r.amount_sar for r in rows if r.event_type == "cart_recovered")
        returns_prevented = sum(r.amount_sar for r in rows if r.event_type == "return_prevented")
        total = assisted_sales + carts_recovered + returns_prevented

        roi = (total / subscription_cost) if subscription_cost > 0 else 0.0

        stats = RevenueStats(
            total_attributed=round(total, 2),
            assisted_sales=round(assisted_sales, 2),
            carts_recovered=round(carts_recovered, 2),
            returns_prevented=round(returns_prevented, 2),
            subscription_cost=subscription_cost,
            roi_multiplier=round(roi, 1),
            events_count=len(rows),
        )

        events = [
            RevenueEventItem(
                id=str(r.id),
                event_type=r.event_type,
                order_id=str(r.order_id) if r.order_id else "",
                order_value=float(r.amount_sar),
                created_at=r.created_at.isoformat() if r.created_at else "",
                source=r.metadata_.get("source", "") if r.metadata_ else "",
            )
            for r in rows
        ]

    return RevenueDashboardResponse(
        stats=stats,
        recent_events=events,
        period_days=days,
    )
