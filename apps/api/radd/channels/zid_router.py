from __future__ import annotations

"""Zid Order Webhook Router."""
import json

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from radd.config import settings
from radd.limiter import limiter
from radd.webhooks.zid_verify import verify_zid_signature

logger = structlog.get_logger()
router = APIRouter(prefix="/webhooks/zid", tags=["zid"])


@router.post("", status_code=status.HTTP_200_OK)
@limiter.limit(settings.default_rate_limit)
async def receive_zid_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_zid_signature: str | None = Header(default=None, alias="X-Zid-Signature"),
):
    """Receive Zid order webhooks for revenue attribution with HMAC-SHA256 verification."""
    body_bytes = await request.body()

    # 1. التحقق من التوقيع — رفض فوري إذا فشل
    is_valid = verify_zid_signature(
        payload=body_bytes,
        signature_header=x_zid_signature,
        secret=settings.zid_webhook_secret,
    )

    if not is_valid:
        logger.warning(
            "zid_webhook_rejected",
            reason="invalid_signature",
            ip=request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=403,
            detail="Invalid Zid webhook signature",
        )

    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = payload.get("event", payload.get("type", ""))
    if not event_type:
        return {"status": "ok"}

    background_tasks.add_task(_process_zid_webhook, event_type, payload)
    return {"status": "ok"}


async def _process_zid_webhook(event_type: str, payload: dict) -> None:
    from sqlalchemy import select

    from radd.db.models import Channel
    from radd.db.session import get_db_session

    # Find workspace by Zid store_id in channel config
    order_data = payload.get("order", payload.get("data", {}))
    store_id = str(payload.get("store_id", payload.get("merchant_id", "")))

    async with get_db_session() as db:
        result = await db.execute(
            select(Channel).where(
                Channel.type == "zid",
                Channel.is_active.is_(True),
            )
        )
        channels = result.scalars().all()
        workspace_id = None
        for ch in channels:
            cfg = ch.config or {}
            if cfg.get("store_id") == store_id or not store_id:
                workspace_id = str(ch.workspace_id)
                break

    if not workspace_id:
        logger.warning("zid.webhook_unknown_store", store_id=store_id)
        return

    async with get_db_session() as db:
        from radd.onboarding.zid_sync import handle_zid_order_webhook
        await handle_zid_order_webhook(event_type, order_data, workspace_id, db)
