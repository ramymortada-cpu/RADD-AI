"""
RADD AI — Monitoring & Alerting
================================
نظام مراقبة وتنبيهات لكل المكونات الحرجة.

الملف: apps/api/radd/monitoring/alerts.py
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("radd.monitoring")


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


class AlertType(str, Enum):
    WORKER_DOWN = "worker_down"
    ESCALATION_QUEUE_FULL = "escalation_queue_full"
    OPENAI_ERROR = "openai_error"
    HIGH_HALLUCINATION_RATE = "high_hallucination_rate"
    HIGH_ESCALATION_RATE = "high_escalation_rate"
    LOW_AUTOMATION_RATE = "low_automation_rate"
    HIGH_LATENCY = "high_latency"
    KB_GAP_DETECTED = "kb_gap_detected"
    INTENT_FALLBACK_SPIKE = "intent_fallback_spike"


@dataclass
class Alert:
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    workspace_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class AlertManager:
    """
    يدير التنبيهات ويرسلها للقنوات المناسبة.
    """

    def __init__(self, redis_client=None, slack_webhook_url: str = None):
        self.redis = redis_client
        self.slack_webhook = slack_webhook_url
        self._recent_alerts: list[Alert] = []

    async def fire(self, alert: Alert):
        """يطلق تنبيه ويرسله لكل القنوات."""
        self._recent_alerts.append(alert)

        # تخزين في Redis
        if self.redis:
            await self._store_alert(alert)

        # تسجيل في logs
        log_method = {
            AlertSeverity.INFO: logger.info,
            AlertSeverity.WARNING: logger.warning,
            AlertSeverity.CRITICAL: logger.error,
            AlertSeverity.FATAL: logger.critical,
        }.get(alert.severity, logger.warning)

        log_method(
            f"alert.{alert.alert_type.value}",
            message=alert.message,
            workspace_id=alert.workspace_id,
            severity=alert.severity.value,
            **alert.metadata,
        )

        # إرسال لـ Slack
        if self.slack_webhook and alert.severity in (AlertSeverity.CRITICAL, AlertSeverity.FATAL):
            await self._send_slack(alert)

    async def _store_alert(self, alert: Alert):
        """يخزن التنبيه في Redis."""
        try:
            import json
            key = f"alerts:{alert.workspace_id or 'global'}"
            data = {
                "type": alert.alert_type.value,
                "severity": alert.severity.value,
                "message": alert.message,
                "metadata": json.dumps(alert.metadata, ensure_ascii=False),
                "timestamp": str(alert.timestamp),
            }
            await self.redis.xadd(key, data, maxlen=1000)
        except Exception as e:
            logger.warning("alert.store_failed", error=str(e))

    async def _send_slack(self, alert: Alert):
        """يرسل تنبيه لـ Slack."""
        if not self.slack_webhook:
            return
        try:
            import httpx

            emoji = {"critical": "🔴", "fatal": "🚨"}.get(alert.severity.value, "⚠️")
            text = f"{emoji} *RADD Alert — {alert.alert_type.value}*\n{alert.message}"
            if alert.workspace_id:
                text += f"\nWorkspace: `{alert.workspace_id}`"

            async with httpx.AsyncClient() as client:
                await client.post(
                    self.slack_webhook,
                    json={"text": text},
                    timeout=5,
                )
        except Exception as e:
            logger.warning("alert.slack_failed", error=str(e))


# ---------------------------------------------------------------------------
# Health Checks — للمكونات الحرجة
# ---------------------------------------------------------------------------

class SystemHealthChecker:
    """يفحص صحة كل مكونات النظام."""

    def __init__(self, redis_client=None, db_session=None, alert_manager: AlertManager = None):
        self.redis = redis_client
        self.db = db_session
        self.alerts = alert_manager

    async def check_all(self) -> dict:
        """يفحص كل المكونات ويرجع تقرير شامل."""
        results = {
            "status": "healthy",
            "checks": {},
            "timestamp": time.time(),
        }

        # 1. Redis
        results["checks"]["redis"] = await self._check_redis()

        # 2. Workers
        results["checks"]["workers"] = await self._check_workers()

        # 3. Escalation Queue
        results["checks"]["escalation_queue"] = await self._check_escalation_queue()

        # 4. OpenAI
        results["checks"]["openai"] = await self._check_openai()

        # تحديد الحالة الإجمالية
        if any(c.get("status") == "critical" for c in results["checks"].values()):
            results["status"] = "critical"
        elif any(c.get("status") == "degraded" for c in results["checks"].values()):
            results["status"] = "degraded"

        return results

    async def _check_redis(self) -> dict:
        if not self.redis:
            return {"status": "unknown", "message": "no redis client"}
        try:
            start = time.monotonic()
            await self.redis.ping()
            latency = round((time.monotonic() - start) * 1000, 1)
            return {"status": "healthy", "latency_ms": latency}
        except Exception as e:
            return {"status": "critical", "error": str(e)}

    async def _check_workers(self) -> dict:
        if not self.redis:
            return {"status": "unknown"}
        try:
            workers = await self.redis.zrangebyscore(
                "active-workers", time.time() - 60, "+inf"
            )
            count = len(workers)
            if count == 0:
                if self.alerts:
                    await self.alerts.fire(Alert(
                        alert_type=AlertType.WORKER_DOWN,
                        severity=AlertSeverity.CRITICAL,
                        message="لا يوجد أي عامل نشط! كل الرسائل الواردة ستتراكم.",
                    ))
                return {"status": "critical", "active_workers": 0}
            return {"status": "healthy", "active_workers": count}
        except Exception as e:
            return {"status": "unknown", "error": str(e)}

    async def _check_escalation_queue(self) -> dict:
        if not self.redis:
            return {"status": "unknown"}
        try:
            # عدد التصعيدات المعلقة (يعتمد على schema DB)
            return {"status": "healthy", "pending": 0}
        except Exception as e:
            return {"status": "unknown", "error": str(e)}

    async def _check_openai(self) -> dict:
        try:
            import openai
            start = time.monotonic()
            client = openai.OpenAI()
            # Simple test call
            client.models.list()
            latency = round((time.monotonic() - start) * 1000, 1)
            return {"status": "healthy", "latency_ms": latency}
        except Exception as e:
            if self.alerts:
                await self.alerts.fire(Alert(
                    alert_type=AlertType.OPENAI_ERROR,
                    severity=AlertSeverity.CRITICAL,
                    message=f"OpenAI API غير متاح: {str(e)[:100]}",
                ))
            return {"status": "critical", "error": str(e)[:100]}


# ---------------------------------------------------------------------------
# Metrics Tracker — لمؤشرات الأداء
# ---------------------------------------------------------------------------

class MetricsTracker:
    """
    يتتبع مؤشرات الأداء بعد الإطلاق.
    يُخزن في Redis counters.
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    async def track_intent_classification(
        self,
        workspace_id: str,
        intent: str,
        latency_ms: float,
        cached: bool,
        fallback: bool,
    ):
        """يسجل تصنيف نية."""
        if not self.redis:
            return
        try:
            pipe = self.redis.pipeline()
            today = time.strftime("%Y-%m-%d")
            prefix = f"metrics:{workspace_id}:{today}"

            pipe.hincrby(f"{prefix}:intents", intent, 1)
            pipe.hincrby(f"{prefix}:intent_total", "count", 1)
            pipe.hincrbyfloat(f"{prefix}:intent_total", "latency_sum", latency_ms)
            if cached:
                pipe.hincrby(f"{prefix}:intent_total", "cached", 1)
            if fallback:
                pipe.hincrby(f"{prefix}:intent_total", "fallback", 1)

            # TTL 7 أيام
            pipe.expire(f"{prefix}:intents", 604800)
            pipe.expire(f"{prefix}:intent_total", 604800)
            await pipe.execute()
        except Exception as e:
            logger.warning("metrics.track_intent_failed", error=str(e))

    async def track_verification(
        self,
        workspace_id: str,
        c_verify: float,
        is_grounded: bool,
        latency_ms: float,
    ):
        """يسجل نتيجة تحقق."""
        if not self.redis:
            return
        try:
            today = time.strftime("%Y-%m-%d")
            prefix = f"metrics:{workspace_id}:{today}"

            pipe = self.redis.pipeline()
            pipe.hincrby(f"{prefix}:verify", "total", 1)
            pipe.hincrbyfloat(f"{prefix}:verify", "score_sum", c_verify)
            if not is_grounded:
                pipe.hincrby(f"{prefix}:verify", "rejected", 1)
            pipe.expire(f"{prefix}:verify", 604800)
            await pipe.execute()
        except Exception as e:
            logger.warning("metrics.track_verify_failed", error=str(e))

    async def track_message_processed(
        self,
        workspace_id: str,
        resolution_type: str,
        latency_ms: float,
    ):
        """يسجل معالجة رسالة."""
        if not self.redis:
            return
        try:
            today = time.strftime("%Y-%m-%d")
            prefix = f"metrics:{workspace_id}:{today}"

            pipe = self.redis.pipeline()
            pipe.hincrby(f"{prefix}:messages", "total", 1)
            pipe.hincrby(f"{prefix}:messages", resolution_type, 1)
            pipe.hincrbyfloat(f"{prefix}:messages", "latency_sum", latency_ms)
            pipe.expire(f"{prefix}:messages", 604800)
            await pipe.execute()
        except Exception as e:
            logger.warning("metrics.track_message_failed", error=str(e))

    async def get_daily_summary(self, workspace_id: str) -> dict:
        """يجلب ملخص اليوم."""
        if not self.redis:
            return {}
        try:
            today = time.strftime("%Y-%m-%d")
            prefix = f"metrics:{workspace_id}:{today}"

            pipe = self.redis.pipeline()
            pipe.hgetall(f"{prefix}:messages")
            pipe.hgetall(f"{prefix}:intents")
            pipe.hgetall(f"{prefix}:intent_total")
            pipe.hgetall(f"{prefix}:verify")
            results = await pipe.execute()

            return {
                "date": today,
                "messages": {k.decode(): v.decode() for k, v in results[0].items()} if results[0] else {},
                "intents": {k.decode(): int(v) for k, v in results[1].items()} if results[1] else {},
                "intent_stats": {k.decode(): v.decode() for k, v in results[2].items()} if results[2] else {},
                "verification": {k.decode(): v.decode() for k, v in results[3].items()} if results[3] else {},
            }
        except Exception as e:
            logger.warning("metrics.get_summary_failed", error=str(e))
            return {}
