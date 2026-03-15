"""
COD Shield API — Dashboard data for outbound calls.

Provides summary stats and call list for the COD Shield dashboard.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from radd.auth.middleware import CurrentUser, require_admin
from radd.db.models import OutboundCall
from radd.db.session import get_db_session

logger = logging.getLogger("radd.admin.cod_shield")

router = APIRouter(prefix="/cod-shield", tags=["cod-shield"])


# ─── Response Schemas ───

class CODShieldStats(BaseModel):
    total_calls: int = 0
    confirmed: int = 0
    cancelled: int = 0
    no_answer: int = 0
    pending: int = 0
    save_attempted: int = 0
    confirmation_rate: float = 0.0
    revenue_saved: float = 0.0  # estimated


class CODShieldCallItem(BaseModel):
    id: str
    order_id: str
    customer_name: str | None
    customer_phone: str
    status: str
    call_type: str
    attempt_count: int
    customer_response: str | None
    created_at: str
    called_at: str | None


class CODShieldResponse(BaseModel):
    stats: CODShieldStats
    calls: list[CODShieldCallItem]


# ─── Endpoint ───

@router.get("/summary", response_model=CODShieldResponse)
async def get_cod_shield_summary(
    days: int = 7,
    current: Annotated[CurrentUser, Depends(require_admin)] = None,
):
    """
    Get COD Shield summary stats and recent calls.

    Query params:
    - days: number of days to look back (default: 7)
    """
    workspace_id = current.workspace_id
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with get_db_session(workspace_id) as db:
        stmt = (
            select(OutboundCall)
            .where(OutboundCall.workspace_id == workspace_id, OutboundCall.created_at >= since)
            .order_by(OutboundCall.created_at.desc())
            .limit(100)
        )
        result = await db.execute(stmt)
        calls = result.scalars().all()

        total = len(calls)
        confirmed = sum(1 for c in calls if c.status == "confirmed")
        cancelled = sum(1 for c in calls if c.status == "cancelled")
        no_answer = sum(1 for c in calls if c.status == "no_answer")
        pending = sum(1 for c in calls if c.status in ("pending", "calling"))
        save_attempted = sum(1 for c in calls if c.status == "save_attempted")

        answered = confirmed + cancelled + save_attempted
        confirmation_rate = (confirmed / answered * 100) if answered > 0 else 0.0

        avg_order_value = 500  # placeholder — 500 EGP average
        revenue_saved = confirmed * avg_order_value

        stats = CODShieldStats(
            total_calls=total,
            confirmed=confirmed,
            cancelled=cancelled,
            no_answer=no_answer,
            pending=pending,
            save_attempted=save_attempted,
            confirmation_rate=round(confirmation_rate, 1),
            revenue_saved=revenue_saved,
        )

        call_items = [
            CODShieldCallItem(
                id=str(c.id),
                order_id=c.order_id,
                customer_name=c.customer_name,
                customer_phone=c.customer_phone,
                status=c.status,
                call_type=c.call_type,
                attempt_count=c.attempt_count,
                customer_response=c.customer_response,
                created_at=c.created_at.isoformat() if c.created_at else "",
                called_at=c.called_at.isoformat() if c.called_at else None,
            )
            for c in calls
        ]

    return CODShieldResponse(stats=stats, calls=call_items)
