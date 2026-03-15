"""
Cart Recovery Funnel — 3-step WhatsApp sequence for abandoned carts.

Flow:
1. After 1 hour: Friendly reminder
2. After 24 hours: Urgency (limited stock)
3. After 48 hours: Discount code (last chance)

Stops immediately if customer completes purchase.

Usage:
    from radd.sales.cart_recovery import CartRecoveryFunnel

    funnel = CartRecoveryFunnel()
    await funnel.trigger(
        workspace_id="...",
        customer_phone="+966...",
        customer_name="فهد",
        cart_items=[{"name": "عطر فاخر", "price": 250, "quantity": 1}],
        cart_total=250,
        cart_url="https://store.salla.sa/cart/abc123",
        store_name="متجر النور",
        dialect="gulf",
    )
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from enum import Enum

import redis.asyncio as aioredis

from radd.config import settings

logger = logging.getLogger("radd.sales.cart_recovery")

QUEUE_NAME = "cart_recovery_queue"


class FunnelStep(str, Enum):
    REMINDER = "reminder"  # Step 1: after 1 hour
    URGENCY = "urgency"  # Step 2: after 24 hours
    DISCOUNT = "discount"  # Step 3: after 48 hours


class CartRecoveryMessages:
    """Generate cart recovery messages in the customer's dialect."""

    @staticmethod
    def reminder(
        customer_name: str,
        cart_items: list,
        store_name: str,
        dialect: str = "gulf",
    ) -> str:
        """Step 1: Friendly reminder (after 1 hour)."""
        items_text = "، ".join([item.get("name", "منتج") for item in cart_items[:3]])

        if dialect == "gulf":
            return (
                f"أهلاً {customer_name}! 👋\n\n"
                f"لاحظنا إنك ما كملت طلبك من {store_name}.\n"
                f"عندك في السلة: {items_text}\n\n"
                f"هل واجهتك مشكلة؟ نقدر نساعدك تكمل الطلب 🛒"
            )
        elif dialect == "egyptian":
            return (
                f"أهلاً {customer_name}! 👋\n\n"
                f"لاحظنا إنك مكملتش الطلب من {store_name}.\n"
                f"عندك في السلة: {items_text}\n\n"
                f"واجهتك مشكلة؟ نقدر نساعدك تكمل الطلب 🛒"
            )
        else:  # MSA
            return (
                f"مرحباً {customer_name}! 👋\n\n"
                f"لاحظنا أنك لم تكمل طلبك من {store_name}.\n"
                f"لديك في السلة: {items_text}\n\n"
                f"هل واجهتك مشكلة؟ يمكننا مساعدتك لإتمام الطلب 🛒"
            )

    @staticmethod
    def urgency(
        customer_name: str,
        cart_items: list,
        store_name: str,
        dialect: str = "gulf",
    ) -> str:
        """Step 2: Create urgency (after 24 hours)."""
        first_item = cart_items[0].get("name", "المنتج") if cart_items else "المنتج"

        if dialect == "gulf":
            return (
                f"مرحباً {customer_name} 🔔\n\n"
                f"{first_item} اللي عجبك من {store_name} لسا متوفر — بس الكمية محدودة!\n\n"
                f"لا يفوتك — كمّل طلبك الحين قبل ما يخلص ⏳"
            )
        elif dialect == "egyptian":
            return (
                f"مرحباً {customer_name} 🔔\n\n"
                f"{first_item} اللي عجبك من {store_name} لسه متوفر — بس الكمية محدودة!\n\n"
                f"متفوتش الفرصة — كمّل طلبك دلوقتي ⏳"
            )
        else:
            return (
                f"مرحباً {customer_name} 🔔\n\n"
                f"{first_item} الذي أعجبك من {store_name} لا يزال متوفراً — لكن الكمية محدودة!\n\n"
                f"أكمل طلبك الآن قبل نفاد الكمية ⏳"
            )

    @staticmethod
    def discount(
        customer_name: str,
        store_name: str,
        discount_code: str = "COMEBACK10",
        discount_percent: int = 10,
        dialect: str = "gulf",
    ) -> str:
        """Step 3: Discount offer (after 48 hours)."""

        if dialect == "gulf":
            return (
                f"آخر فرصة يا {customer_name}! 🎁\n\n"
                f"عشانك من عملاء {store_name} المميزين — جهزنا لك خصم {discount_percent}%\n\n"
                f"استخدم كود: *{discount_code}*\n\n"
                f"العرض ينتهي خلال 24 ساعة ⏰"
            )
        elif dialect == "egyptian":
            return (
                f"آخر فرصة يا {customer_name}! 🎁\n\n"
                f"عشانك من عملاء {store_name} المميزين — جهزنالك خصم {discount_percent}%\n\n"
                f"استخدم كود: *{discount_code}*\n\n"
                f"العرض بينتهي خلال 24 ساعة ⏰"
            )
        else:
            return (
                f"فرصة أخيرة يا {customer_name}! 🎁\n\n"
                f"بصفتك من عملاء {store_name} المميزين — أعددنا لك خصماً بنسبة {discount_percent}%\n\n"
                f"استخدم الكود: *{discount_code}*\n\n"
                f"ينتهي العرض خلال 24 ساعة ⏰"
            )


class CartRecoveryFunnel:
    """Manages the 3-step cart recovery sequence."""

    async def trigger(
        self,
        workspace_id: str,
        customer_phone: str,
        customer_name: str,
        cart_items: list,
        cart_total: float,
        store_name: str,
        dialect: str = "gulf",
        cart_url: str = "",
        discount_code: str = "COMEBACK10",
        discount_percent: int = 10,
        redis_url: str = "",
    ) -> dict:
        """
        Start the cart recovery funnel.
        Schedules 3 messages at 1h, 24h, and 48h.

        Returns dict with funnel_id and scheduled steps.
        """
        if not redis_url:
            redis_url = settings.redis_url

        now = datetime.now(timezone.utc)
        funnel_id = f"cart_{workspace_id}_{customer_phone}_{now.strftime('%Y%m%d%H%M%S')}"

        steps = [
            {
                "funnel_id": funnel_id,
                "step": FunnelStep.REMINDER.value,
                "workspace_id": workspace_id,
                "customer_phone": customer_phone,
                "customer_name": customer_name,
                "store_name": store_name,
                "dialect": dialect,
                "cart_items": cart_items,
                "cart_total": cart_total,
                "cart_url": cart_url,
                "discount_code": discount_code,
                "discount_percent": discount_percent,
                "scheduled_at": (now + timedelta(hours=1)).isoformat(),
                "created_at": now.isoformat(),
            },
            {
                "funnel_id": funnel_id,
                "step": FunnelStep.URGENCY.value,
                "workspace_id": workspace_id,
                "customer_phone": customer_phone,
                "customer_name": customer_name,
                "store_name": store_name,
                "dialect": dialect,
                "cart_items": cart_items,
                "cart_total": cart_total,
                "cart_url": cart_url,
                "scheduled_at": (now + timedelta(hours=24)).isoformat(),
                "created_at": now.isoformat(),
            },
            {
                "funnel_id": funnel_id,
                "step": FunnelStep.DISCOUNT.value,
                "workspace_id": workspace_id,
                "customer_phone": customer_phone,
                "customer_name": customer_name,
                "store_name": store_name,
                "dialect": dialect,
                "cart_items": cart_items,
                "cart_total": cart_total,
                "cart_url": cart_url,
                "discount_code": discount_code,
                "discount_percent": discount_percent,
                "scheduled_at": (now + timedelta(hours=48)).isoformat(),
                "created_at": now.isoformat(),
            },
        ]

        try:
            r = aioredis.from_url(redis_url, decode_responses=True)

            for step in steps:
                await r.lpush(QUEUE_NAME, json.dumps(step, ensure_ascii=False))

            # Store funnel state for cancellation
            await r.set(
                f"funnel:{funnel_id}:active",
                "true",
                ex=60 * 60 * 72,  # 72 hours TTL
            )

            await r.aclose()

            logger.info("Cart recovery funnel started: %s, 3 steps scheduled", funnel_id)

            return {
                "success": True,
                "funnel_id": funnel_id,
                "steps_scheduled": 3,
                "customer_phone": customer_phone,
            }

        except Exception as e:
            logger.error("Failed to start cart recovery funnel: %s", e)
            return {"success": False, "error": str(e)}

    async def cancel(self, funnel_id: str, redis_url: str = "") -> bool:
        """Cancel an active funnel (e.g., customer completed purchase)."""
        if not redis_url:
            redis_url = settings.redis_url

        try:
            r = aioredis.from_url(redis_url, decode_responses=True)
            await r.set(f"funnel:{funnel_id}:active", "false")
            await r.aclose()
            logger.info("Funnel cancelled: %s", funnel_id)
            return True
        except Exception as e:
            logger.error("Failed to cancel funnel %s: %s", funnel_id, e)
            return False

    def generate_message(self, step: str, **kwargs) -> str:
        """Generate the message text for a given step."""
        if step == FunnelStep.REMINDER.value:
            return CartRecoveryMessages.reminder(
                customer_name=kwargs.get("customer_name", ""),
                cart_items=kwargs.get("cart_items", []),
                store_name=kwargs.get("store_name", ""),
                dialect=kwargs.get("dialect", "gulf"),
            )
        elif step == FunnelStep.URGENCY.value:
            return CartRecoveryMessages.urgency(
                customer_name=kwargs.get("customer_name", ""),
                cart_items=kwargs.get("cart_items", []),
                store_name=kwargs.get("store_name", ""),
                dialect=kwargs.get("dialect", "gulf"),
            )
        elif step == FunnelStep.DISCOUNT.value:
            return CartRecoveryMessages.discount(
                customer_name=kwargs.get("customer_name", ""),
                store_name=kwargs.get("store_name", ""),
                discount_code=kwargs.get("discount_code", "COMEBACK10"),
                discount_percent=kwargs.get("discount_percent", 10),
                dialect=kwargs.get("dialect", "gulf"),
            )
        return ""
