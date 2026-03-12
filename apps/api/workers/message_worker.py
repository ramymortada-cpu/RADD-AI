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
from radd.db.models import Channel, Conversation, Customer, Message, AuditLog, RevenueEvent, SmartRule as SmartRuleModel, FollowUpQueue
from radd.db.session import get_db_session
from radd.deps import get_redis
from radd.pipeline.normalizer import normalize
from radd.pipeline.intent import classify_intent
from radd.pipeline.dialect import detect_dialect
from radd.pipeline.entity_extractor import entities_to_dict, extract_entities
from radd.pipeline.orchestrator import run_pipeline_async
from radd.customers.profile_updater import update_profile
from radd.customers.context_builder import build_customer_context
from radd.whatsapp.client import send_text_message
from radd.personas.engine import select_persona, build_persona_prompt, PersonaType
from radd.returns.prevention import detect_return_reason, generate_prevention_response
from radd.rules.engine import evaluate_rules, apply_rule_action, DEFAULT_RULES, SmartRule as SmartRuleObj, TriggerType, ActionType
from radd.sales.engine import determine_stage

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
    message_type = msg_data.get("message_type", "text")
    media_id = msg_data.get("media_id", "")

    logger.info("worker.processing", workspace_id=str(workspace_id), external_id=external_id, type=message_type)

    # ── Image message: Vision pipeline ────────────────────────────────────────
    if message_type == "image" and media_id:
        await _process_image_message(workspace_id, sender_phone, external_id, media_id, text_body)
        return

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

        # ── Step 7: Normalize Arabic text ────────────────────────────────────
        normalized_text = normalize(text_body)

        # ── Step 8: Detect dialect ────────────────────────────────────────────
        dialect = detect_dialect(normalized_text)

        # ── Step 9: Classify intent (9 intents v0.2) ─────────────────────────
        intent_result = classify_intent(normalized_text)

        # ── Step 10: Extract entities → store in message.metadata ────────────
        raw_entities = extract_entities(normalized_text)
        entities = entities_to_dict(raw_entities)

        # ── Store inbound message ─────────────────────────────────────────────
        inbound_msg = Message(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            sender_type="customer",
            content=text_body,
            content_normalized=normalized_text,
            external_id=external_id,
            metadata_={"entities": entities, "dialect": dialect, "intent": intent_result.intent},
        )
        db.add(inbound_msg)
        await db.flush()

        # ── Step 11: Build customer context string ────────────────────────────
        customer_ctx = build_customer_context(customer)

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

        # ── Step 11b: V2 — Smart Rules evaluation ─────────────────────────────
        current_hour = datetime.now(timezone.utc).hour
        current_stage = getattr(conversation, "stage", "unknown") or "unknown"
        customer_sentiment = float(customer.avg_sentiment or 0.5)

        # Load workspace-specific rules from DB, fall back to defaults
        rules_result = await db.execute(
            select(SmartRuleModel).where(
                SmartRuleModel.workspace_id == workspace_id,
                SmartRuleModel.is_active == True,
            ).order_by(SmartRuleModel.priority.desc())
        )
        db_rules = rules_result.scalars().all()

        if db_rules:
            smart_rules = [
                SmartRuleObj(
                    id=str(r.id),
                    name=r.name,
                    description=r.description or "",
                    trigger_type=TriggerType(r.triggers[0]["type"]) if r.triggers else TriggerType.INTENT,
                    trigger_value=r.triggers[0]["value"] if r.triggers else "",
                    action_type=ActionType(r.actions[0]["type"]) if r.actions else ActionType.USE_PERSONA,
                    action_value=r.actions[0]["value"] if r.actions else "",
                    is_active=r.is_active,
                    priority=r.priority,
                )
                for r in db_rules
            ]
        else:
            smart_rules = DEFAULT_RULES

        rule_match = evaluate_rules(
            rules=smart_rules,
            intent=intent_result.intent,
            customer_tier=customer.customer_tier or "new",
            conversation_stage=current_stage,
            message_text=text_body,
            current_hour=current_hour,
            sentiment=customer_sentiment,
        )
        rule_instructions = apply_rule_action(rule_match)
        if rule_match.matched:
            logger.info(
                "worker.rule_matched",
                rule=rule_match.rule.name if rule_match.rule else "unknown",
                action=str(rule_match.action_type),
            )

        # ── Step 11c: V2 — Persona selection ──────────────────────────────────
        is_pre_purchase = intent_result.intent in {"product_inquiry", "product_comparison", "purchase_hesitation"}
        forced_persona_name = rule_instructions.get("force_persona")

        if forced_persona_name:
            persona_map = {"sales": PersonaType.SALES, "support": PersonaType.SUPPORT, "receptionist": PersonaType.RECEPTIONIST}
            from radd.personas.engine import PERSONAS
            persona = PERSONAS.get(persona_map.get(forced_persona_name, PersonaType.RECEPTIONIST))
        else:
            persona = select_persona(
                intent=intent_result.intent,
                is_pre_purchase=is_pre_purchase,
                conversation_turn=conversation.message_count or 0,
                customer_tier=customer.customer_tier or "new",
            )

        persona_system_prompt = build_persona_prompt(
            persona=persona,
            store_name="متجرنا",
            dialect=dialect.dialect if hasattr(dialect, "dialect") else str(dialect),
            customer_context=customer_ctx,
        )

        # ── Step 11d: V2 — Return Prevention attempt ───────────────────────────
        prevention_response = None
        if intent_result.intent == "return_policy" or rule_instructions.get("try_return_prevention"):
            try:
                return_reason = detect_return_reason(text_body)
                prevention_result = generate_prevention_response(
                    reason=return_reason,
                    dialect=dialect.dialect if hasattr(dialect, "dialect") else "gulf",
                )
                if prevention_result.confidence >= 0.65:
                    prevention_response = prevention_result.response_text
                    logger.info(
                        "worker.return_prevention_applied",
                        reason=str(return_reason),
                        confidence=prevention_result.confidence,
                    )
            except Exception as e:
                logger.warning("worker.return_prevention_failed", error=str(e))

        # ── Step 11e: V2 — Determine conversation stage ───────────────────────
        new_stage = determine_stage(
            intent=intent_result.intent,
            is_pre_purchase=is_pre_purchase,
            message_text=text_body,
            conversation_turn=conversation.message_count or 0,
            previous_stage=current_stage,
        )

        # ── Step 12: Run orchestrator with full context ───────────────────────
        # Force escalation if a rule demands it
        if rule_instructions.get("force_escalation"):
            from radd.pipeline.templates import get_escalation_message
            from radd.pipeline.orchestrator import PipelineResult
            dial_str = dialect.dialect if hasattr(dialect, "dialect") else "gulf"
            pipeline_result = PipelineResult(
                response_text=get_escalation_message(dial_str),
                intent=intent_result.intent,
                dialect=dial_str,
                confidence=0.0,
                resolution_type="escalated_hard",
                intent_result=intent_result,
                confidence_breakdown={"intent": intent_result.confidence, "retrieval": 0.0, "verify": 0.0},
            )
        else:
            override_threshold = rule_instructions.get("override_auto_threshold")
            from radd.deps import get_qdrant
            qdrant = get_qdrant()
            pipeline_result = await run_pipeline_async(
                message=normalized_text,
                workspace_id=workspace_id,
                db=db,
                qdrant=qdrant,
                conversation_context={
                    "store_name": "متجرنا",
                    "customer_context": customer_ctx,
                    "dialect": dialect.dialect if hasattr(dialect, "dialect") else str(dialect),
                    "intent": intent_result.intent,
                    "persona_system_prompt": persona_system_prompt,
                    "override_auto_threshold": override_threshold,
                },
                conversation_history=history,
            )

        # Apply return prevention if orchestrator didn't auto-respond
        if prevention_response and pipeline_result.resolution_type.startswith("escalated"):
            pipeline_result.response_text = prevention_response
            pipeline_result.resolution_type = "auto_rag"
            pipeline_result.confidence = 0.75

        # ── Step 15: Store outbound message ──────────────────────────────────
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
        conversation.stage = new_stage.value if hasattr(new_stage, "value") else str(new_stage)
        conversation.ai_persona = persona.type.value if persona else None

        if pipeline_result.resolution_type.startswith("escalated"):
            conversation.status = "waiting_agent"

        await db.flush()

        # ── Step 16: Update customer profile ─────────────────────────────────
        try:
            await update_profile(
                db=db,
                customer=customer,
                resolution_type=pipeline_result.resolution_type,
                message_text=text_body,
            )
        except Exception as e:
            logger.warning("worker.profile_update_failed", error=str(e))

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

    # ── Step 17: Send (or log-only in shadow mode) ───────────────────────────
    if settings.shadow_mode:
        logger.info(
            "worker.shadow_mode.suppressed",
            workspace_id=str(workspace_id),
            phone=sender_phone,
            response_preview=final_response[:120],
            resolution_type=pipeline_result.resolution_type,
            confidence=round(pipeline_result.confidence, 3),
        )
    else:
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


async def _process_image_message(
    workspace_id: uuid.UUID,
    sender_phone: str,
    external_id: str,
    media_id: str,
    caption: str,
) -> None:
    """Process an image message using Vision pipeline."""
    async with get_db_session(workspace_id) as db:
        result = await db.execute(
            select(Channel).where(Channel.workspace_id == workspace_id, Channel.type == "whatsapp")
        )
        channel = result.scalar_one_or_none()
        if not channel:
            return

        customer = await get_or_create_customer(db, workspace_id, sender_phone)
        conversation = await get_or_create_conversation(db, workspace_id, customer, channel.id)

        channel_config = channel.config or {}
        wa_token = channel_config.get("wa_api_token") or settings.wa_api_token
        dialect_result = detect_dialect(caption or "")
        dialect_str = dialect_result.dialect if hasattr(dialect_result, "dialect") else "gulf"

        from radd.vision.image_analyzer import process_whatsapp_image
        vision_result = await process_whatsapp_image(
            media_id=media_id,
            wa_token=wa_token,
            dialect=dialect_str,
            store_name="متجرنا",
            customer_text=caption,
        )

        response_text = vision_result.get("response_text", "تعذّر تحليل الصورة. سأحولك لفريق الدعم.")

        # Store messages
        inbound = Message(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            sender_type="customer",
            content=caption or "[صورة]",
            external_id=external_id,
            metadata_={"message_type": "image", "media_id": media_id, "image_type": vision_result.get("image_type", "")},
        )
        db.add(inbound)

        outbound = Message(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            sender_type="system",
            content=response_text,
        )
        db.add(outbound)
        conversation.last_message_at = datetime.now(timezone.utc)
        conversation.message_count = (conversation.message_count or 0) + 2
        await db.flush()

    if not settings.shadow_mode:
        try:
            await send_text_message(
                phone_number=sender_phone,
                message=response_text,
                phone_number_id=channel_config.get("wa_phone_number_id") or settings.wa_phone_number_id,
                api_token=wa_token,
            )
        except Exception as e:
            logger.error("worker.image_send_failed", error=str(e))


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
