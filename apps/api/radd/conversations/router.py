from __future__ import annotations

"""
Conversations API — list, detail, agent reply, status updates.
"""
import uuid
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select

from radd.auth.middleware import CurrentUser, require_agent, require_reviewer
from radd.config import settings
from radd.conversations.csat import handle_csat_response, parse_csat_response
from radd.conversations.schemas import (
    AgentReply,
    ConversationDetail,
    ConversationList,
    ConversationSummary,
    CustomerSummary,
    MessageResponse,
)
from radd.db.models import AuditLog, Channel, Conversation, Customer, Message
from radd.db.session import get_db_session
from radd.limiter import limiter
from radd.websocket.manager import ws_manager

logger = structlog.get_logger()
router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get(
    "",
    response_model=ConversationList,
    summary="قائمة المحادثات / List conversations",
    description="Paginated list of workspace conversations with optional status filter. Callable by reviewers. Side effects: none.",
    responses={
        200: {"description": "Conversations returned"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - reviewer role required"},
    },
)
@limiter.limit(settings.default_rate_limit)
async def list_conversations(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    async with get_db_session(current.workspace_id) as db:
        q = select(Conversation).where(Conversation.workspace_id == current.workspace_id)
        if status_filter:
            q = q.where(Conversation.status == status_filter)

        total_result = await db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar_one()

        q = q.order_by(Conversation.last_message_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(q)
        conversations = result.scalars().all()

        # Fetch customers in batch
        customer_ids = list({c.customer_id for c in conversations})
        customer_map: dict[uuid.UUID, Customer] = {}
        if customer_ids:
            cust_result = await db.execute(
                select(Customer).where(Customer.id.in_(customer_ids))
            )
            for cust in cust_result.scalars().all():
                customer_map[cust.id] = cust

    items = []
    for conv in conversations:
        summary = ConversationSummary.model_validate(conv)
        cust = customer_map.get(conv.customer_id)
        if cust:
            summary.customer = CustomerSummary.model_validate(cust)
        items.append(summary)

    return ConversationList(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
    summary="تفاصيل محادثة / Get conversation",
    description="Fetch a single conversation with messages and customer. Callable by reviewers. Side effects: none.",
    responses={
        200: {"description": "Conversation detail returned"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Conversation not found"},
    },
)
@limiter.limit(settings.default_rate_limit)
async def get_conversation(
    request: Request,
    conversation_id: uuid.UUID,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    async with get_db_session(current.workspace_id) as db:
        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.workspace_id == current.workspace_id,
            )
        )
        conv = conv_result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        messages = msg_result.scalars().all()

        cust_result = await db.execute(select(Customer).where(Customer.id == conv.customer_id))
        customer = cust_result.scalar_one_or_none()

    detail = ConversationDetail.model_validate(conv)
    detail.messages = [MessageResponse.model_validate(m) for m in messages]
    if customer:
        detail.customer = CustomerSummary.model_validate(customer)
    return detail


@router.patch(
    "/{conversation_id}",
    response_model=ConversationSummary,
    summary="تحديث محادثة / Update conversation",
    description="Update conversation status or assignment. Callable by agents. Side effects: DB update, resolved_at set if status=resolved.",
    responses={
        200: {"description": "Conversation updated"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - agent role required"},
        404: {"description": "Conversation not found"},
    },
)
@limiter.limit(settings.default_rate_limit)
async def update_conversation(
    request: Request,
    conversation_id: uuid.UUID,
    body: dict,
    current: Annotated[CurrentUser, Depends(require_agent)],
):
    """Update conversation status or assignment."""
    allowed_fields = {"status", "assigned_user_id"}
    updates = {k: v for k, v in body.items() if k in allowed_fields}

    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.workspace_id == current.workspace_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

        for key, value in updates.items():
            setattr(conv, key, value)
        if updates.get("status") == "resolved":
            conv.resolved_at = datetime.now(UTC)

    return ConversationSummary.model_validate(conv)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="رد الوكيل / Agent reply",
    description="Agent sends a message in a conversation. Delivers via WhatsApp and broadcasts to other agents. Callable by agents. Side effects: message stored, WhatsApp delivery, WebSocket broadcast.",
    responses={
        201: {"description": "Message sent successfully"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Conversation not found"},
    },
)
@limiter.limit(settings.default_rate_limit)
async def agent_reply(
    request: Request,
    conversation_id: uuid.UUID,
    body: AgentReply,
    current: Annotated[CurrentUser, Depends(require_agent)],
):
    """
    Agent sends a message in a conversation.
    Delivers via WhatsApp and logs it.
    """
    async with get_db_session(current.workspace_id) as db:
        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.workspace_id == current.workspace_id,
            )
        )
        conv = conv_result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

        # Fetch channel config for WA delivery
        chan_result = await db.execute(select(Channel).where(Channel.id == conv.channel_id))
        channel = chan_result.scalar_one_or_none()

        cust_result = await db.execute(select(Customer).where(Customer.id == conv.customer_id))
        customer = cust_result.scalar_one_or_none()

        # Store agent message
        msg = Message(
            workspace_id=current.workspace_id,
            conversation_id=conversation_id,
            sender_type="agent",
            content=body.content,
        )
        db.add(msg)

        # Update conversation
        conv.last_message_at = datetime.now(UTC)
        conv.message_count = (conv.message_count or 0) + 1
        if body.resolve:
            conv.status = "resolved"
            conv.resolved_at = datetime.now(UTC)
        elif conv.status == "waiting_agent":
            conv.status = "active"

        db.add(AuditLog(
            workspace_id=current.workspace_id,
            user_id=current.user.id,
            action="message.agent_sent",
            entity_type="conversation",
            entity_id=conversation_id,
        ))

        await db.flush()
        msg_id = msg.id

    # Deliver via WhatsApp (outside transaction)
    if channel and customer:
        try:
            from radd.config import settings
            from radd.utils.crypto import get_channel_config_decrypted
            from radd.whatsapp.client import send_text_message
            channel_config = get_channel_config_decrypted(channel)

            # Decode phone: stored as hash — need raw phone for delivery.
            # In production: store encrypted phone. For pilot: pass phone via channel metadata.
            phone = channel_config.get("pilot_phone_override", "")
            if phone:
                await send_text_message(
                    phone_number=phone,
                    message=body.content,
                    phone_number_id=channel_config.get("wa_phone_number_id") or settings.wa_phone_number_id,
                    api_token=channel_config.get("wa_api_token") or settings.wa_api_token,
                )
        except Exception as e:
            logger.error("agent_reply.wa_delivery_failed", error=str(e))

    # Broadcast to other agents watching this conversation
    await ws_manager.broadcast_to_workspace(
        str(current.workspace_id),
        {
            "type": "conversation.message",
            "conversation_id": str(conversation_id),
            "sender_type": "agent",
            "agent_id": str(current.user.id),
            "content_preview": body.content[:100],
        },
        exclude_user=str(current.user.id),
    )

    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(select(Message).where(Message.id == msg_id))
        msg = result.scalar_one()

    return MessageResponse.model_validate(msg)


@router.post(
    "/{conversation_id}/csat",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="تسجيل CSAT / Record CSAT",
    description="Record CSAT rating (1-5) for a conversation. Callable by reviewers. Side effects: CSAT stored.",
    responses={
        204: {"description": "CSAT recorded"},
        400: {"description": "Invalid rating (must be 1-5)"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Conversation not found"},
    },
)
@limiter.limit(settings.default_rate_limit)
async def record_csat(
    request: Request,
    conversation_id: uuid.UUID,
    body: dict,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    """Record CSAT rating (1-5) for a conversation."""
    rating = body.get("rating")
    if rating is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rating required")
    if isinstance(rating, str):
        rating = parse_csat_response(rating)
    if rating is None or not (1 <= rating <= 5):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rating must be 1-5")
    async with get_db_session(current.workspace_id) as db:
        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.workspace_id == current.workspace_id,
            )
        )
        if not conv_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        await handle_csat_response(db, str(conversation_id), rating, str(current.workspace_id))
