#!/usr/bin/env python3
"""
Outbound Call Worker — COD Shield

Consumes call tasks from Redis list 'cod_shield_calls'
and initiates outbound calls via Twilio.

Usage:
    cd apps/api && uv run python -m workers.outbound_call_worker

Redis task format (JSON):
{
    "workspace_id": "uuid",
    "order_id": "ORD-12345",
    "customer_phone": "+201234567890",
    "customer_name": "أحمد",
    "store_name": "متجر النور",
    "call_type": "order_confirmation"  // or "shipping_verification"
}
"""
import asyncio
import json
import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import redis.asyncio as aioredis

logger = logging.getLogger("radd.worker.outbound_call")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

QUEUE_NAME = "cod_shield_calls"
POLL_INTERVAL = 2  # seconds between polls when queue is empty


class OutboundCallWorker:
    """Processes outbound call tasks from Redis queue."""

    def __init__(self):
        self._running = True
        self._redis = None

    async def start(self):
        """Main worker loop."""
        from radd.config import settings

        self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)

        logger.info("OutboundCallWorker started — listening on '%s'", QUEUE_NAME)

        while self._running:
            try:
                result = await self._redis.brpop(QUEUE_NAME, timeout=5)

                if result is None:
                    continue

                _, task_json = result
                task = json.loads(task_json)

                logger.info(
                    "Processing call task: order=%s, phone=%s",
                    task.get("order_id"),
                    task.get("customer_phone"),
                )

                await self._process_task(task)

            except json.JSONDecodeError as e:
                logger.error("Invalid JSON in queue: %s", e)
            except Exception as e:
                logger.error("Error processing task: %s", e, exc_info=True)
                await asyncio.sleep(POLL_INTERVAL)

        logger.info("OutboundCallWorker stopped")

    async def _process_task(self, task: dict) -> None:
        """Process a single call task."""
        from radd.config import settings
        from radd.db.models import OutboundCall
        from radd.db.session import get_db_session
        from radd.voice.outbound_poc import make_outbound_call
        from sqlalchemy import select

        workspace_id_str = task.get("workspace_id")
        order_id = task.get("order_id", "unknown")
        customer_phone = task.get("customer_phone")
        customer_name = task.get("customer_name", "العميل")
        store_name = task.get("store_name", "المتجر")
        task.get("call_type", "order_confirmation")

        if not customer_phone:
            logger.error("No phone number for order %s — skipping", order_id)
            return

        if not workspace_id_str:
            logger.error("No workspace_id for order %s — skipping", order_id)
            return

        try:
            workspace_id = UUID(workspace_id_str)
        except (ValueError, TypeError):
            logger.error("Invalid workspace_id for order %s — skipping", order_id)
            return

        attempt_count = task.get("attempt_count", 1)
        call_record_id = None
        try:
            async with get_db_session(workspace_id) as db:
                call_record = OutboundCall(
                    workspace_id=workspace_id,
                    order_id=order_id,
                    customer_phone=customer_phone,
                    customer_name=customer_name,
                    store_name=store_name,
                    call_type="order_confirmation",
                    status="calling",
                    attempt_count=attempt_count,
                )
                db.add(call_record)
                await db.flush()
                await db.refresh(call_record)
                call_record_id = call_record.id
                logger.info("Created call record: %s", call_record_id)
        except Exception as e:
            logger.error("Failed to create call record for order %s: %s", order_id, e)

        result = make_outbound_call(
            to_number=customer_phone,
            customer_name=customer_name,
            order_id=order_id,
            store_name=store_name,
        )

        if call_record_id:
            try:
                async with get_db_session(workspace_id) as db:
                    stmt = select(OutboundCall).where(OutboundCall.id == call_record_id)
                    res = await db.execute(stmt)
                    record = res.scalars().one_or_none()

                    if record:
                        if result.get("success"):
                            call_sid = result.get("call_sid")
                            record.call_sid = call_sid
                            record.status = "calling"
                            record.called_at = datetime.now(timezone.utc)
                            # Store call_sid -> workspace_id for Twilio webhook lookup
                            try:
                                r = aioredis.from_url(settings.redis_url, decode_responses=True)
                                await r.set(
                                    f"cod_shield_call_sid:{call_sid}",
                                    workspace_id_str,
                                    ex=86400,
                                )
                                await r.aclose()
                            except Exception as e:
                                logger.warning("Failed to store call_sid mapping: %s", e)
                            logger.info("Call initiated: SID=%s", call_sid)
                        else:
                            record.status = "failed"
                            record.metadata_ = {"error": result.get("error", "unknown")}
                            logger.error("Call failed for order %s: %s", order_id, result.get("error"))

                    await db.flush()
            except Exception as e:
                logger.error("Failed to update call record %s: %s", call_record_id, e)

    def stop(self):
        """Signal the worker to stop."""
        self._running = False
        logger.info("Shutdown signal received")


async def main():
    worker = OutboundCallWorker()

    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, worker.stop)
    except (NotImplementedError, OSError):
        pass

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
