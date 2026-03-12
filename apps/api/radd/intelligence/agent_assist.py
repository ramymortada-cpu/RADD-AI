from __future__ import annotations
"""
RADD AI — Agent Assist
When a conversation is escalated, generate:
1. A smart reply suggestion for the agent
2. A context summary (customer history, sentiment, issue)
3. KB passages most relevant to this conversation
"""
import structlog
from openai import AsyncOpenAI

from radd.config import settings

logger = structlog.get_logger()

AGENT_ASSIST_PROMPT = """أنت مساعد لموظف خدمة عملاء محترف.

لديك:
- محادثة عميل مع الـ AI
- تاريخ العميل ومعلوماته
- مقاطع قاعدة المعرفة ذات الصلة

مهمتك: اقترح للموظف رداً مناسباً وقصيراً. لا تطيل. الموظف يريد اقتراحاً يبدأ منه ويعدّله.

قواعد:
- اكتب المقترح بالعربية، كأنك الموظف تتكلم مع العميل مباشرة
- لا تذكر إنه اقتراح AI
- لا تختلق معلومات
- أضف [مطلوب: ...] إذا الموظف يحتاج معلومة إضافية قبل الرد
- اللهجة: {dialect}"""


async def generate_agent_suggestion(
    customer_message: str,
    conversation_history: list[dict],
    customer_context: str,
    kb_passages: list[str],
    dialect: str = "gulf",
    escalation_reason: str = "",
) -> dict:
    """
    Generate a smart reply suggestion for the escalation agent.
    Returns suggestion, confidence, and recommended_action.
    """
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Build context
    history_text = ""
    for msg in conversation_history[-6:]:
        role = "العميل" if msg.get("sender_type") == "customer" else "الـ AI"
        history_text += f"{role}: {msg.get('content', '')}\n"

    kb_text = "\n".join([f"- {p}" for p in kb_passages[:3]]) if kb_passages else "لا توجد مقاطع ذات صلة"

    user_content = f"""## المحادثة:
{history_text}

## آخر رسالة من العميل:
{customer_message}

## معلومات العميل:
{customer_context or "لا توجد معلومات"}

## سبب التصعيد:
{escalation_reason or "تصعيد تلقائي"}

## مقاطع قاعدة المعرفة ذات الصلة:
{kb_text}

---
اكتب اقتراح الرد للموظف:"""

    dialect_display = {"gulf": "خليجية", "egyptian": "مصرية", "msa": "فصحى"}.get(dialect, "خليجية")

    try:
        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {
                    "role": "system",
                    "content": AGENT_ASSIST_PROMPT.format(dialect=dialect_display),
                },
                {"role": "user", "content": user_content},
            ],
            max_tokens=250,
            temperature=0.3,
            timeout=12.0,
        )

        suggestion = response.choices[0].message.content.strip()
        recommended_action = _detect_recommended_action(customer_message, escalation_reason)

        logger.info("agent_assist.generated", dialect=dialect, action=recommended_action)

        return {
            "suggestion": suggestion,
            "recommended_action": recommended_action,
            "confidence": 0.85,
        }

    except Exception as e:
        logger.error("agent_assist.failed", error=str(e))
        return {
            "suggestion": "",
            "recommended_action": "manual",
            "confidence": 0.0,
            "error": str(e),
        }


def _detect_recommended_action(message: str, reason: str) -> str:
    """Suggest what action the agent should take."""
    msg_lower = message.lower()
    reason_lower = (reason or "").lower()

    if any(w in msg_lower for w in ["أرجع", "استرجاع", "إرجاع", "ارجع"]):
        return "initiate_return"
    if any(w in msg_lower for w in ["ألغي", "الغاء", "إلغاء"]):
        return "cancel_order"
    if any(w in msg_lower for w in ["تتبع", "وين طلبي", "وصل", "شحن"]):
        return "track_shipment"
    if any(w in msg_lower for w in ["مشكلة", "عيب", "تالف", "مكسور"]):
        return "handle_complaint"
    if "vip" in reason_lower or "at_risk" in reason_lower:
        return "priority_response"
    return "respond"


def build_escalation_context_package(
    customer,
    conversation,
    recent_messages: list[dict],
    pipeline_result,
    suggestion: dict | None = None,
) -> dict:
    """
    Build the full context package sent to the agent at escalation.
    Enhanced with Agent Assist suggestion.
    """
    pkg = {
        "customer": {
            "tier": customer.customer_tier,
            "total_conversations": customer.total_conversations,
            "total_escalations": customer.total_escalations,
            "avg_sentiment": float(customer.avg_sentiment or 0.5),
            "salla_orders": customer.salla_total_orders,
            "salla_revenue": float(customer.salla_total_revenue or 0),
        },
        "conversation": {
            "intent": conversation.intent,
            "dialect": conversation.dialect,
            "stage": getattr(conversation, "stage", "unknown"),
            "ai_persona": getattr(conversation, "ai_persona", None),
            "message_count": conversation.message_count,
        },
        "ai_summary": {
            "confidence": pipeline_result.confidence,
            "resolution_type": pipeline_result.resolution_type,
            "rag_draft": pipeline_result.rag_draft,
            "confidence_breakdown": pipeline_result.confidence_breakdown,
        },
        "recent_messages": recent_messages[-5:] if recent_messages else [],
        "agent_assist": suggestion or {},
    }
    return pkg
