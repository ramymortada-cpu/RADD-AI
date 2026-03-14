"""
RADD AI — CSAT Collection
===========================
نظام جمع تقييمات رضا العملاء تلقائياً.

الملف: apps/api/radd/conversations/csat.py
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("radd.conversations.csat")


# ---------------------------------------------------------------------------
# CSAT Message Templates
# ---------------------------------------------------------------------------

CSAT_TEMPLATES = {
    "gulf": {
        "prompt": "شكراً لتواصلك معنا! 🙏\nكيف تقيّم تجربتك اليوم؟\n\n⭐ 1 — سيئة\n⭐⭐ 2 — مقبولة\n⭐⭐⭐ 3 — جيدة\n⭐⭐⭐⭐ 4 — ممتازة\n⭐⭐⭐⭐⭐ 5 — رائعة\n\nرد برقم من 1 إلى 5",
        "thanks": "شكراً جزيلاً على تقييمك! نسعد بخدمتك دائماً 😊",
        "low_score": "نعتذر عن أي إزعاج. سنعمل على تحسين خدمتنا. شكراً لملاحظتك 🙏",
    },
    "egyptian": {
        "prompt": "شكراً إنك تواصلت معانا! 🙏\nإزاي تقيّم تجربتك النهاردة؟\n\n⭐ 1 — وحشة\n⭐⭐ 2 — مقبولة\n⭐⭐⭐ 3 — كويسة\n⭐⭐⭐⭐ 4 — ممتازة\n⭐⭐⭐⭐⭐ 5 — عظيمة\n\nرد برقم من 1 لـ 5",
        "thanks": "شكراً أوي على تقييمك! بنتمنى نخدمك دايماً 😊",
        "low_score": "بنعتذر عن أي حاجة ضايقتك. هنحسّن خدمتنا. شكراً لملاحظتك 🙏",
    },
    "msa": {
        "prompt": "شكراً لتواصلك معنا! 🙏\nكيف تقيّم تجربتك اليوم؟\n\n⭐ 1 — سيئة\n⭐⭐ 2 — مقبولة\n⭐⭐⭐ 3 — جيدة\n⭐⭐⭐⭐ 4 — ممتازة\n⭐⭐⭐⭐⭐ 5 — رائعة\n\nالرجاء الرد برقم من 1 إلى 5",
        "thanks": "شكراً جزيلاً على تقييمك! نسعد بخدمتكم دائماً 😊",
        "low_score": "نعتذر عن أي إزعاج. سنعمل على تحسين خدمتنا. شكراً لملاحظتكم 🙏",
    },
}


async def send_csat_request(
    whatsapp_client,
    customer_phone: str,
    conversation_id: str,
    dialect: str = "gulf",
    delay_seconds: int = 30,
):
    """
    يرسل طلب تقييم CSAT بعد إغلاق المحادثة.

    Args:
        whatsapp_client: WhatsApp API client
        customer_phone: رقم هاتف العميل
        conversation_id: معرف المحادثة
        dialect: لهجة العميل
        delay_seconds: التأخير قبل الإرسال (30 ثانية افتراضياً)
    """
    import asyncio
    await asyncio.sleep(delay_seconds)

    template = CSAT_TEMPLATES.get(dialect, CSAT_TEMPLATES["msa"])

    try:
        await whatsapp_client.send_message(
            to=customer_phone,
            text=template["prompt"],
            metadata={"type": "csat_request", "conversation_id": conversation_id},
        )
        logger.info("csat.request_sent", conversation_id=conversation_id)
    except Exception as e:
        logger.warning("csat.send_failed", error=str(e), conversation_id=conversation_id)


def parse_csat_response(text: str) -> Optional[int]:
    """
    يحلل رد العميل ويستخرج التقييم.

    يفهم: "5", "⭐⭐⭐⭐⭐", "5 نجوم", "ممتاز", "رائع", إلخ
    """
    text = text.strip()

    # رقم مباشر
    if text in ("1", "2", "3", "4", "5"):
        return int(text)

    # عد النجوم
    stars = text.count("⭐")
    if 1 <= stars <= 5:
        return stars

    # كلمات مفتاحية
    positive_words = {"ممتاز", "رائع", "عظيم", "excellent", "great", "amazing", "5"}
    good_words = {"جيد", "كويس", "حلو", "good", "nice", "4"}
    ok_words = {"مقبول", "عادي", "okay", "ok", "3"}
    bad_words = {"سيء", "وحش", "bad", "poor", "1", "2"}

    text_lower = text.lower()
    for word in positive_words:
        if word in text_lower:
            return 5
    for word in good_words:
        if word in text_lower:
            return 4
    for word in ok_words:
        if word in text_lower:
            return 3
    for word in bad_words:
        if word in text_lower:
            return 1

    return None


async def handle_csat_response(
    db_session,
    conversation_id: str,
    rating: int,
    workspace_id: str,
):
    """يخزن تقييم CSAT في قاعدة البيانات."""
    from sqlalchemy import text

    try:
        await db_session.execute(
            text("""
                UPDATE conversations
                SET metadata = jsonb_set(
                    COALESCE(metadata, '{}'),
                    '{csat}',
                    to_jsonb(:rating::int)
                )
                WHERE id = :conversation_id
                AND workspace_id = :workspace_id
            """),
            {
                "conversation_id": conversation_id,
                "rating": rating,
                "workspace_id": workspace_id,
            },
        )
        await db_session.commit()
        logger.info("csat.stored", conversation_id=conversation_id, rating=rating)
    except Exception as e:
        logger.error("csat.store_failed", error=str(e))
