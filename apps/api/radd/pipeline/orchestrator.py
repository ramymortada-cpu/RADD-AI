from __future__ import annotations
"""
Pipeline orchestrator — Sprint 2/3 (full template + RAG path).
Input: normalized Arabic message + conversation context + optional DB/Qdrant clients.
Output: PipelineResult.

Routing logic:
  C_intent ≥ 0.85 AND template intent → template path (C = C_intent)
  else → RAG path (retrieve → generate → verify → route by min confidence)
    ≥ 0.85 → auto-respond
    0.60–0.84 → soft escalation (draft queued)
    < 0.60 → hard escalation (agent takes over)
"""
from dataclasses import dataclass, field

import structlog

from radd.config import settings
from radd.pipeline.dialect import DialectResult, detect_dialect
from radd.pipeline.intent import IntentResult, classify_intent
from radd.pipeline.normalizer import is_arabic, normalize
from radd.pipeline.templates import (
    TemplateResult,
    get_escalation_message,
    is_template_intent,
    render_template,
)

logger = structlog.get_logger()


@dataclass
class PipelineResult:
    response_text: str
    intent: str
    dialect: str
    confidence: float
    resolution_type: str            # auto_template | auto_rag | escalated_hard | escalated_soft
    intent_result: IntentResult | None = None
    dialect_result: DialectResult | None = None
    template_result: TemplateResult | None = None
    source_passages: list[dict] = field(default_factory=list)
    confidence_breakdown: dict = field(default_factory=dict)
    rag_draft: str | None = None    # For soft escalation: draft to show agent


def run_pipeline(
    message: str,
    conversation_context: dict | None = None,
) -> PipelineResult:
    """
    Synchronous pipeline for Sprint 1 template path only.
    Used by the message worker when no DB/Qdrant is available (fallback).
    """
    context = conversation_context or {}

    if not is_arabic(message):
        return PipelineResult(
            response_text="أهلاً! يسعدنا مساعدتك. رسائلنا باللغة العربية.",
            intent="other",
            dialect="msa",
            confidence=1.0,
            resolution_type="auto_template",
        )

    normalized = normalize(message)
    dialect_result = detect_dialect(normalized)
    dialect = dialect_result.dialect
    intent_result = classify_intent(normalized)
    intent = intent_result.intent

    if is_template_intent(intent) and intent_result.confidence >= settings.confidence_auto_threshold:
        params = {
            "customer_name": context.get("customer_name", ""),
            "order_number": context.get("order_number", ""),
            "store_name": context.get("store_name", "متجرنا"),
        }
        template_result = render_template(intent, dialect, params)
        if template_result:
            return PipelineResult(
                response_text=template_result.text,
                intent=intent,
                dialect=dialect,
                confidence=intent_result.confidence,
                resolution_type="auto_template",
                intent_result=intent_result,
                dialect_result=dialect_result,
                template_result=template_result,
                confidence_breakdown={
                    "intent": intent_result.confidence,
                    "retrieval": 1.0,
                    "verify": 1.0,
                },
            )

    escalation_msg = get_escalation_message(dialect)
    return PipelineResult(
        response_text=escalation_msg,
        intent=intent,
        dialect=dialect,
        confidence=intent_result.confidence,
        resolution_type="escalated_hard",
        intent_result=intent_result,
        dialect_result=dialect_result,
        confidence_breakdown={
            "intent": intent_result.confidence,
            "retrieval": 0.0,
            "verify": 0.0,
        },
    )


async def run_pipeline_async(
    message: str,
    workspace_id,
    db,
    qdrant,
    conversation_context: dict | None = None,
    conversation_history: list[dict] | None = None,
) -> PipelineResult:
    """
    Full async pipeline: template path OR RAG path.
    Requires DB session + Qdrant client (Sprint 2+).
    """
    context = conversation_context or {}

    # ── Not Arabic ────────────────────────────────────────────────────────────
    if not is_arabic(message):
        return PipelineResult(
            response_text="أهلاً! يسعدنا مساعدتك. رسائلنا باللغة العربية.",
            intent="other",
            dialect="msa",
            confidence=1.0,
            resolution_type="auto_template",
        )

    # ── 1. Normalize ──────────────────────────────────────────────────────────
    normalized = normalize(message)

    # ── 2. Detect dialect ─────────────────────────────────────────────────────
    dialect_result = detect_dialect(normalized)
    dialect = dialect_result.dialect

    # ── 3. Classify intent ────────────────────────────────────────────────────
    if settings.use_intent_v2:
        from radd.pipeline.intent_v2 import classify_intent_llm
        from radd.deps import get_redis
        redis_client = get_redis()
        hist_str = [h.get("content", "") for h in (conversation_history or [])] if conversation_history else None
        intent_dict = await classify_intent_llm(normalized, conversation_history=hist_str, redis_client=redis_client)
        intent = intent_dict["intent_name"]
        confidence_intent = intent_dict.get("confidence", 0.5)
        entities = intent_dict.get("entities", {})
        # خريطة النوايا للـ templates: shipping_inquiry → shipping
        if intent == "shipping_inquiry":
            intent = "shipping"
        intent_result = IntentResult(intent=intent, confidence=confidence_intent)
        order_number_from_entities = entities.get("order_number")
    else:
        intent_result = classify_intent(normalized)
        intent = intent_result.intent
        order_number_from_entities = None  # v1 doesn't extract entities

    # ── 4a. Action path (Salla order status) ─────────────────────────────────
    if intent == "order_status":
        from radd.actions.base import detect_and_run_action
        workspace_config = context.get("workspace_config", {})
        action_result = await detect_and_run_action(intent, message, dialect, workspace_config)
        if action_result:
            logger.info("pipeline.action_path", action=action_result.action, dialect=dialect)
            return PipelineResult(
                response_text=action_result.response_text,
                intent=intent,
                dialect=dialect,
                confidence=0.95,
                resolution_type="auto_template",
                intent_result=intent_result,
                dialect_result=dialect_result,
                confidence_breakdown={"intent": intent_result.confidence, "retrieval": 1.0, "verify": 1.0},
            )

    # ── 4b. Template path ─────────────────────────────────────────────────────
    if is_template_intent(intent) and intent_result.confidence >= settings.confidence_auto_threshold:
        params = {
            "customer_name": context.get("customer_name", ""),
            "order_number": (order_number_from_entities or context.get("order_number", "")) if order_number_from_entities else context.get("order_number", ""),
            "store_name": context.get("store_name", "متجرنا"),
        }
        template_result = render_template(intent, dialect, params)
        if template_result:
            logger.info("pipeline.template_path", intent=intent, dialect=dialect)
            return PipelineResult(
                response_text=template_result.text,
                intent=intent,
                dialect=dialect,
                confidence=intent_result.confidence,
                resolution_type="auto_template",
                intent_result=intent_result,
                dialect_result=dialect_result,
                template_result=template_result,
                confidence_breakdown={
                    "intent": intent_result.confidence,
                    "retrieval": 1.0,
                    "verify": 1.0,
                },
            )

    # ── 5. RAG path ───────────────────────────────────────────────────────────
    from radd.pipeline.retriever import retrieve
    from radd.pipeline.generator import generate_rag_response

    passages, c_retrieval = await retrieve(
        query=normalized,
        workspace_id=workspace_id,
        db=db,
        qdrant=qdrant,
    )

    # No KB content → hard escalate
    if not passages or c_retrieval < 0.20:
        logger.info("pipeline.no_passages", intent=intent, c_retrieval=c_retrieval)
        return PipelineResult(
            response_text=get_escalation_message(dialect),
            intent=intent,
            dialect=dialect,
            confidence=min(intent_result.confidence, c_retrieval),
            resolution_type="escalated_hard",
            intent_result=intent_result,
            dialect_result=dialect_result,
            confidence_breakdown={
                "intent": intent_result.confidence,
                "retrieval": c_retrieval,
                "verify": 0.0,
            },
        )

    # Generate response — use persona prompt if available, else standard context
    store_name = context.get("store_name", "متجرنا")
    customer_context = context.get("customer_context", "")
    persona_system_prompt = context.get("persona_system_prompt")
    response_text, cited_ids = await generate_rag_response(
        query=normalized,
        passages=passages,
        dialect=dialect,
        store_name=store_name,
        conversation_history=conversation_history,
        customer_context=customer_context,
        system_prompt_override=persona_system_prompt,
    )

    # Verify grounding
    passage_texts = [p.content for p in passages]
    if settings.use_verifier_v2:
        from radd.pipeline.verifier_v2 import verify_response_async
        c_verify, is_grounded, _details = await verify_response_async(response_text, passage_texts)
    else:
        from radd.pipeline.verifier import verify_response_fast
        c_verify, is_grounded = verify_response_fast(response_text, passage_texts)

    # Full confidence = min of all three signals
    confidence = min(intent_result.confidence, c_retrieval, c_verify)

    source_passages_log = [
        {
            "chunk_id": p.chunk_id,
            "document_id": p.document_id,
            "score": round(p.score, 3),
            "text_preview": p.content[:150],
        }
        for p in passages
    ]

    confidence_breakdown = {
        "intent": round(intent_result.confidence, 3),
        "retrieval": round(c_retrieval, 3),
        "verify": round(c_verify, 3),
    }

    # ── 6. Confidence routing ─────────────────────────────────────────────────
    auto_threshold = context.get("override_auto_threshold") or settings.confidence_auto_threshold
    soft_threshold = settings.confidence_soft_escalation_threshold

    if confidence >= auto_threshold:
        logger.info("pipeline.rag_auto", confidence=confidence, intent=intent)
        return PipelineResult(
            response_text=response_text,
            intent=intent,
            dialect=dialect,
            confidence=confidence,
            resolution_type="auto_rag",
            intent_result=intent_result,
            dialect_result=dialect_result,
            source_passages=source_passages_log,
            confidence_breakdown=confidence_breakdown,
        )

    elif confidence >= soft_threshold:
        # Soft escalation: pass draft to agent
        logger.info("pipeline.soft_escalate", confidence=confidence, intent=intent)
        return PipelineResult(
            response_text=get_escalation_message(dialect),
            intent=intent,
            dialect=dialect,
            confidence=confidence,
            resolution_type="escalated_soft",
            intent_result=intent_result,
            dialect_result=dialect_result,
            source_passages=source_passages_log,
            confidence_breakdown=confidence_breakdown,
            rag_draft=response_text,
        )

    else:
        # Hard escalation
        logger.info("pipeline.hard_escalate", confidence=confidence, intent=intent)
        return PipelineResult(
            response_text=get_escalation_message(dialect),
            intent=intent,
            dialect=dialect,
            confidence=confidence,
            resolution_type="escalated_hard",
            intent_result=intent_result,
            dialect_result=dialect_result,
            source_passages=source_passages_log,
            confidence_breakdown=confidence_breakdown,
        )
