"""
RADD AI — Rate Limiting Middleware
===================================
حماية الـ API من الاستخدام المفرط لكل workspace.

الملف: apps/api/radd/middleware/rate_limiter.py
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("radd.middleware.rate_limiter")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# حدود لكل workspace في الدقيقة
RATE_LIMITS = {
    "pilot": {"rpm": 60, "burst": 10},
    "growth": {"rpm": 200, "burst": 30},
    "scale": {"rpm": 1000, "burst": 100},
    "default": {"rpm": 100, "burst": 20},
}

# مسارات مستثناة من الـ rate limiting
EXEMPT_PATHS = {
    "/health",
    "/api/v1/webhooks/whatsapp",  # Meta webhooks يجب أن تمر دائماً
    "/docs",
    "/redoc",
    "/openapi.json",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware يستخدم Redis sliding window.
    يحد عدد الطلبات لكل workspace في الدقيقة.
    """

    def __init__(self, app, redis_client=None):
        super().__init__(app)
        self.redis = redis_client

    async def dispatch(self, request: Request, call_next):
        # تجاوز المسارات المستثناة
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # استخراج workspace_id من الـ JWT أو header
        workspace_id = self._extract_workspace_id(request)
        if not workspace_id:
            return await call_next(request)

        # التحقق من الـ rate limit
        if self.redis:
            allowed = await self._check_rate_limit(workspace_id)
            if not allowed:
                logger.warning(
                    "rate_limiter.exceeded",
                    workspace_id=workspace_id,
                    path=request.url.path,
                )
                raise HTTPException(
                    status_code=429,
                    detail="تم تجاوز الحد المسموح من الطلبات. يرجى المحاولة لاحقاً.",
                    headers={"Retry-After": "60"},
                )

        response = await call_next(request)
        return response

    def _extract_workspace_id(self, request: Request) -> Optional[str]:
        """يستخرج workspace_id من الـ request."""
        # من الـ JWT (في state بعد auth middleware)
        if hasattr(request, "state") and hasattr(request.state, "workspace_id"):
            return request.state.workspace_id
        # من header مخصص
        return request.headers.get("X-Workspace-ID")

    async def _check_rate_limit(self, workspace_id: str) -> bool:
        """
        Sliding window rate limiter باستخدام Redis.
        Returns True إذا مسموح، False إذا تم التجاوز.
        """
        try:
            key = f"rate_limit:{workspace_id}"
            now = time.time()
            window = 60  # دقيقة واحدة

            pipe = self.redis.pipeline()
            # إزالة الطلبات القديمة
            pipe.zremrangebyscore(key, 0, now - window)
            # إضافة الطلب الحالي
            pipe.zadd(key, {str(now): now})
            # عدد الطلبات في النافذة
            pipe.zcard(key)
            # تجديد TTL
            pipe.expire(key, window + 10)

            results = await pipe.execute()
            request_count = results[2]

            # جلب الحد المسموح (default: 100/min)
            limit = RATE_LIMITS.get("default", {}).get("rpm", 100)

            return request_count <= limit

        except Exception as e:
            logger.warning("rate_limiter.redis_error", error=str(e))
            return True  # في حالة خطأ Redis، نسمح بالمرور


# ---------------------------------------------------------------------------
# Webhook-specific Rate Limiter
# ---------------------------------------------------------------------------

class WebhookRateLimiter:
    """
    Rate limiter مخصص لـ WhatsApp webhooks.
    يحمي من الرسائل المكررة ويحد الحجم.
    """

    def __init__(self, redis_client, max_per_minute: int = 500):
        self.redis = redis_client
        self.max_per_minute = max_per_minute

    async def is_allowed(self, workspace_id: str) -> bool:
        """هل يُسمح بمعالجة رسالة جديدة لهذا الـ workspace؟"""
        if not self.redis:
            return True

        try:
            key = f"webhook_rate:{workspace_id}"
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, 60)
            return count <= self.max_per_minute

        except Exception:
            return True

    async def get_remaining(self, workspace_id: str) -> int:
        """كم رسالة متبقية في هذه الدقيقة."""
        if not self.redis:
            return self.max_per_minute
        try:
            key = f"webhook_rate:{workspace_id}"
            count = await self.redis.get(key)
            used = int(count) if count else 0
            return max(0, self.max_per_minute - used)
        except Exception:
            return self.max_per_minute
