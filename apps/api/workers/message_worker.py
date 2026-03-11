"""
Message worker — Redis Streams consumer.
Reads from messages:{workspace_id} streams.
Runs the pipeline, stores results, sends WhatsApp response.
"""
import asyncio
import hashlib
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog
from sqlalchemy import func, select, update

sys.path.insert(0, str(Path(__file__).parent.parent))

from radd.config import settings
from radd.db.models import Channel, Conversation, Customer, Message, AuditLog
from radd.db.session import get_db_session
from radd.deps import get_redis
from radd.pipeline.normalizer import normalize
from radd.pipeline.orchestrator import run_pipeline_async
from radd.whatsapp.client import send_text_message

logger = structlog.get_logger()

CONSUMER_GROUP = "radd-workers"
CONSUMER_NAME = "worker-1"
BLOCK_MS = 5000
SESSION_WINDOW_SECONDS = 1800  # 30 minutes


async def get_or_create_customer(db, workspace_id: uuid.UUID, phone: str) -> Customer:
    phone_hash = hashlib.sha256(phone.encode()).hexdigest()
    result = await db.execute(
        select(Customer).where(
            Customer.workspace_id == workspace_id,
            Customer.channel_identifier_hash == phone_hash,
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        customer = Customer(
            workspace_id=workspace_id,
            channel_identifier_hash=phone_hash,
            channel_type="whatsapp",
        )
        db.add(customer)
        await db.flush()
    else:
        customer.last_seen_at = datetime.now(timezone.utc)
    return customer


async def get_or_create_conversation(
    db, workspace_id: uuid.UUID, customer: Customer, channel_id: uuid.UUID
) -> Conversation:
    """Get active conversation (within session window) or create new one."""
    cutoff = datetime.now(timezone.utc).timestamp() - SESSION_WINDOW_SECONDS
    result = await db.execute(
        select(Conversation).where(
            Conversation.workspace_id == workspace_id,
            Conversation.customer_id == customer.id,
            Conversation.status == "active",
            Conversation.last_message_at >= datetime.fromtimestamp(cutoff, tz=timezone.utc),
        ).order_by(Conversation.last_message_at.desc()).limit(1)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        conversation = Conversation(
            workspace_id=workspace_id,
            customer_id=customer.id,
            channel_id=channel_id,
            status="active",
            first_message_at=datetime.now(timezone.utc),
            last_message_at=datetime.now(timezone.utc),
        )
        db.add(conversation)
        await db.flush()
    return conversation


async def process_message(msg_data: dict) -> None:
    workspace_id = uuid.UUID(msg_data["workspace_id"])
    sender_phone = msg_data["sender_phone"]
    text_body = msg_data["text"]
    external_id = msg_data["message_id"]

    logger.info("worker.processing", workspace_id=str(workspace_id), external_id=external_id)

    async with get_db_session(workspace_id) as db:
        # Resolve channel
        result = await db.execute(
            select(Channel).where(Channel.workspace_id == workspace_id, Channel.type == "whatsapp")
        )
        channel = result.scalar_one_or_none()
        if not channel:
            logger.error("worker.no_channel", workspace_id=str(workspace_id))
            return

        customer = await get_or_create_customer(db, workspace_id, sender_phone)
        conversation = await get_or_create_conversation(db, workspace_id, customer, channel.id)

        # Store inbound message
        normalized_text = normalize(text_body)
        inbound_msg = Message(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            sender_type="customer",
            content=text_body,
            content_normalized=normalized_text,
            external_id=external_id,
        )
        db.add(inbound_msg)
        await db.flush()

        # Fetch recent conversation history for RAG context
        from sqlalchemy import select as sa_select
        from radd.db.models import Message as MessageModel
        history_result = await db.execute(
            sa_select(MessageModel)
            .where(MessageModel.conversation_id == conversation.id)
            .order_by(MessageModel.created_at.desc())
            .limit(6)
        )
        history = [
            {"sender_type": m.sender_type, "content": m.content}
            for m in reversed(history_result.scalars().all())
        ]

        # Run full async pipeline (template + RAG)
        qdrant = get_qdrant()
        pipeline_result = await run_pipeline_async(
            message=normalized_text,
            workspace_id=workspace_id,
            db=db,
            qdrant=qdrant,
            conversation_context={
                "store_name": "متجرنا",  # Sprint 4+: load from workspace settings
            },
            conversation_history=history,
        )

        # Store system response message
        response_msg = Message(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            sender_type="system",
            content=pipeline_result.response_text,
            confidence={
                "intent": pipeline_result.confidence_breakdown.get("intent", 0),
                "retrieval": pipeline_result.confidence_breakdown.get("retrieval", 0),
                "verify": pipeline_result.confidence_breakdown.get("verify", 0),
            },
            source_passages=pipeline_result.source_passages or [],
        )
        db.add(response_msg)

        # Update conversation metadata
        conversation.intent = pipeline_result.intent
        conversation.dialect = pipeline_result.dialect
        conversation.confidence_score = pipeline_result.confidence
        conversation.resolution_type = pipeline_result.resolution_type
        conversation.last_message_at = datetime.now(timezone.utc)
        conversation.message_count = (conversation.message_count or 0) + 2

        if pipeline_result.resolution_type.startswith("escalated"):
            conversation.status = "waiting_agent"

        await db.flush()

        # Audit log
        db.add(AuditLog(
            workspace_id=workspace_id,
            action="message.processed",
            entity_type="conversation",
            entity_id=conversation.id,
            details={
                "intent": pipeline_result.intent,
                "dialect": pipeline_result.dialect,
                "resolution_type": pipeline_result.resolution_type,
                "confidence": pipeline_result.confidence,
            },
        ))

        # Create escalation event for hard/soft escalations
        escalation_event = None
        if pipeline_result.resolution_type in ("escalated_hard", "escalated_soft"):
            from radd.escalation.service import create_escalation
            escalation_event = await create_escalation(
                db=db,
                workspace_id=workspace_id,
                conversation=conversation,
                customer=customer,
                pipeline_result=pipeline_result,
                trigger_message_id=inbound_msg.id,
            )

    # Broadcast escalation to agent WebSocket (outside DB transaction)
    if escalation_event is not None:
        try:
            from radd.websocket.manager import ws_manager
            context = escalation_event.context_package or {}
            await ws_manager.broadcast_to_workspace(
                str(workspace_id),
                {
                    "type": "escalation.new",
                    "escalation_id": str(escalation_event.id),
                    "escalation_type": escalation_event.escalation_type,
                    "reason": escalation_event.reason,
                    "conversation_id": str(escalation_event.conversation_id),
                    "summary": context.get("summary", ""),
                    "confidence": float(escalation_event.confidence_at_escalation or 0),
                    "rag_draft": escalation_event.rag_draft,
                },
            )
        except Exception as e:
            logger.warning("worker.ws_notify_failed", error=str(e))

    # Apply guardrails before sending
    from radd.pipeline.guardrails import apply_guardrails
    guard = apply_guardrails(
        inbound_message=text_body,
        outbound_response=pipeline_result.response_text,
    )
    if guard.injection_detected:
        logger.warning("worker.injection_detected", workspace_id=str(workspace_id))
        final_response = "سأحولك لأحد فريقنا لمساعدتك."
    else:
        final_response = guard.redacted_text

    # Send WhatsApp response (outside DB transaction)
    try:
        channel_config = channel.config or {}
        await send_text_message(
            phone_number=sender_phone,
            message=final_response,
            phone_number_id=channel_config.get("wa_phone_number_id") or settings.wa_phone_number_id,
            api_token=settings.wa_api_token,
        )
    except Exception as e:
        logger.error("worker.send_failed", error=str(e), phone=sender_phone)


async def run_worker():
    r = get_redis()
    logger.info("worker.started", consumer_group=CONSUMER_GROUP, consumer=CONSUMER_NAME)

    # Discover all active workspace stream keys on startup
    # In production: use workspace registry. For MVP: scan keys.
    while True:
        try:
            keys = await r.keys("messages:*")
            if not keys:
                await asyncio.sleep(1)
                continue

            for stream_key in keys:
                # Ensure consumer group exists
                try:
                    await r.xgroup_create(stream_key, CONSUMER_GROUP, id="0", mkstream=True)
                except Exception:
                    pass  # Group already exists

                # Read new messages
                messages = await r.xreadgroup(
                    CONSUMER_GROUP,
                    CONSUMER_NAME,
                    {stream_key: ">"},
                    count=10,
                    block=BLOCK_MS,
                )

                if not messages:
                    continue

                for _, msg_list in messages:
                    for msg_id, msg_data in msg_list:
                        try:
                            await process_message(msg_data)
                            await r.xack(stream_key, CONSUMER_GROUP, msg_id)
                        except Exception as e:
                            logger.error("worker.message_failed", error=str(e), msg_id=msg_id)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("worker.loop_error", error=str(e))
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(run_worker())
