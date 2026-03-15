"""Admin integrations: Salla sync, starter pack, agent assist, Salla actions."""
# TODO: Add Salla order webhook endpoint to receive order.created events.
# When implemented, call: radd.onboarding.salla_sync.handle_salla_order_webhook()
# for revenue attribution (RevenueEventType.ASSISTED_SALE). See: radd/revenue/attribution.py
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy import select as sa_select

from radd.auth.middleware import CurrentUser, require_admin, require_reviewer
from radd.config import settings
from radd.db.models import Conversation, Customer, EscalationEvent, Workspace
from radd.db.models import Message as MsgModel
from radd.db.session import get_db_session
from radd.limiter import limiter

router = APIRouter(tags=["admin-integrations"])


class SallaSyncRequest(BaseModel):
    salla_api_url: str = "https://api.salla.dev/admin/v2"
    salla_token: str


class StarterPackRequest(BaseModel):
    sector: str  # perfumes | fashion | electronics | food


class CancelOrderRequest(BaseModel):
    order_reference: str
    salla_token: str
    reason: str = "change_mind"


class TrackShipmentRequest(BaseModel):
    order_reference: str
    salla_token: str


class CreateReturnRequest(BaseModel):
    order_reference: str
    salla_token: str
    reason: str = "wrong_item"


@router.post("/salla/sync")
@limiter.limit("10/minute")
async def trigger_salla_sync(
    request: Request,
    body: SallaSyncRequest,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Trigger a full Salla product + store policy sync into the KB."""
    from radd.knowledge.service import KBService
    from radd.onboarding.salla_sync import run_full_sync
    async with get_db_session(current.workspace_id) as db:
        kb_service = KBService(db=db, workspace_id=uuid.UUID(str(current.workspace_id)))
        result = await run_full_sync(
            workspace_id=str(current.workspace_id),
            salla_api_url=body.salla_api_url,
            salla_token=body.salla_token,
            db_session=db,
            kb_service=kb_service,
        )
    return {
        "synced": True,
        "products_synced": result.products_synced if hasattr(result, "products_synced") else 0,
        "documents_created": result.documents_created if hasattr(result, "documents_created") else 0,
    }


@router.post("/starter-pack")
@limiter.limit("5/minute")
async def apply_starter_pack(
    request: Request,
    body: StarterPackRequest,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Apply a sector-specific starter pack (pre-built KB + keywords) to this workspace."""
    from radd.knowledge.service import KBService
    from radd.sales.engine import apply_starter_pack
    async with get_db_session(current.workspace_id) as db:
        kb_service = KBService(db=db, workspace_id=uuid.UUID(str(current.workspace_id)))
        result = await apply_starter_pack(
            workspace_id=str(current.workspace_id),
            sector=body.sector,
            kb_service=kb_service,
        )
        ws_result = await db.execute(
            select(Workspace).where(Workspace.id == current.workspace_id)
        )
        ws = ws_result.scalar_one_or_none()
        if ws:
            ws.sector = body.sector
    return result


@router.post("/salla/cancel-order")
@limiter.limit("20/minute")
async def cancel_salla_order(
    request: Request,
    body: CancelOrderRequest,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Cancel a Salla order by reference number."""
    from radd.actions.salla_advanced import cancel_order
    result = await cancel_order(
        order_reference=body.order_reference,
        access_token=body.salla_token,
        reason=body.reason,
    )
    return result


@router.post("/salla/track-shipment")
@limiter.limit("30/minute")
async def track_salla_shipment(
    request: Request,
    body: TrackShipmentRequest,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    """Get real shipment tracking info for a Salla order."""
    from radd.actions.salla_advanced import track_shipment
    result = await track_shipment(
        order_reference=body.order_reference,
        access_token=body.salla_token,
    )
    return result


@router.post("/salla/create-return")
@limiter.limit("20/minute")
async def create_salla_return(
    request: Request,
    body: CreateReturnRequest,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Create a return request for a Salla order."""
    from radd.actions.salla_advanced import create_return_request
    result = await create_return_request(
        order_reference=body.order_reference,
        access_token=body.salla_token,
        reason=body.reason,
    )
    return result


@router.get("/escalations/{escalation_id}/assist")
@limiter.limit(settings.default_rate_limit)
async def get_agent_assist(
    request: Request,
    escalation_id: uuid.UUID,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    """Get AI-generated reply suggestion for an escalated conversation."""
    from radd.intelligence.agent_assist import generate_agent_suggestion

    async with get_db_session(current.workspace_id) as db:
        esc_result = await db.execute(
            sa_select(EscalationEvent).where(
                EscalationEvent.id == escalation_id,
                EscalationEvent.workspace_id == current.workspace_id,
            )
        )
        esc = esc_result.scalar_one_or_none()
        if not esc:
            raise HTTPException(status_code=404, detail="Escalation not found")

        conv_result = await db.execute(
            sa_select(Conversation).where(Conversation.id == esc.conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        cust_result = await db.execute(
            sa_select(Customer).where(Customer.id == conversation.customer_id)
        )
        customer = cust_result.scalar_one_or_none()

        msgs_result = await db.execute(
            sa_select(MsgModel)
            .where(MsgModel.conversation_id == esc.conversation_id)
            .order_by(MsgModel.created_at.desc())
            .limit(8)
        )
        messages = [
            {"sender_type": m.sender_type, "content": m.content}
            for m in reversed(msgs_result.scalars().all())
        ]

    from radd.customers.context_builder import build_customer_context
    customer_ctx = build_customer_context(customer) if customer else ""

    last_msg = messages[-1]["content"] if messages else ""
    suggestion = await generate_agent_suggestion(
        customer_message=last_msg,
        conversation_history=messages,
        customer_context=customer_ctx,
        kb_passages=[],
        dialect=conversation.dialect or "gulf",
        escalation_reason=esc.reason or "",
    )

    return {
        "escalation_id": str(escalation_id),
        "suggestion": suggestion.get("suggestion", ""),
        "recommended_action": suggestion.get("recommended_action", "respond"),
        "confidence": suggestion.get("confidence", 0),
        "context": {
            "customer_tier": customer.customer_tier if customer else "new",
            "total_escalations": customer.total_escalations if customer else 0,
            "dialect": conversation.dialect,
            "stage": getattr(conversation, "stage", "unknown"),
        },
    }
