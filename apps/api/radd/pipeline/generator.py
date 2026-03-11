from __future__ import annotations
"""
RAG generator — GPT-4.1-mini with grounded Arabic generation.
Injects source passages + conversation history into prompt.
Generates dialect-aware, KB-grounded Arabic response.
"""
import structlog
from openai import AsyncOpenAI

from radd.config import settings
from radd.pipeline.retriever import RetrievedPassage

logger = structlog.get_logger()

MAX_HISTORY_MESSAGES = 3
MAX_PASSAGE_CHARS = 800    # Truncate individual passages
MAX_TOTAL_PASSAGE_CHARS = 3000


SYSTEM_PROMPT_TEMPLATE = """أنت مساعد خدمة عملاء محترف لمتجر إلكتروني سعودي.

قواعد صارمة:
١. أجب فقط من المقاطع المرجعية المقدمة. لا تخترع معلومات.
٢. إذا لم تجد الإجابة في المقاطع، قل بوضوح: "هذه المعلومات غير متوفرة لديّ الآن، سأحولك لفريق الدعم."
٣. استخدم لهجة {dialect} العربية. كن واضحاً ومفيداً وموجزاً.
٤. لا تذكر أنك AI أو روبوت. تصرف كموظف دعم بشري.
٥. أجب بالعربية فقط. لا تخلط مع الإنجليزية إلا للأرقام والمصطلحات التقنية.
٦. إذا سأل العميل عن رقم طلب محدد ولا يوجد في المقاطع، اطلب منه التأكيد أو أحله للدعم.

المتجر: {store_name}"""

DIALECT_NAMES = {
    "gulf": "الخليجية",
    "egyptian": "المصرية",
    "msa": "الفصحى",
}


def _format_passages(passages: list[RetrievedPassage]) -> str:
    """Format retrieved passages for prompt injection."""
    formatted = []
    total_chars = 0

    for i, p in enumerate(passages, 1):
        passage_text = p.content[:MAX_PASSAGE_CHARS]
        if total_chars + len(passage_text) > MAX_TOTAL_PASSAGE_CHARS:
            break
        formatted.append(f"[مقطع {i}]\n{passage_text}")
        total_chars += len(passage_text)

    return "\n\n".join(formatted)


def _format_history(history: list[dict]) -> list[dict]:
    """Format conversation history for GPT messages."""
    messages = []
    for msg in history[-MAX_HISTORY_MESSAGES:]:
        role = "user" if msg.get("sender_type") == "customer" else "assistant"
        messages.append({"role": role, "content": msg.get("content", "")})
    return messages


async def generate_rag_response(
    query: str,
    passages: list[RetrievedPassage],
    dialect: str,
    store_name: str = "متجرنا",
    conversation_history: list[dict] | None = None,
) -> tuple[str, list[str]]:
    """
    Generate a grounded Arabic response using GPT-4.1-mini.
    Returns (response_text, cited_chunk_ids).
    """
    if not passages:
        return "عذراً، لم أجد معلومات كافية للإجابة. سأحولك لفريق الدعم.", []

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    dialect_name = DIALECT_NAMES.get(dialect, "الفصحى")

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        dialect=dialect_name,
        store_name=store_name,
    )

    passages_text = _format_passages(passages)
    history_messages = _format_history(conversation_history or [])

    user_message = f"""المقاطع المرجعية:
{passages_text}

---
سؤال العميل: {query}"""

    messages = (
        [{"role": "system", "content": system_prompt}]
        + history_messages
        + [{"role": "user", "content": user_message}]
    )

    try:
        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=messages,
            temperature=0.2,       # Low temperature for factual CS responses
            max_tokens=400,
            timeout=15.0,
        )
        response_text = response.choices[0].message.content.strip()
        cited_ids = [p.chunk_id for p in passages]

        logger.info(
            "generator.complete",
            tokens_used=response.usage.total_tokens,
            dialect=dialect,
            passages=len(passages),
        )
        return response_text, cited_ids

    except Exception as e:
        logger.error("generator.failed", error=str(e))
        return "عذراً، حدث خطأ أثناء معالجة طلبك. سأحولك لفريق الدعم.", []
