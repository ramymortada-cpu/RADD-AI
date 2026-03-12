"""
WhatsApp webhook handler.
GET: Meta verification challenge.
POST: Inbound message receiver.
"""
import hashlib
import hmac
import json
import uuid

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from radd.limiter import limiter
from sqlalchemy import select

from radd.config import settings
from radd.db.models import Channel
from radd.db.session import get_db_session
from radd.deps import get_redis
from radd.pipeline.templates import UNSUPPORTED_MEDIA_MESSAGE

logger = structlog.get_logger()
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

DEDUP_TTL_SECONDS = 300  # 5 minutes


# ── Verification ──────────────────────────────────────────────────────────────

@router.get("/whatsapp")
@limiter.limit(settings.auth_rate_limit)
async def verify_webhook(request: Request):
    """Meta webhook verification challenge."""
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.meta_verify_token:
        logger.info("whatsapp.webhook_verified")
        return Response(content=challenge, media_type="text/plain")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


# ── Inbound message handler ───────────────────────────────────────────────────

@router.post("/whatsapp", status_code=status.HTTP_200_OK)
@limiter.limit(settings.default_rate_limit)
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """
    Receive inbound WhatsApp message.
    1. Verify HMAC-SHA256 signature.
    2. Parse message.
    3. Deduplicate via Redis.
    4. ACK 200 immediately.
    5. Enqueue to Redis Stream for async processing.
    """
    body_bytes = await request.body()

    # ── HMAC verification ────────────────────────────────────────────────────
    if settings.meta_app_secret:
        signature_header = request.headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(
            settings.meta_app_secret.encode(),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature_header, expected):
            logger.warning("whatsapp.hmac_failure")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    # Enqueue parsed messages in background (ACK first)
    background_tasks.add_task(_process_webhook_payload, payload)
    return {"status": "ok"}


async def _process_webhook_payload(payload: dict) -> None:
    """Parse WhatsApp webhook payload and enqueue each message to Redis Stream."""
    r = get_redis()

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id", "")

            for msg in messages:
                msg_id = msg.get("id", "")
                msg_type = msg.get("type", "")
                sender_phone = msg.get("from", "")

                # Deduplicate
                dedup_key = f"dedup:wa:{msg_id}"
                already_seen = await r.set(dedup_key, "1", nx=True, ex=DEDUP_TTL_SECONDS)
                if not already_seen:
                    logger.info("whatsapp.duplicate_skipped", message_id=msg_id)
                    continue

                # Handle image messages — enqueue for Vision processing
                if msg_type == "image":
                    image_data = msg.get("image", {})
                    media_id = image_data.get("id", "")
                    caption = image_data.get("caption", "")
                    if media_id:
                        workspace_id = await _resolve_workspace(phone_number_id)
                        if workspace_id:
                            stream_key = f"messages:{workspace_id}"
                            await r.xadd(stream_key, {
                                "message_id": msg_id,
                                "sender_phone": sender_phone,
                                "text": caption or "[صورة]",
                                "phone_number_id": phone_number_id,
                                "workspace_id": str(workspace_id),
                                "timestamp": msg.get("timestamp", ""),
                                "message_type": "image",
                                "media_id": media_id,
                            })
                            logger.info("whatsapp.image_enqueued", workspace_id=str(workspace_id))
                    continue

                # Non-text (non-image): skip with log
                if msg_type != "text":
                    logger.info("whatsapp.non_text_skipped", type=msg_type)
                    continue

                text_body = msg.get("text", {}).get("body", "")
                if not text_body:
                    continue

                # Resolve workspace by phone_number_id → channel lookup
                workspace_id = await _resolve_workspace(phone_number_id)
                if not workspace_id:
                    logger.warning("whatsapp.unknown_phone_number_id", pid=phone_number_id)
                    continue

                stream_key = f"messages:{workspace_id}"
                await r.xadd(stream_key, {
                    "message_id": msg_id,
                    "sender_phone": sender_phone,
                    "text": text_body,
                    "phone_number_id": phone_number_id,
                    "workspace_id": str(workspace_id),
                    "timestamp": msg.get("timestamp", ""),
                })
                logger.info(
                    "whatsapp.message_enqueued",
                    workspace_id=str(workspace_id),
                    message_id=msg_id,
                )


async def _resolve_workspace(phone_number_id: str) -> uuid.UUID | None:
    """Resolve workspace_id from WhatsApp phone_number_id via channel config."""
    if not phone_number_id:
        return None

    # Use unscoped session for cross-workspace channel lookup
    async with get_db_session() as db:
        result = await db.execute(
            select(Channel).where(
                Channel.type == "whatsapp",
                Channel.is_active.is_(True),
            )
        )
        channels = result.scalars().all()

    for channel in channels:
        config = channel.config or {}
        if config.get("wa_phone_number_id") == phone_number_id:
            return channel.workspace_id

    return None
