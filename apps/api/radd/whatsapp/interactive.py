from __future__ import annotations
"""
WhatsApp Interactive Messages — Buttons, Lists, Product Cards.
Builds structured WhatsApp Cloud API payloads for rich messages.
"""
import httpx
import structlog

logger = structlog.get_logger()

WA_API_BASE = "https://graph.facebook.com/v20.0"


# ─── Message builders ────────────────────────────────────────────────────────

def build_button_message(
    body_text: str,
    buttons: list[dict],  # [{"id": "...", "title": "..."}, ...]
    header_text: str | None = None,
    footer_text: str | None = None,
) -> dict:
    """Build a WhatsApp interactive button message (max 3 buttons)."""
    buttons = buttons[:3]  # WA limit

    payload = {
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
                    for b in buttons
                ]
            },
        },
    }

    if header_text:
        payload["interactive"]["header"] = {"type": "text", "text": header_text}
    if footer_text:
        payload["interactive"]["footer"] = {"text": footer_text}

    return payload


def build_list_message(
    body_text: str,
    button_label: str,
    sections: list[dict],  # [{"title": "...", "rows": [{"id": "...", "title": "...", "description": "..."}]}]
    header_text: str | None = None,
) -> dict:
    """Build a WhatsApp interactive list message."""
    payload = {
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button": button_label[:20],
                "sections": sections,
            },
        },
    }
    if header_text:
        payload["interactive"]["header"] = {"type": "text", "text": header_text}

    return payload


def build_product_card(
    product_name: str,
    price: str,
    description: str,
    catalog_id: str | None = None,
    product_retailer_id: str | None = None,
    image_url: str | None = None,
) -> dict:
    """
    Build a product card message.
    If catalog_id provided → use native WA catalog.
    Otherwise → use text + image.
    """
    if catalog_id and product_retailer_id:
        return {
            "type": "interactive",
            "interactive": {
                "type": "product",
                "action": {
                    "catalog_id": catalog_id,
                    "product_retailer_id": product_retailer_id,
                },
            },
        }

    # Fallback: text card with button
    body = f"*{product_name}*\n{price}\n\n{description}"
    return build_button_message(
        body_text=body,
        buttons=[
            {"id": f"order_{product_retailer_id or 'now'}", "title": "اطلب الآن 🛒"},
            {"id": "more_details", "title": "تفاصيل أكثر 📋"},
        ],
    )


def build_return_prevention_message(
    reason: str,
    dialect: str = "gulf",
    product_name: str = "",
) -> dict:
    """Build interactive message for return prevention with options."""
    if dialect == "gulf":
        body = f"آسف تحس كذا{' بخصوص ' + product_name if product_name else ''}! عندي لك خيارين:"
    elif dialect == "egyptian":
        body = f"آسف على الإزعاج{' بخصوص ' + product_name if product_name else ''}! عندي خيارين:"
    else:
        body = f"آسف لذلك! يمكنني مساعدتك بأحد خيارين:"

    buttons = []
    if reason in ("wrong_size", "size_issue"):
        buttons = [
            {"id": "exchange_size", "title": "تبديل المقاس ♻️"},
            {"id": "full_refund", "title": "استرداد كامل 💰"},
        ]
    elif reason == "wrong_item":
        buttons = [
            {"id": "send_correct", "title": "أرسل الصحيح 🚚"},
            {"id": "full_refund", "title": "استرداد كامل 💰"},
        ]
    elif reason == "damaged":
        buttons = [
            {"id": "send_replacement", "title": "إرسال بديل 📦"},
            {"id": "partial_refund", "title": "استرداد جزئي 💸"},
            {"id": "full_refund", "title": "استرداد كامل 💰"},
        ]
    else:
        buttons = [
            {"id": "discount_keep", "title": "خصم 15% واحتفظ 🎁"},
            {"id": "full_refund", "title": "استرداد كامل 💰"},
        ]

    return build_button_message(body_text=body, buttons=buttons)


def build_products_list_message(
    products: list[dict],
    dialect: str = "gulf",
) -> dict:
    """Build a list message showing multiple products."""
    if dialect == "gulf":
        header = "منتجاتنا المتاحة"
        body = "اختر المنتج اللي يهمك وأحطيك تفاصيل أكثر:"
        button = "شوف المنتجات"
    elif dialect == "egyptian":
        header = "منتجاتنا المتاحة"
        body = "اختار المنتج اللي يهمك:"
        button = "شوف المنتجات"
    else:
        header = "المنتجات المتاحة"
        body = "اختر المنتج لمزيد من التفاصيل:"
        button = "عرض المنتجات"

    rows = [
        {
            "id": f"product_{p.get('id', i)}",
            "title": p.get("name", "")[:24],
            "description": f"{p.get('price', '')} ر.س — {p.get('description', '')[:60]}",
        }
        for i, p in enumerate(products[:10])
    ]

    return build_list_message(
        body_text=body,
        button_label=button,
        sections=[{"title": header, "rows": rows}],
        header_text=header,
    )


# ─── Sender ───────────────────────────────────────────────────────────────────

async def send_interactive_message(
    phone_number: str,
    message_payload: dict,
    phone_number_id: str,
    api_token: str,
) -> bool:
    """Send a WhatsApp interactive message."""
    url = f"{WA_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        **message_payload,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            logger.info("whatsapp.interactive_sent", phone=phone_number[:6] + "***")
            return True
        except Exception as e:
            logger.error("whatsapp.interactive_failed", error=str(e))
            return False


async def send_text_with_buttons(
    phone_number: str,
    text: str,
    buttons: list[dict],
    phone_number_id: str,
    api_token: str,
    header: str | None = None,
) -> bool:
    """Convenience: send text message with action buttons."""
    payload = build_button_message(body_text=text, buttons=buttons, header_text=header)
    return await send_interactive_message(phone_number, payload, phone_number_id, api_token)
