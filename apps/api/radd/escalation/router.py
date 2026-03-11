from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from radd.limiter import limiter
from radd.config import settings
from sqlalchemy import func, select

from radd.auth.middleware import CurrentUser, require_agent
from radd.db.models import EscalationEvent
from radd.db.session import get_db_session
from radd.escalation import service
from radd.escalation.schemas import (
    EscalationQueue,
    EscalationResolve,
    EscalationResponse,
)

router = APIRouter(prefix="/escalations", tags=["escalations"])


@router.get("", response_model=EscalationQueue)
@limiter.limit(settings.default_rate_limit)
async def list_escalations(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_agent)],
    status_filter: str = Query("pending", alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Agent queue — pending escalations sorted by age (oldest first)."""
    async with get_db_session(current.workspace_id) as db:
        q = (
            select(EscalationEvent)
            .where(
                EscalationEvent.workspace_id == current.workspace_id,
                EscalationEvent.status == status_filter,
            )
            .order_by(EscalationEvent.created_at.asc())
        )
        total_result = await db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar_one()

        items_result = await db.execute(
            q.offset((page - 1) * page_size).limit(page_size)
        )
        items = items_result.scalars().all()

    return EscalationQueue(
        items=[EscalationResponse.model_validate(e) for e in items],
        total=total,
    )


@router.get("/{escalation_id}", response_model=EscalationResponse)
@limiter.limit(settings.default_rate_limit)
async def get_escalation(
    request: Request,
    escalation_id: uuid.UUID,
    current: Annotated[CurrentUser, Depends(require_agent)],
):
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(EscalationEvent).where(
                EscalationEvent.id == escalation_id,
                EscalationEvent.workspace_id == current.workspace_id,
            )
        )
        event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation not found")
    return EscalationResponse.model_validate(event)


@router.post("/{escalation_id}/accept", response_model=EscalationResponse)
@limiter.limit(settings.default_rate_limit)
async def accept_escalation(
    request: Request,
    escalation_id: uuid.UUID,
    current: Annotated[CurrentUser, Depends(require_agent)],
):
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(EscalationEvent).where(
                EscalationEvent.id == escalation_id,
                EscalationEvent.workspace_id == current.workspace_id,
            )
        )
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation not found")
        if event.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Escalation is already '{event.status}'",
            )
        event = await service.accept_escalation(db, event, current.user.id, current.workspace_id)

    # Notify via WebSocket
    from radd.websocket.manager import ws_manager
    await ws_manager.broadcast_to_workspace(
        str(current.workspace_id),
        {
            "type": "escalation.accepted",
            "escalation_id": str(escalation_id),
            "agent_id": str(current.user.id),
        },
    )
    return EscalationResponse.model_validate(event)


@router.post("/{escalation_id}/resolve", response_model=EscalationResponse)
@limiter.limit(settings.default_rate_limit)
async def resolve_escalation(
    request: Request,
    escalation_id: uuid.UUID,
    body: EscalationResolve,
    current: Annotated[CurrentUser, Depends(require_agent)],
):
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(EscalationEvent).where(
                EscalationEvent.id == escalation_id,
                EscalationEvent.workspace_id == current.workspace_id,
            )
        )
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation not found")
        if event.status not in ("pending", "accepted"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resolve escalation with status '{event.status}'",
            )
        event = await service.resolve_escalation(
            db, event, current.user.id, current.workspace_id, notes=body.notes
        )

    # Optionally send final message to customer
    if body.send_message:
        from radd.db.session import get_db_session as _session
        from sqlalchemy import select as _select
        from radd.db.models import Conversation as Conv, Channel
        async with _session(current.workspace_id) as db2:
            conv_res = await db2.execute(_select(Conv).where(Conv.id == event.conversation_id))
            conv = conv_res.scalar_one_or_none()
            if conv:
                chan_res = await db2.execute(_select(Channel).where(Channel.id == conv.channel_id))
                channel = chan_res.scalar_one_or_none()
                if channel:
                    from radd.db.models import Customer as Cust
                    cust_res = await db2.execute(_select(Cust).where(Cust.id == conv.customer_id))
                    customer = cust_res.scalar_one_or_none()
                    if customer:
                        import hashlib
                        # Decode phone (stored as hash — can't reverse; use channel config)
                        # In production: store encrypted phone. For MVP: skip auto-send.
                        pass

    return EscalationResponse.model_validate(event)
