"""
RADD AI — Message Worker v2.0 — Horizontal Scaling
===================================================
يحل مشكلة bottleneck في العامل الحالي بالانتقال من consumer group واحد
إلى نموذج "مجموعة لكل مساحة عمل" (Group-per-Workspace).

الملف الأصلي: apps/api/workers/message_worker.py
هذا الملف: apps/api/workers/message_worker_v2.py
"""

from __future__ import annotations

import asyncio
import logging
import signal
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("radd.workers.message_worker_v2")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONSUMER_NAME_PREFIX = "radd-worker"
WORKER_REGISTRY_KEY = "active-workers"
WORKER_HEARTBEAT_TTL = 30  # seconds
STREAM_DISCOVERY_INTERVAL = 10  # seconds
BATCH_SIZE = 5  # messages per workspace per read
BLOCK_TIMEOUT_MS = 200  # short block for round-robin
MAIN_LOOP_SLEEP = 0.5  # seconds between main loop iterations
ERROR_SLEEP = 2  # seconds to sleep on error
HEALTH_CHECK_INTERVAL = 10  # seconds


# ---------------------------------------------------------------------------
# Worker Registry — تسجيل العمال في Redis
# ---------------------------------------------------------------------------

@dataclass
class WorkerInfo:
    """معلومات عامل واحد."""
    worker_id: str
    started_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    streams_assigned: list[str] = field(default_factory=list)
    messages_processed: int = 0


class WorkerRegistry:
    """
    يدير تسجيل العمال في Redis وتتبع حالتهم.
    كل عامل يسجل نفسه ويرسل heartbeat دوري.
    """

    def __init__(self, redis_client, worker_id: str):
        self.redis = redis_client
        self.worker_id = worker_id

    async def register(self):
        """يسجل العامل في Redis."""
        await self.redis.zadd(
            WORKER_REGISTRY_KEY,
            {self.worker_id: time.time()},
        )
        logger.info("worker_v2.registered", worker_id=self.worker_id)

    async def heartbeat(self):
        """يحدث timestamp العامل (heartbeat)."""
        await self.redis.zadd(
            WORKER_REGISTRY_KEY,
            {self.worker_id: time.time()},
        )

    async def deregister(self):
        """يزيل العامل من الـ registry."""
        await self.redis.zrem(WORKER_REGISTRY_KEY, self.worker_id)
        logger.info("worker_v2.deregistered", worker_id=self.worker_id)

    async def get_active_workers(self) -> list[str]:
        """يرجع قائمة العمال النشطين (heartbeat خلال آخر 60 ثانية)."""
        cutoff = time.time() - 60
        # إزالة العمال الميتين
        await self.redis.zremrangebyscore(WORKER_REGISTRY_KEY, 0, cutoff)
        # جلب الباقيين
        workers = await self.redis.zrangebyscore(
            WORKER_REGISTRY_KEY, cutoff, "+inf"
        )
        return [w.decode("utf-8") if isinstance(w, bytes) else w for w in workers]

    async def get_worker_rank(self) -> tuple[int, int]:
        """يرجع ترتيب هذا العامل وإجمالي العمال."""
        workers = await self.get_active_workers()
        workers.sort()  # ترتيب ثابت لضمان التوزيع المتسق
        try:
            rank = workers.index(self.worker_id)
        except ValueError:
            rank = 0
        return rank, len(workers) or 1


# ---------------------------------------------------------------------------
# Stream Router — توزيع الـ streams على العمال
# ---------------------------------------------------------------------------

class StreamRouter:
    """
    يحدد أي streams يراقبها كل عامل بناءً على ترتيبه.
    يستخدم consistent hashing بسيط: كل عامل يأخذ streams حسب hash(stream) % total_workers.
    """

    def __init__(self, redis_client, registry: WorkerRegistry):
        self.redis = redis_client
        self.registry = registry
        self._cached_streams: list[str] = []
        self._last_discovery: float = 0

    async def discover_streams(self) -> list[str]:
        """يكتشف كل الـ streams النشطة."""
        now = time.time()
        if now - self._last_discovery < STREAM_DISCOVERY_INTERVAL and self._cached_streams:
            return self._cached_streams

        try:
            keys = await self.redis.keys("messages:*")
            streams = []
            for key in keys:
                k = key.decode("utf-8") if isinstance(key, bytes) else key
                # تجاهل الـ stream القديم بدون workspace ID
                if ":" in k and k != "messages:":
                    streams.append(k)

            self._cached_streams = sorted(streams)
            self._last_discovery = now
            return self._cached_streams

        except Exception as e:
            logger.warning("worker_v2.stream_discovery_failed", error=str(e))
            return self._cached_streams

    async def get_my_streams(self) -> list[str]:
        """يرجع الـ streams المخصصة لهذا العامل."""
        all_streams = await self.discover_streams()
        if not all_streams:
            return []

        rank, total = await self.registry.get_worker_rank()

        # توزيع بسيط: كل عامل يأخذ streams حسب index % total
        my_streams = [
            s for i, s in enumerate(all_streams) if i % total == rank
        ]

        return my_streams


# ---------------------------------------------------------------------------
# Consumer Group Manager
# ---------------------------------------------------------------------------

async def ensure_consumer_group(redis_client, stream_key: str, group_name: str):
    """ينشئ consumer group إذا لم تكن موجودة."""
    try:
        await redis_client.xgroup_create(
            stream_key, group_name, id="0", mkstream=True
        )
    except Exception as e:
        if "BUSYGROUP" not in str(e):
            logger.warning(
                "worker_v2.xgroup_create_failed",
                group=group_name,
                stream=stream_key,
                error=str(e),
            )


def get_consumer_group(stream_key: str) -> str:
    """يستخرج اسم الـ consumer group من اسم الـ stream."""
    # messages:ws_abc123 → group:ws_abc123
    parts = stream_key.split(":", 1)
    workspace_id = parts[1] if len(parts) > 1 else "default"
    return f"group:{workspace_id}"


# ---------------------------------------------------------------------------
# Message Processing
# ---------------------------------------------------------------------------

async def process_message(msg_data: dict, workspace_id: str):
    """
    يعالج رسالة واحدة — يستدعي الـ pipeline.

    هذا هو المكان الذي يتم فيه:
    1. Parse message payload
    2. Resolve/create Customer record
    3. Resolve/create Conversation
    4. Load conversation history
    5. run_pipeline_async() مع المصنف الجديد
    6. Apply guardrails
    7. Store messages in DB
    8. Send WhatsApp reply
    9. If escalated: create EscalationEvent + WS broadcast
    """
    # استيراد الـ pipeline (deferred لتجنب circular imports)
    try:
        from radd.pipeline.orchestrator import run_pipeline_async
        from radd.pipeline.intent_v2 import classify_intent_llm

        # --- Parse ---
        message_text = msg_data.get(b"text", msg_data.get("text", ""))
        if isinstance(message_text, bytes):
            message_text = message_text.decode("utf-8")

        customer_phone = msg_data.get(b"phone", msg_data.get("phone", ""))
        if isinstance(customer_phone, bytes):
            customer_phone = customer_phone.decode("utf-8")

        wa_message_id = msg_data.get(b"wa_msg_id", msg_data.get("wa_msg_id", ""))
        if isinstance(wa_message_id, bytes):
            wa_message_id = wa_message_id.decode("utf-8")

        logger.info(
            "worker_v2.processing_message",
            workspace_id=workspace_id,
            text_preview=message_text[:50],
        )

        # --- تصنيف النية (الجديد) ---
        intent_result = await classify_intent_llm(message_text)

        logger.info(
            "worker_v2.intent_classified",
            intent=intent_result["intent_name"],
            entities=intent_result.get("entities", {}),
            fallback=intent_result.get("fallback", False),
        )

        # --- باقي الـ pipeline ---
        # TODO: استدعاء run_pipeline_async مع intent_result
        # هذا يعتمد على الكود الحالي في orchestrator.py
        # سيتم تعديله في orchestrator_patch.py

        return True

    except Exception as e:
        logger.error(
            "worker_v2.process_message_failed",
            error=str(e),
            workspace_id=workspace_id,
        )
        return False


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@dataclass
class WorkerHealth:
    """حالة صحة العامل."""
    worker_id: str
    status: str = "healthy"
    uptime_seconds: float = 0
    messages_processed: int = 0
    streams_assigned: int = 0
    last_heartbeat: float = 0
    errors_last_minute: int = 0


class HealthTracker:
    """يتتبع صحة العامل."""

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.started_at = time.time()
        self.messages_processed = 0
        self.errors: list[float] = []

    def record_success(self):
        self.messages_processed += 1

    def record_error(self):
        self.errors.append(time.time())
        # تنظيف الأخطاء القديمة (أكثر من دقيقة)
        cutoff = time.time() - 60
        self.errors = [e for e in self.errors if e > cutoff]

    def get_health(self, streams_count: int) -> WorkerHealth:
        cutoff = time.time() - 60
        recent_errors = len([e for e in self.errors if e > cutoff])
        return WorkerHealth(
            worker_id=self.worker_id,
            status="healthy" if recent_errors < 10 else "degraded",
            uptime_seconds=round(time.time() - self.started_at, 1),
            messages_processed=self.messages_processed,
            streams_assigned=streams_count,
            last_heartbeat=time.time(),
            errors_last_minute=recent_errors,
        )


# ---------------------------------------------------------------------------
# Main Worker Loop
# ---------------------------------------------------------------------------

async def run_worker(redis_client):
    """
    الحلقة الرئيسية للعامل v2.

    1. يسجل نفسه في الـ registry
    2. يكتشف الـ streams المخصصة له
    3. ينشئ consumer groups إذا لم تكن موجودة
    4. يقرأ ويعالج الرسائل
    5. يرسل heartbeat دوري
    """
    worker_id = f"{CONSUMER_NAME_PREFIX}-{uuid.uuid4().hex[:8]}"
    registry = WorkerRegistry(redis_client, worker_id)
    router = StreamRouter(redis_client, registry)
    health = HealthTracker(worker_id)

    # التسجيل
    await registry.register()
    logger.info("worker_v2.started", worker_id=worker_id)

    # Graceful shutdown
    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("worker_v2.shutdown_requested", worker_id=worker_id)
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    last_heartbeat = 0

    try:
        while not shutdown_event.is_set():
            try:
                # --- Heartbeat ---
                now = time.time()
                if now - last_heartbeat > WORKER_HEARTBEAT_TTL / 2:
                    await registry.heartbeat()
                    last_heartbeat = now

                # --- اكتشاف وتوزيع الـ streams ---
                my_streams = await router.get_my_streams()

                if not my_streams:
                    logger.debug("worker_v2.no_streams_assigned", worker_id=worker_id)
                    await asyncio.sleep(STREAM_DISCOVERY_INTERVAL)
                    continue

                # --- إنشاء consumer groups ---
                for stream_key in my_streams:
                    group = get_consumer_group(stream_key)
                    await ensure_consumer_group(redis_client, stream_key, group)

                # --- قراءة الرسائل من كل stream ---
                for stream_key in my_streams:
                    group = get_consumer_group(stream_key)
                    workspace_id = stream_key.split(":", 1)[-1] if ":" in stream_key else "unknown"

                    try:
                        messages = await redis_client.xreadgroup(
                            group,
                            worker_id,
                            {stream_key: ">"},
                            count=BATCH_SIZE,
                            block=BLOCK_TIMEOUT_MS,
                        )

                        if not messages:
                            continue

                        for _, msg_list in messages:
                            for msg_id, msg_data in msg_list:
                                try:
                                    success = await process_message(
                                        msg_data, workspace_id
                                    )
                                    if success:
                                        await redis_client.xack(
                                            stream_key, group, msg_id
                                        )
                                        health.record_success()
                                    else:
                                        health.record_error()

                                except Exception as e:
                                    logger.error(
                                        "worker_v2.message_failed",
                                        error=str(e),
                                        msg_id=msg_id,
                                        stream=stream_key,
                                    )
                                    health.record_error()

                    except Exception as e:
                        logger.error(
                            "worker_v2.stream_read_error",
                            error=str(e),
                            stream=stream_key,
                        )

                # --- فترة راحة بين الدورات ---
                await asyncio.sleep(MAIN_LOOP_SLEEP)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("worker_v2.main_loop_error", error=str(e))
                await asyncio.sleep(ERROR_SLEEP)

    finally:
        # إلغاء التسجيل عند الإيقاف
        await registry.deregister()
        worker_health = health.get_health(len(my_streams) if 'my_streams' in dir() else 0)
        logger.info(
            "worker_v2.stopped",
            worker_id=worker_id,
            messages_processed=worker_health.messages_processed,
            uptime_seconds=worker_health.uptime_seconds,
        )


# ---------------------------------------------------------------------------
# Webhook Publisher Update — تعديل مكان نشر الرسائل
# ---------------------------------------------------------------------------

async def publish_message_to_stream(
    redis_client,
    workspace_id: str,
    message_data: dict,
) -> str:
    """
    ينشر رسالة في الـ stream الخاص بالـ workspace.
    يُستدعى من radd/webhooks/router.py بدل النشر في stream واحد.

    Args:
        redis_client: Redis client
        workspace_id: معرف مساحة العمل
        message_data: بيانات الرسالة

    Returns:
        message_id من Redis
    """
    stream_key = f"messages:{workspace_id}"
    msg_id = await redis_client.xadd(stream_key, message_data)
    logger.debug(
        "worker_v2.message_published",
        stream=stream_key,
        msg_id=msg_id,
    )
    return msg_id


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

async def main():
    """نقطة الدخول — يتصل بـ Redis ويبدأ العمل."""
    # استيراد Redis client من المشروع
    try:
        from radd.deps import get_redis
        redis_client = get_redis()
    except ImportError:
        # Fallback for standalone testing
        import redis.asyncio as redis
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = redis.from_url(redis_url, decode_responses=False)

    await run_worker(redis_client)


if __name__ == "__main__":
    asyncio.run(main())
