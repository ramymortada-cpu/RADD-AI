"""
WhatsApp Cloud API client.
Handles: send text message, mark as read.
"""
import httpx
import structlog

from radd.config import settings

logger = structlog.get_logger()


async def send_text_message(
    phone_number: str,
    message: str,
    phone_number_id: str | None = None,
    api_token: str | None = None,
) -> dict:
    """Send a text message via WhatsApp Cloud API."""
    pid = phone_number_id or settings.wa_phone_number_id
    token = api_token or settings.wa_api_token

    url = f"{settings.wa_api_base_url}/{pid}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "text",
        "text": {"preview_url": False, "body": message},
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        logger.info("whatsapp.message_sent", to=phone_number, message_id=data.get("messages", [{}])[0].get("id"))
        return data


async def mark_as_read(message_id: str, phone_number_id: str | None = None, api_token: str | None = None) -> dict:
    """Mark an inbound WhatsApp message as read."""
    pid = phone_number_id or settings.wa_phone_number_id
    token = api_token or settings.wa_api_token

    url = f"{settings.wa_api_base_url}/{pid}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        return response.json()
