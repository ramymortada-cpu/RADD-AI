"""
Message worker — Redis Streams consumer.
Reads from messages:{workspace_id} streams.
Runs the pipeline, stores results, sends WhatsApp response.
"""
import asyncio
import hashlib
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import structlog
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent))

from radd.alerts import alert_manager, init_alert_manager
from radd.config import settings
from radd.customers.context_builder import build_customer_context
from radd.customers.profile_updater import update_profile
from radd.db.models import (
    AuditLog,
    Channel,
    Conversation,
    Customer,
    Message,
    Workspace,
)
from radd.db.models import SmartRule as SmartRuleModel
from radd.db.session import get_db_session
from radd.deps import get_redis
from radd.personas.engine import PersonaType, build_persona_prompt, select_persona
from radd.pipeline.dialect import detect_dialect
from radd.pipeline.entity_extractor import entities_to_dict, extract_entities
from radd.pipeline.intent import IntentResult
from radd.pipeline.intent_v2 import classify_intent_llm
from radd.pipeline.normalizer import normalize
from radd.pipeline.orchestrator import run_pipeline_async
from radd.returns.prevention import detect_return_reason, generate_prevention_response
from radd.rules.engine import (
    DEFAULT_RULES,
    ActionType,
    TriggerType,
    apply_rule_action,
    evaluate_rules,
)
from radd.rules.engine import SmartRule as SmartRuleObj
from radd.sales.engine import determine_stage
from radd.whatsapp.client import send_text_message

logger = structlog.get_logger()

# CONSUMER_GROUP = "radd-workers"  # deprecated — use per-workspace groups
CONSUMER_NAME_PREFIX = "radd-worker"
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
        customer.last_seen_at = datetime.now(UTC)
    return customer


async def get_or_create_conversation(
    db, workspace_id: uuid.UUID, customer: Customer, channel_id: uuid.UUID
) -> Conversation:
    """Get active conversation (within session window) or create new one."""
    cutoff = datetime.now(UTC).timestamp() - SESSION_WINDOW_SECONDS
    result = await db.execute(
        select(Conversation).where(
            Conversation.workspace_id == workspace_id,
            Conversation.customer_id == customer.id,
            Conversation.status == "active",
            Conversation.last_message_at >= datetime.fromtimestamp(cutoff, tz=UTC),
        ).order_by(Conversation.last_message_at.desc()).limit(1)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        conversation = Conversation(
            workspace_id=workspace_id,
            customer_id=customer.id,
            channel_id=channel_id,
            status="active",
            first_message_at=datetime.now(UTC),
            last_message_at=datetime.now(UTC),
        )
        db.add(conversation)
        await db.flush()
    return conversation


async def _handle_media_messages(msg_data: dict, workspace_id: uuid.UUID) -> str | None:
    """Handle voice and image messages. Returns None if handled (skip), else text to process."""
    sender_phone = msg_data["sender_phone"]
    text_body = msg_data["text"]
    external_id = msg_data["message_id"]
    message_type = msg_data.get("message_type", "text")
    media_id = msg_data.get("media_id", "")

    if message_type == "voice" and media_id:
        voice_enabled = True
        try:
            async with get_db_session(workspace_id) as _db:
                from radd.db.models import Workspace as WsModel
                _ws = await _db.get(WsModel, workspace_id)
                if _ws:
                    _cfg = _ws.settings or {}
                    voice_enabled = _cfg.get("voice_transcription_enabled", True)
        except Exception:
            pass

        if voice_enabled:
            from radd.workers.voice_handler import process_voice_message as _process_voice
            transcribed = await _process_voice(
                workspace_id, sender_phone, external_id, media_id,
                get_or_create_customer, get_or_create_conversation,
            )
            if transcribed:
                await process_message({
                    "workspace_id": str(workspace_id),
                    "sender_phone": sender_phone,
                    "text": transcribed,
                    "message_id": external_id,
                    "message_type": "text",
                    "media_id": "",
                })
            return None
        text_body = "[رسالة صوتية — التفريغ موقوف]"

    if message_type == "image" and media_id:
        from radd.workers.vision_handler import process_image_message as _process_image
        await _process_image(
            workspace_id, sender_phone, external_id, media_id, text_body,
            get_or_create_customer, get_or_create_conversation,
        )
        return None

    return text_body


async def _run_nlp_pipeline(text_body: str, workspace_id: uuid.UUID) -> dict:
    """Normalize, detect dialect, classify intent, extract entities."""
    normalized_text = normalize(text_body)
    dialect = detect_dialect(normalized_text)
    intent_dict = await classify_intent_llm(normalized_text, redis_client=get_redis())
    intent_name = intent_dict["intent_name"]
    if intent_name == "shipping_inquiry":
        intent_name = "shipping"
    intent_result = IntentResult(
        intent=intent_name,
        confidence=intent_dict.get("confidence", 0.95),
    )
    raw_entities = extract_entities(normalized_text)
    entities = entities_to_dict(raw_entities)
    return {
        "normalized": normalized_text,
        "dialect": dialect,
        "intent_result": intent_result,
        "entities": entities,
    }


async def _build_context(db, workspace_id: uuid.UUID, customer: Customer, conversation: Conversation) -> dict:
    """Build customer context and fetch message history."""
    customer_ctx = build_customer_context(customer)
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
    return {"customer_context": customer_ctx, "history": history}


async def _apply_smart_rules(
    db,
    workspace_id: uuid.UUID,
    intent_result: IntentResult,
    customer: Customer,
    conversation: Conversation,
    text_body: str,
    dialect,
    customer_ctx: str,
) -> dict:
    """Evaluate rules and select persona."""
    current_hour = datetime.now(UTC).hour
    current_stage = getattr(conversation, "stage", "unknown") or "unknown"
    customer_sentiment = float(customer.avg_sentiment or 0.5)

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

    return {
        "rule_match": rule_match,
        "rule_instructions": rule_instructions,
        "persona": persona,
        "persona_system_prompt": persona_system_prompt,
        "is_pre_purchase": is_pre_purchase,
        "current_stage": current_stage,
    }


async def _handle_return_prevention(
    intent_result: IntentResult,
    rule_instructions: dict,
    text_body: str,
    dialect,
) -> str | None:
    """Attempt return prevention. Returns prevention response or None."""
    if intent_result.intent != "return_policy" and not rule_instructions.get("try_return_prevention"):
        return None
    try:
        return_reason = detect_return_reason(text_body)
        prevention_result = generate_prevention_response(
            reason=return_reason,
            dialect=dialect.dialect if hasattr(dialect, "dialect") else "gulf",
        )
        if prevention_result.confidence >= 0.65:
            logger.info(
                "worker.return_prevention_applied",
                reason=str(return_reason),
                confidence=prevention_result.confidence,
            )
            return prevention_result.response_text
    except Exception as e:
        logger.warning("worker.return_prevention_failed", error=str(e))
    return None


async def _run_orchestrator(
    db,
    workspace_id: uuid.UUID,
    normalized_text: str,
    intent_result: IntentResult,
    dialect,
    customer_ctx: str,
    persona_system_prompt: str,
    history: list,
    rule_instructions: dict,
) -> object:
    """Run pipeline or force escalation. Returns PipelineResult."""
    if rule_instructions.get("force_escalation"):
        from radd.pipeline.orchestrator import PipelineResult
        from radd.pipeline.templates import get_escalation_message
        dial_str = dialect.dialect if hasattr(dialect, "dialect") else "gulf"
        return PipelineResult(
            response_text=get_escalation_message(dial_str),
            intent=intent_result.intent,
            dialect=dial_str,
            confidence=0.0,
            resolution_type="escalated_hard",
            intent_result=intent_result,
            confidence_breakdown={"intent": intent_result.confidence, "retrieval": 0.0, "verify": 0.0},
        )
    override_threshold = rule_instructions.get("override_auto_threshold")
    ws_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = ws_result.scalar_one_or_none()
    ws_settings = (ws.settings or {}) if ws else {}
    if ws_settings.get("automation_paused"):
        from radd.pipeline.orchestrator import PipelineResult
        from radd.pipeline.templates import get_escalation_message
        dial_str = dialect.dialect if hasattr(dialect, "dialect") else "gulf"
        logger.info("worker.automation_paused", workspace_id=str(workspace_id), reason="automation_paused")
        return PipelineResult(
            response_text=get_escalation_message(dial_str),
            intent=intent_result.intent,
            dialect=dial_str,
            confidence=0.0,
            resolution_type="escalated_hard",
            intent_result=intent_result,
            confidence_breakdown={"intent": intent_result.confidence, "retrieval": 0.0, "verify": 0.0},
            escalation_reason_override="automation_paused",
        )
    use_intent_v2 = ws_settings.get("use_intent_v2") if "use_intent_v2" in ws_settings else settings.use_intent_v2
    use_verifier_v2 = ws_settings.get("use_verifier_v2") if "use_verifier_v2" in ws_settings else settings.use_verifier_v2
    from radd.deps import get_qdrant
    qdrant = get_qdrant()
    return await run_pipeline_async(
        message=normalized_text,
        workspace_id=workspace_id,
        db=db,
        qdrant=qdrant,
        conversation_context={
            "store_name": ws_settings.get("store_name", "متجرنا"),
            "customer_context": customer_ctx,
            "dialect": dialect.dialect if hasattr(dialect, "dialect") else str(dialect),
            "intent": intent_result.intent,
            "persona_system_prompt": persona_system_prompt,
            "override_auto_threshold": override_threshold,
            "use_intent_v2": use_intent_v2,
            "use_verifier_v2": use_verifier_v2,
            "workspace_config": ws_settings,
        },
        conversation_history=history,
    )


async def _store_outbound_and_update(
    db,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    customer: Customer,
    inbound_msg: Message,
    pipeline_result,
    text_body: str,
    persona,
    new_stage,
) -> object | None:
    """Store outbound message, update conversation, create escalation, audit log."""
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

    conversation.intent = pipeline_result.intent
    conversation.dialect = pipeline_result.dialect
    conversation.confidence_score = pipeline_result.confidence
    conversation.resolution_type = pipeline_result.resolution_type
    conversation.last_message_at = datetime.now(UTC)
    conversation.message_count = (conversation.message_count or 0) + 2
    conversation.stage = new_stage.value if hasattr(new_stage, "value") else str(new_stage)
    conversation.ai_persona = persona.type.value if persona else None

    if pipeline_result.resolution_type.startswith("escalated"):
        conversation.status = "waiting_agent"

    await db.flush()

    try:
        await update_profile(
            db=db,
            customer=customer,
            resolution_type=pipeline_result.resolution_type,
            message_text=text_body,
        )
    except Exception as e:
        logger.warning("worker.profile_update_failed", error=str(e))

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

    escalation_event = None
    ESCALATION_QUEUE_LIMIT = 50
    if pipeline_result.resolution_type in ("escalated_hard", "escalated_soft"):
        from radd.escalation.service import create_escalation, get_pending_escalations_count
        reason_override = getattr(pipeline_result, "escalation_reason_override", None)
        escalation_event = await create_escalation(
            db=db,
            workspace_id=workspace_id,
            conversation=conversation,
            customer=customer,
            pipeline_result=pipeline_result,
            trigger_message_id=inbound_msg.id,
            reason_override=reason_override,
        )
        try:
            pending_count = await get_pending_escalations_count(db, workspace_id)
            if pending_count > ESCALATION_QUEUE_LIMIT:
                await alert_manager.warning(
                    event="escalation_queue_overflow",
                    message=f"Escalation queue has {pending_count} pending items",
                    context={
                        "workspace_id": str(workspace_id),
                        "pending_count": pending_count,
                        "limit": ESCALATION_QUEUE_LIMIT,
                    },
                )
        except Exception:
            pass

    return escalation_event


async def _post_process_and_send(
    workspace_id: uuid.UUID,
    sender_phone: str,
    text_body: str,
    pipeline_result,
    prevention_response: str | None,
    dialect,
    channel: Channel,
    new_stage,
    db,
    conversation: Conversation,
    customer: Customer,
    escalation_event: object | None,
) -> None:
    """Broadcast escalation, apply guardrails, schedule follow-up, send response."""
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

    should_schedule_followup = (
        new_stage.value in ("consideration", "objection", "inquiry")
        if hasattr(new_stage, "value") else False
    )
    if should_schedule_followup and not pipeline_result.resolution_type.startswith("escalated"):
        try:
            from radd.followups.scheduler import schedule_abandoned_sale_followup
            await schedule_abandoned_sale_followup(
                db_session=db,
                workspace_id=str(workspace_id),
                conversation_id=str(conversation.id),
                customer_id=str(customer.id),
                product_name="",
                delay_minutes=120,
            )
            logger.info("worker.followup_scheduled", stage=str(new_stage))
        except Exception as e:
            logger.warning("worker.followup_schedule_failed", error=str(e))

    await _send_final_response(
        sender_phone, final_response, channel, dialect, text_body,
        pipeline_result, prevention_response, workspace_id,
    )


async def _send_final_response(
    sender_phone: str,
    final_response: str,
    channel: Channel,
    dialect,
    text_body: str,
    pipeline_result,
    prevention_response: str | None,
    workspace_id: uuid.UUID,
) -> None:
    """Send via WhatsApp or log in shadow mode."""
    from radd.utils.crypto import get_channel_config_decrypted
    channel_config = get_channel_config_decrypted(channel)
    wa_phone_number_id = channel_config.get("wa_phone_number_id") or settings.wa_phone_number_id
    wa_token = settings.wa_api_token

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
            if prevention_response and pipeline_result.resolution_type != "escalated_hard":
                from radd.returns.prevention import detect_return_reason
                from radd.whatsapp.interactive import (
                    build_return_prevention_message,
                    send_interactive_message,
                )
                return_reason = detect_return_reason(text_body)
                interactive_payload = build_return_prevention_message(
                    reason=str(return_reason),
                    dialect=dialect.dialect if hasattr(dialect, "dialect") else "gulf",
                )
                sent = await send_interactive_message(
                    phone_number=sender_phone,
                    message_payload=interactive_payload,
                    phone_number_id=wa_phone_number_id,
                    api_token=wa_token,
                )
                if not sent:
                    await send_text_message(
                        phone_number=sender_phone,
                        message=final_response,
                        phone_number_id=wa_phone_number_id,
                        api_token=wa_token,
                    )
            else:
                await send_text_message(
                    phone_number=sender_phone,
                    message=final_response,
                    phone_number_id=wa_phone_number_id,
                    api_token=wa_token,
                )
        except Exception as e:
            logger.error("worker.send_failed", error=str(e), phone=sender_phone)


async def process_message(msg_data: dict) -> None:
    workspace_id = uuid.UUID(msg_data["workspace_id"])
    sender_phone = msg_data["sender_phone"]
    external_id = msg_data["message_id"]
    message_type = msg_data.get("message_type", "text")

    logger.info("worker.processing", workspace_id=str(workspace_id), external_id=external_id, type=message_type)

    text_body = await _handle_media_messages(msg_data, workspace_id)
    if text_body is None:
        return

    async with get_db_session(workspace_id) as db:
        result = await db.execute(
            select(Channel).where(Channel.workspace_id == workspace_id, Channel.type == "whatsapp")
        )
        channel = result.scalar_one_or_none()
        if not channel:
            logger.error("worker.no_channel", workspace_id=str(workspace_id))
            return

        customer = await get_or_create_customer(db, workspace_id, sender_phone)
        conversation = await get_or_create_conversation(db, workspace_id, customer, channel.id)

        nlp = await _run_nlp_pipeline(text_body, workspace_id)
        normalized_text = nlp["normalized"]
        dialect = nlp["dialect"]
        intent_result = nlp["intent_result"]
        entities = nlp["entities"]

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

        context = await _build_context(db, workspace_id, customer, conversation)
        customer_ctx = context["customer_context"]
        history = context["history"]

        rules_result = await _apply_smart_rules(
            db, workspace_id, intent_result, customer, conversation, text_body, dialect, customer_ctx
        )
        rule_instructions = rules_result["rule_instructions"]
        persona = rules_result["persona"]
        persona_system_prompt = rules_result["persona_system_prompt"]
        is_pre_purchase = rules_result["is_pre_purchase"]
        current_stage = rules_result["current_stage"]

        prevention_response = await _handle_return_prevention(
            intent_result, rule_instructions, text_body, dialect
        )

        new_stage = determine_stage(
            intent=intent_result.intent,
            is_pre_purchase=is_pre_purchase,
            message_text=text_body,
            conversation_turn=conversation.message_count or 0,
            previous_stage=current_stage,
        )

        pipeline_result = await _run_orchestrator(
            db, workspace_id, normalized_text, intent_result, dialect,
            customer_ctx, persona_system_prompt, history, rule_instructions,
        )

        if prevention_response and pipeline_result.resolution_type.startswith("escalated"):
            pipeline_result.response_text = prevention_response
            pipeline_result.resolution_type = "auto_rag"
            pipeline_result.confidence = 0.75

        escalation_event = await _store_outbound_and_update(
            db, workspace_id, conversation, customer, inbound_msg,
            pipeline_result, text_body, persona, new_stage,
        )

    await _post_process_and_send(
        workspace_id, sender_phone, text_body, pipeline_result, prevention_response,
        dialect, channel, new_stage, db, conversation, customer, escalation_event,
    )


async def run_worker():
    init_alert_manager(
        slack_webhook_url=settings.slack_alert_webhook_url,
        app_env=settings.app_env,
    )
    r = get_redis()
    consumer_name = f"{CONSUMER_NAME_PREFIX}-{uuid.uuid4().hex[:8]}"
    logger.info("worker.started", consumer=consumer_name)

    # Discover all active workspace stream keys on startup
    # In production: use workspace registry. For MVP: scan keys.
    while True:
        try:
            keys = await r.keys("messages:*")
            if not keys:
                await asyncio.sleep(1)
                continue

            for stream_key in keys:
                # Per-workspace consumer group: messages:{workspace_id} → group:{workspace_id}
                stream_key_str = stream_key.decode("utf-8") if isinstance(stream_key, bytes) else stream_key
                workspace_id_str = stream_key_str.split(":", 1)[1] if ":" in stream_key_str else "default"
                consumer_group = f"group:{workspace_id_str}"

                # Ensure consumer group exists
                try:
                    await r.xgroup_create(stream_key, consumer_group, id="0", mkstream=True)
                except Exception as e:
                    if "BUSYGROUP" not in str(e):
                        logger.warning("worker.xgroup_create_failed", group=consumer_group, error=str(e))

                # Read new messages
                messages = await r.xreadgroup(
                    consumer_group,
                    consumer_name,
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
                            await r.xack(stream_key, consumer_group, msg_id)
                        except Exception as e:
                            logger.error("worker.message_failed", error=str(e), msg_id=msg_id)
                            _data = msg_data if isinstance(msg_data, dict) else {}
                            _ws_id = _data.get("workspace_id", _data.get(b"workspace_id", ""))
                            try:
                                from radd.monitoring.sentry_and_logging import (
                                    capture_pipeline_error,
                                )
                                capture_pipeline_error(e, str(_ws_id), "")
                            except Exception:
                                pass
                            try:
                                await alert_manager.critical(
                                    event="message_processing_failed",
                                    message="Failed to process customer message",
                                    context={
                                        "workspace_id": str(_ws_id) if _ws_id else "unknown",
                                        "error": str(e)[:200],
                                        "error_type": type(e).__name__,
                                    },
                                )
                            except Exception:
                                pass

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("worker.loop_error", error=str(e))
            try:
                await alert_manager.fatal(
                    event="worker_crashed",
                    message="Message worker stopped processing — requires immediate restart",
                    context={
                        "error": str(e)[:200],
                        "error_type": type(e).__name__,
                    },
                )
            except Exception:
                pass
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(run_worker())
