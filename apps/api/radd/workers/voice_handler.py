"""Voice message processing — extracted from message_worker."""
from __future__ import annotations
import uuid

import structlog
from sqlalchemy import select

from radd.config import settings
from radd.db.models import Channel, Message
from radd.db.session import get_db_session
from radd.utils.crypto import get_channel_config_decrypted
from radd.whatsapp.client import send_text_message

logger = structlog.get_logger()


async def process_voice_message(
    workspace_id: uuid.UUID,
    sender_phone: str,
    external_id: str,
    media_id: str,
    get_or_create_customer,
    get_or_create_conversation,
) -> None:
    """Transcribe voice via Whisper, then route through text pipeline or send fallback."""
    async with get_db_session(workspace_id) as db:
        result = await db.execute(
            select(Channel).where(Channel.workspace_id == workspace_id, Channel.type == "whatsapp")
        )
        channel = result.scalar_one_or_none()
        if not channel:
            return

        channel_config = get_channel_config_decrypted(channel)
        wa_token = channel_config.get("wa_api_token") or settings.wa_api_token

        from radd.voice.transcriber import process_whatsapp_voice, build_voice_fallback_response
        transcription = await process_whatsapp_voice(media_id=media_id, wa_token=wa_token)

        if not transcription.get("success") or not transcription.get("text"):
            customer = await get_or_create_customer(db, workspace_id, sender_phone)
            conversation = await get_or_create_conversation(db, workspace_id, customer, channel.id)
            fallback_text = build_voice_fallback_response("gulf")

            inbound = Message(
                workspace_id=workspace_id, conversation_id=conversation.id,
                sender_type="customer", content="[رسالة صوتية]", external_id=external_id,
                message_type="voice",
            )
            db.add(inbound)
            outbound = Message(
                workspace_id=workspace_id, conversation_id=conversation.id,
                sender_type="system", content=fallback_text, message_type="text",
            )
            db.add(outbound)
            await db.flush()

            if not settings.shadow_mode:
                try:
                    await send_text_message(
                        phone_number=sender_phone, message=fallback_text,
                        phone_number_id=channel_config.get("wa_phone_number_id") or settings.wa_phone_number_id,
                        api_token=wa_token,
                    )
                except Exception as e:
                    logger.error("worker.voice_fallback_send_failed", error=str(e))
            return

    transcribed_text = transcription["text"]
    logger.info("voice.transcription_success", text_preview=transcribed_text[:60])
    return transcribed_text
