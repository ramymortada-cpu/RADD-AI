"""
Twilio Webhooks — Call status updates and DTMF gather responses.

Endpoints:
- POST /api/v1/webhooks/twilio/call-status   — Call completed/failed/no-answer
- POST /api/v1/webhooks/twilio/gather         — Customer pressed a digit (DTMF)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Request
from fastapi.responses import Response
from sqlalchemy import select

from radd.config import settings
from radd.db.models import OutboundCall
from radd.db.session import get_db_session
from radd.voice.outbound_poc import generate_gather_response_twiml

logger = logging.getLogger("radd.webhooks.twilio")

router = APIRouter(prefix="/webhooks/twilio", tags=["twilio-webhooks"])

# Redis key prefix for call_sid -> workspace_id lookup (set by worker when call is created)
CALL_SID_PREFIX = "cod_shield_call_sid:"
CALL_SID_TTL = 86400  # 24 hours


async def _get_workspace_id_for_call_sid(call_sid: str) -> str | None:
    """Look up workspace_id from Redis (stored by worker when call is created)."""
    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        ws_id = await r.get(f"{CALL_SID_PREFIX}{call_sid}")
        await r.aclose()
        return ws_id
    except Exception as e:
        logger.error("Failed to lookup workspace for call_sid %s: %s", call_sid, e)
        return None


# ─── Call Status Webhook ───


@router.post("/call-status")
async def twilio_call_status(request: Request):
    """
    Receives call status updates from Twilio.

    Twilio sends form-encoded data with fields:
    - CallSid: unique call identifier
    - CallStatus: completed | busy | no-answer | failed | canceled
    - To: destination phone number
    """
    form = await request.form()
    call_sid = form.get("CallSid", "")
    call_status = form.get("CallStatus", "")
    to_number = form.get("To", "")

    logger.info("Twilio call status: SID=%s, status=%s, to=%s", call_sid, call_status, to_number)

    if not call_sid:
        return Response(status_code=200)

    # Map Twilio status to our status
    status_map = {
        "completed": None,  # Don't override — gather handler sets confirmed/cancelled
        "busy": "no_answer",
        "no-answer": "no_answer",
        "failed": "failed",
        "canceled": "failed",
    }

    new_status = status_map.get(call_status)

    if new_status is None and call_status == "completed":
        # Call was answered — gather handler will update status
        logger.info("Call %s completed — waiting for gather response", call_sid)
        return Response(status_code=200)

    if new_status:
        # Call failed — update DB and schedule next channel
        workspace_id_str = await _get_workspace_id_for_call_sid(call_sid)
        if not workspace_id_str:
            logger.warning("No workspace_id for call_sid %s — cannot update", call_sid)
            return Response(status_code=200)

        try:
            from uuid import UUID

            workspace_id = UUID(workspace_id_str)
        except (ValueError, TypeError):
            logger.error("Invalid workspace_id for call_sid %s", call_sid)
            return Response(status_code=200)

        try:
            async with get_db_session(workspace_id) as db:
                stmt = select(OutboundCall).where(
                    OutboundCall.call_sid == call_sid,
                    OutboundCall.workspace_id == workspace_id,
                )
                result = await db.execute(stmt)
                call_record = result.scalar_one_or_none()

                if call_record:
                    call_record.status = new_status
                    call_record.updated_at = datetime.now(timezone.utc)

                    # Check if we should retry or move to next channel
                    if call_record.attempt_count < call_record.max_attempts:
                        # Retry call — re-queue
                        call_record.attempt_count += 1
                        await db.flush()

                        # Re-queue for another call attempt
                        await _requeue_call(call_record)
                        logger.info(
                            "Call %s failed — re-queued (attempt %s)",
                            call_sid,
                            call_record.attempt_count,
                        )
                    else:
                        # Max attempts reached — fallback to WhatsApp
                        call_record.next_channel = "whatsapp"
                        await db.flush()

                        # Schedule WhatsApp fallback after 15 minutes
                        await _schedule_whatsapp_fallback(call_record)
                        logger.info("Call %s max attempts reached — WhatsApp fallback scheduled", call_sid)
                else:
                    logger.warning("No call record found for SID %s", call_sid)
        except Exception as e:
            logger.error("Error updating call status for %s: %s", call_sid, e)

    return Response(status_code=200)


# ─── Gather Webhook (DTMF Response) ───


@router.post("/gather")
async def twilio_gather(request: Request):
    """
    Receives DTMF input from customer during a call.

    Digits:
    - 1: Confirm order
    - 2: Cancel order → trigger Save the Sale
    """
    form = await request.form()
    digits = form.get("Digits", "")
    call_sid = form.get("CallSid", "")

    logger.info("Twilio gather: SID=%s, digits=%s", call_sid, digits)

    # Update call record
    if call_sid:
        workspace_id_str = await _get_workspace_id_for_call_sid(call_sid)
        if workspace_id_str:
            try:
                from uuid import UUID

                workspace_id = UUID(workspace_id_str)
            except (ValueError, TypeError):
                workspace_id = None
        else:
            workspace_id = None

        if workspace_id:
            try:
                async with get_db_session(workspace_id) as db:
                    stmt = select(OutboundCall).where(
                        OutboundCall.call_sid == call_sid,
                        OutboundCall.workspace_id == workspace_id,
                    )
                    result = await db.execute(stmt)
                    call_record = result.scalar_one_or_none()

                    if call_record:
                        call_record.customer_response = digits
                        call_record.responded_at = datetime.now(timezone.utc)

                        if digits == "1":
                            call_record.status = "confirmed"
                        elif digits == "2":
                            call_record.status = "cancelled"
                            await _schedule_save_the_sale(call_record)
                        else:
                            call_record.status = "calling"  # Unknown digit — retry gather

                        await db.flush()
                        logger.info("Call %s: customer pressed %s → %s", call_sid, digits, call_record.status)
            except Exception as e:
                logger.error("Error updating gather response for %s: %s", call_sid, e)

    # Return TwiML response
    twiml = generate_gather_response_twiml(digits)
    return Response(content=twiml, media_type="application/xml")


# ─── Fallback Schedulers ───


async def _requeue_call(call_record: OutboundCall) -> None:
    """Re-queue a failed call for another attempt."""
    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        task = {
            "workspace_id": str(call_record.workspace_id) if call_record.workspace_id else "",
            "order_id": call_record.order_id,
            "customer_phone": call_record.customer_phone,
            "customer_name": call_record.customer_name or "العميل",
            "store_name": call_record.store_name or "المتجر",
            "call_type": call_record.call_type,
            "attempt_count": call_record.attempt_count,
            "retry": True,
        }
        await r.lpush("cod_shield_calls", json.dumps(task, ensure_ascii=False))
        await r.aclose()
    except Exception as e:
        logger.error("Failed to requeue call for order %s: %s", call_record.order_id, e)


async def _schedule_whatsapp_fallback(call_record: OutboundCall) -> None:
    """Schedule a WhatsApp message as fallback after call failure."""
    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True)

        task = {
            "type": "cod_whatsapp_fallback",
            "workspace_id": str(call_record.workspace_id) if call_record.workspace_id else "",
            "order_id": call_record.order_id,
            "customer_phone": call_record.customer_phone,
            "customer_name": call_record.customer_name or "العميل",
            "store_name": call_record.store_name or "المتجر",
            "message_template": "cod_confirmation",
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        }

        await r.lpush("cod_shield_whatsapp", json.dumps(task, ensure_ascii=False))
        await r.aclose()

        logger.info("WhatsApp fallback scheduled for order %s (15 min)", call_record.order_id)
    except Exception as e:
        logger.error("Failed to schedule WhatsApp fallback: %s", e)


async def _schedule_save_the_sale(call_record: OutboundCall) -> None:
    """Schedule a Save the Sale WhatsApp conversation after cancellation."""
    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True)

        task = {
            "type": "save_the_sale",
            "workspace_id": str(call_record.workspace_id) if call_record.workspace_id else "",
            "order_id": call_record.order_id,
            "customer_phone": call_record.customer_phone,
            "customer_name": call_record.customer_name or "العميل",
            "store_name": call_record.store_name or "المتجر",
            "message": f"مرحباً {call_record.customer_name or 'العميل'}، لاحظنا إنك لغيت طلبك رقم {call_record.order_id}. ممكن نعرف السبب؟ لو فيه أي مشكلة نقدر نحلها لك 🙏",
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
        }

        await r.lpush("cod_shield_whatsapp", json.dumps(task, ensure_ascii=False))
        await r.aclose()

        logger.info("Save the Sale scheduled for order %s", call_record.order_id)
    except Exception as e:
        logger.error("Failed to schedule Save the Sale: %s", e)
