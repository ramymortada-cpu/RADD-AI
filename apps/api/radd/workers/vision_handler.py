"""Image message processing — extracted from message_worker."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from radd.config import settings
from radd.db.models import Channel, Message
from radd.db.session import get_db_session
from radd.pipeline.dialect import detect_dialect
from radd.utils.crypto import get_channel_config_decrypted
from radd.whatsapp.client import send_text_message

import structlog
logger = structlog.get_logger()


async def process_image_message(
    workspace_id: uuid.UUID,
    sender_phone: str,
    external_id: str,
    media_id: str,
    caption: str,
    get_or_create_customer,
    get_or_create_conversation,
) -> None:
    """Process image via Vision API, store messages, send response."""
    async with get_db_session(workspace_id) as db:
        result = await db.execute(
            select(Channel).where(Channel.workspace_id == workspace_id, Channel.type == "whatsapp")
        )
        channel = result.scalar_one_or_none()
        if not channel:
            return

        channel_config = get_channel_config_decrypted(channel)
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

        customer = await get_or_create_customer(db, workspace_id, sender_phone)
        conversation = await get_or_create_conversation(db, workspace_id, customer, channel.id)

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
