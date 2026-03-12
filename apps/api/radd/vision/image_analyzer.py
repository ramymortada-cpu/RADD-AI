from __future__ import annotations
"""
RADD AI — Image Understanding
Analyzes customer-sent images using OpenAI Vision (GPT-4o).
Use cases:
- Damaged product photo → support response
- Product asking for identification → sales response
- Shipping label → order tracking help
"""
import base64
import structlog
from openai import AsyncOpenAI

from radd.config import settings

logger = structlog.get_logger()


VISION_SYSTEM_PROMPT = """أنت مساعد خدمة عملاء لمتجر إلكتروني سعودي.
يرسل لك العميل صورة. حلّل الصورة وأجب بالعربية.

قواعد:
١. إذا الصورة لمنتج تالف أو به عيب → أبدِ تعاطفك وطلب مساعدة للإرجاع أو الاستبدال.
٢. إذا الصورة لمنتج للاستفسار عنه → حاول تحديد المنتج وقدم معلومات مفيدة.
٣. إذا الصورة لملصق شحن أو وصل → استخرج رقم التتبع إذا ظهر.
٤. إذا لم تتمكن من تحديد محتوى الصورة → اطلب توضيحاً.
٥. لا تخترع معلومات عن المنتج إذا لم تكن متأكداً.
٦. أجب بلهجة {dialect}.
٧. المتجر: {store_name}"""


async def analyze_image(
    image_url: str | None = None,
    image_base64: str | None = None,
    dialect: str = "gulf",
    store_name: str = "متجرنا",
    customer_text: str = "",
) -> dict:
    """
    Analyze a customer-sent image using GPT-4o vision.
    Accepts either a URL or base64-encoded image.
    Returns analysis dict with response_text and image_type.
    """
    if not image_url and not image_base64:
        return {
            "success": False,
            "error": "no_image",
            "response_text": "لم أتمكن من معالجة الصورة. هل يمكنك إرسالها مرة أخرى؟",
        }

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    dialect_display = {"gulf": "خليجية", "egyptian": "مصرية", "msa": "فصحى"}.get(dialect, "خليجية")
    system_prompt = VISION_SYSTEM_PROMPT.format(dialect=dialect_display, store_name=store_name)

    # Build image content
    if image_url:
        image_content = {"type": "image_url", "image_url": {"url": image_url, "detail": "auto"}}
    else:
        image_content = {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}", "detail": "auto"},
        }

    user_content = []
    if customer_text:
        user_content.append({"type": "text", "text": f"رسالة العميل مع الصورة: {customer_text}"})
    else:
        user_content.append({"type": "text", "text": "ما رأيك في هذه الصورة؟ ساعدني."})
    user_content.append(image_content)

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_tokens=400,
            timeout=20.0,
        )

        response_text = response.choices[0].message.content.strip()
        image_type = _classify_image_type(response_text)

        logger.info(
            "vision.analyzed",
            image_type=image_type,
            dialect=dialect,
            tokens=response.usage.total_tokens,
        )

        return {
            "success": True,
            "response_text": response_text,
            "image_type": image_type,
        }

    except Exception as e:
        logger.error("vision.failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "response_text": "تعذّر تحليل الصورة. سأحولك لفريق الدعم لمساعدتك.",
        }


def _classify_image_type(response_text: str) -> str:
    """Classify the type of image based on the AI response."""
    text_lower = response_text.lower()
    if any(w in text_lower for w in ["تالف", "عيب", "مكسور", "خراب", "مشكلة"]):
        return "damaged_product"
    if any(w in text_lower for w in ["تتبع", "شحن", "tracking", "وصل"]):
        return "shipping_label"
    if any(w in text_lower for w in ["منتج", "سعر", "توفر", "مواصفات"]):
        return "product_inquiry"
    return "general"


async def process_whatsapp_image(
    media_id: str,
    wa_token: str,
    dialect: str = "gulf",
    store_name: str = "متجرنا",
    customer_text: str = "",
) -> dict:
    """
    Download a WhatsApp media file and analyze it.
    WhatsApp uses media_id → download URL flow.
    """
    import httpx

    headers = {"Authorization": f"Bearer {wa_token}"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            # Step 1: Get media URL
            media_resp = await client.get(
                f"https://graph.facebook.com/v20.0/{media_id}",
                headers=headers,
            )
            media_resp.raise_for_status()
            media_url = media_resp.json().get("url", "")

            if not media_url:
                return {
                    "success": False,
                    "response_text": "تعذّر تحميل الصورة.",
                }

            # Step 2: Download image
            img_resp = await client.get(media_url, headers=headers)
            img_resp.raise_for_status()
            image_b64 = base64.b64encode(img_resp.content).decode("utf-8")

            # Step 3: Analyze
            return await analyze_image(
                image_base64=image_b64,
                dialect=dialect,
                store_name=store_name,
                customer_text=customer_text,
            )

        except Exception as e:
            logger.error("vision.whatsapp_download_failed", error=str(e))
            return {
                "success": False,
                "response_text": "تعذّر معالجة الصورة. هل يمكنك وصف المشكلة بالكلمات؟",
            }
