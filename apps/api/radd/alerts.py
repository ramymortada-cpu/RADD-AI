"""
RADD Alert Manager — تنبيهات الأحداث الحرجة.

يرسل تنبيهات إلى Slack عند:
- توقف الـ Worker
- امتلاء escalation queue
- خطأ حرج في الـ pipeline
- فشل متكرر في webhook
- تجاوز rate limit بشكل مفرط

المستويات:
  INFO    → يُسجَّل فقط (structlog)
  WARNING → يُسجَّل + Sentry
  CRITICAL → يُسجَّل + Sentry + Slack
  FATAL   → يُسجَّل + Sentry + Slack + Email (مستقبلاً)
"""

import hashlib
import json
import time
from enum import Enum
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


# ألوان Slack حسب المستوى
_SLACK_COLORS = {
    AlertLevel.INFO: "#36a64f",       # أخضر
    AlertLevel.WARNING: "#ff9800",    # برتقالي
    AlertLevel.CRITICAL: "#e53935",   # أحمر
    AlertLevel.FATAL: "#7b1fa2",     # بنفسجي داكن
}

# إيقونات حسب المستوى
_SLACK_ICONS = {
    AlertLevel.INFO: "ℹ️",
    AlertLevel.WARNING: "⚠️",
    AlertLevel.CRITICAL: "🚨",
    AlertLevel.FATAL: "💀",
}

# منع تكرار نفس التنبيه — في الـ memory (يكفي للـ MVP)
_alert_cooldowns: dict[str, float] = {}
_COOLDOWN_SECONDS = 300  # 5 دقائق بين نفس التنبيه


class AlertManager:
    """
    مدير التنبيهات المركزي.

    الاستخدام:
        from radd.alerts import alert_manager

        await alert_manager.critical(
            event="worker_crashed",
            message="Message worker stopped processing",
            context={"workspace_id": str(ws_id), "error": str(e)},
        )
    """

    def __init__(self, slack_webhook_url: str = "", app_env: str = "production"):
        self.slack_webhook_url = slack_webhook_url
        self.app_env = app_env
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Public API ──────────────────────────────────────────

    async def info(self, event: str, message: str, context: dict[str, Any] | None = None) -> None:
        await self._handle(AlertLevel.INFO, event, message, context)

    async def warning(self, event: str, message: str, context: dict[str, Any] | None = None) -> None:
        await self._handle(AlertLevel.WARNING, event, message, context)

    async def critical(self, event: str, message: str, context: dict[str, Any] | None = None) -> None:
        await self._handle(AlertLevel.CRITICAL, event, message, context)

    async def fatal(self, event: str, message: str, context: dict[str, Any] | None = None) -> None:
        await self._handle(AlertLevel.FATAL, event, message, context)

    # ── Core Logic ──────────────────────────────────────────

    async def _handle(
        self,
        level: AlertLevel,
        event: str,
        message: str,
        context: dict[str, Any] | None,
    ) -> None:
        ctx = context or {}

        # 1. دائماً نسجّل
        log_fn = {
            AlertLevel.INFO: logger.info,
            AlertLevel.WARNING: logger.warning,
            AlertLevel.CRITICAL: logger.error,
            AlertLevel.FATAL: logger.critical,
        }[level]

        log_fn(f"alert.{event}", level=level.value, message=message, **ctx)

        # 2. Sentry لـ WARNING وما فوق
        if level in (AlertLevel.WARNING, AlertLevel.CRITICAL, AlertLevel.FATAL):
            self._capture_sentry(level, event, message, ctx)

        # 3. Slack لـ CRITICAL وما فوق فقط
        if level in (AlertLevel.CRITICAL, AlertLevel.FATAL):
            if self._should_send(event, level):
                await self._send_slack(level, event, message, ctx)

    def _should_send(self, event: str, level: AlertLevel) -> bool:
        """منع تكرار نفس التنبيه خلال فترة الـ cooldown."""
        key = hashlib.md5(f"{event}:{level.value}".encode()).hexdigest()
        now = time.monotonic()
        last_sent = _alert_cooldowns.get(key, 0)

        if now - last_sent < _COOLDOWN_SECONDS:
            logger.debug(
                "alert.cooldown_skipped",
                alert_event=event,
                cooldown_remaining=int(_COOLDOWN_SECONDS - (now - last_sent)),
            )
            return False

        _alert_cooldowns[key] = now
        return True

    def _capture_sentry(
        self,
        level: AlertLevel,
        event: str,
        message: str,
        context: dict[str, Any],
    ) -> None:
        """إرسال الحدث إلى Sentry مع السياق الكامل."""
        try:
            import sentry_sdk

            with sentry_sdk.push_scope() as scope:
                scope.set_tag("alert.level", level.value)
                scope.set_tag("alert.event", event)
                scope.set_tag("environment", self.app_env)
                for key, val in context.items():
                    scope.set_extra(key, val)

                if level == AlertLevel.FATAL:
                    sentry_sdk.capture_exception(
                        RuntimeError(f"[FATAL] {event}: {message}")
                    )
                else:
                    sentry_sdk.capture_message(
                        f"[{level.value.upper()}] {event}: {message}",
                        level=level.value,
                    )
        except ImportError:
            pass  # Sentry غير مثبت — نتجاهل

    async def _send_slack(
        self,
        level: AlertLevel,
        event: str,
        message: str,
        context: dict[str, Any],
    ) -> None:
        """إرسال تنبيه Slack."""
        if not self.slack_webhook_url:
            logger.debug("alert.slack_not_configured", alert_event=event)
            return

        icon = _SLACK_ICONS[level]
        color = _SLACK_COLORS[level]
        env_label = f"`{self.app_env}`"

        # بناء context fields
        fields = [
            {"title": "Event", "value": f"`{event}`", "short": True},
            {"title": "Environment", "value": env_label, "short": True},
        ]

        for key, val in context.items():
            if key not in ("traceback", "stack_trace"):  # تجنب الإفصاح عن stack traces
                val_str = str(val)
                display_val = f"`{val_str}`" if len(val_str) < 100 else val_str[:100] + "…"
                fields.append({
                    "title": key.replace("_", " ").title(),
                    "value": display_val,
                    "short": True,
                })

        payload = {
            "text": f"{icon} *RADD Alert — {level.value.upper()}*",
            "attachments": [
                {
                    "color": color,
                    "title": message,
                    "fields": fields,
                    "footer": "RADD AI Alert System",
                    "ts": int(time.time()),
                }
            ],
        }

        try:
            client = self._get_client()
            response = await client.post(
                self.slack_webhook_url,
                content=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            if response.status_code != 200:
                logger.warning(
                    "alert.slack_failed",
                    status_code=response.status_code,
                    response=response.text[:200],
                )
        except Exception as e:
            # التنبيهات لا تكسر التطبيق أبداً
            logger.error("alert.slack_exception", error=str(e))


# ── Singleton ────────────────────────────────────────────────────────────────
# يُهيَّأ في main.py بعد قراءة config

alert_manager: AlertManager = AlertManager()


def init_alert_manager(slack_webhook_url: str, app_env: str) -> None:
    """استدعِ هذه الدالة مرة واحدة في main.py عند بدء التطبيق."""
    global alert_manager
    alert_manager = AlertManager(
        slack_webhook_url=slack_webhook_url,
        app_env=app_env,
    )
    logger.info(
        "alert_manager.initialized",
        slack_configured=bool(slack_webhook_url),
        environment=app_env,
    )
