from __future__ import annotations
"""
Advanced Salla Actions: Cancel Order + Track Shipment
Extends the base Salla action with write operations.
"""
import httpx
import structlog

logger = structlog.get_logger()

SALLA_API_BASE = "https://api.salla.dev/admin/v2"

CANCEL_REASONS = {
    "change_mind": "غيّرت رأيي",
    "wrong_item": "طلبت غلط",
    "price": "السعر",
    "delivery_delay": "تأخر التوصيل",
    "other": "سبب آخر",
}

SHIPPING_TRACKING_URLS = {
    "aramex": "https://www.aramex.com/track/results?ShipmentNumber=",
    "smsa": "https://www.smsaexpress.com/en/tracktrace?tracknumbers=",
    "naqel": "https://naqelexpress.com/en/tracking?trackno=",
    "j&t": "https://www.jtexpress.sa/index/query/gcp.html?bills=",
    "dhl": "https://www.dhl.com/sa-en/home/tracking.html?tracking-id=",
}


async def cancel_order(
    order_reference: str,
    access_token: str,
    reason: str = "change_mind",
) -> dict:
    """
    Cancel a Salla order by reference number.
    Returns structured result dict.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # First find the order by reference
            search_resp = await client.get(
                f"{SALLA_API_BASE}/orders",
                headers=headers,
                params={"reference_id": order_reference, "per_page": 1},
            )
            search_resp.raise_for_status()
            orders = search_resp.json().get("data", [])

            if not orders:
                return {"success": False, "error": "not_found", "reference": order_reference}

            order = orders[0]
            order_id = order.get("id")
            status = order.get("status", {}).get("slug", "")

            # Check if order can be cancelled
            if status in ("delivered", "canceled", "refunded"):
                return {
                    "success": False,
                    "error": "cannot_cancel",
                    "status": status,
                    "reference": order_reference,
                }

            # Cancel the order
            cancel_resp = await client.post(
                f"{SALLA_API_BASE}/orders/{order_id}/cancel",
                headers=headers,
                json={"reason": reason},
            )

            if cancel_resp.status_code in (200, 201, 204):
                return {
                    "success": True,
                    "order_id": str(order_id),
                    "reference": order_reference,
                    "reason": reason,
                }
            else:
                return {
                    "success": False,
                    "error": "api_rejected",
                    "status_code": cancel_resp.status_code,
                    "reference": order_reference,
                }

        except Exception as e:
            logger.error("salla.cancel_failed", error=str(e), ref=order_reference)
            return {"success": False, "error": "network_error", "reference": order_reference}


async def track_shipment(
    order_reference: str,
    access_token: str,
) -> dict:
    """
    Get real shipment tracking info from Salla + tracking URL.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{SALLA_API_BASE}/orders",
                headers=headers,
                params={"reference_id": order_reference, "per_page": 1},
            )
            resp.raise_for_status()
            orders = resp.json().get("data", [])

            if not orders:
                return {"found": False, "reference": order_reference}

            order = orders[0]
            shipping = order.get("shipping", {})
            tracking_number = shipping.get("tracking_number", "")
            carrier_name = (shipping.get("company") or {}).get("name", "").lower()
            carrier_display = (shipping.get("company") or {}).get("name", "")
            estimated = shipping.get("estimated_delivery", "")
            status = order.get("status", {}).get("slug", "")

            # Build tracking URL
            tracking_url = ""
            for key, base_url in SHIPPING_TRACKING_URLS.items():
                if key in carrier_name:
                    tracking_url = f"{base_url}{tracking_number}"
                    break

            return {
                "found": True,
                "reference": order_reference,
                "tracking_number": tracking_number,
                "carrier": carrier_display,
                "tracking_url": tracking_url,
                "estimated_delivery": estimated,
                "status": status,
            }

        except Exception as e:
            logger.error("salla.track_failed", error=str(e), ref=order_reference)
            return {"found": False, "error": "network_error", "reference": order_reference}


def format_cancel_response(result: dict, dialect: str = "gulf") -> str:
    """Format cancel order result as Arabic message."""
    ref = result.get("reference", "")

    if result.get("success"):
        msgs = {
            "gulf": f"تم إلغاء طلبك رقم {ref} بنجاح. سيتم استرداد المبلغ خلال 3-5 أيام عمل.",
            "egyptian": f"تم إلغاء طلبك رقم {ref} بنجاح. هيتم استرداد المبلغ خلال 3-5 أيام عمل.",
            "msa": f"تم إلغاء طلبك رقم {ref} بنجاح. سيتم استرداد المبلغ خلال 3-5 أيام عمل.",
        }
        return msgs.get(dialect, msgs["gulf"])

    error = result.get("error", "")
    if error == "not_found":
        msgs = {
            "gulf": f"ما قدرت أجد طلب برقم {ref}. تأكد من الرقم.",
            "egyptian": f"مش لاقي طلب برقم {ref}. تأكد من الرقم.",
            "msa": f"لم أجد طلباً برقم {ref}. تأكد من الرقم.",
        }
        return msgs.get(dialect, msgs["gulf"])

    if error == "cannot_cancel":
        status = result.get("status", "")
        msgs = {
            "gulf": f"للأسف ما يمكن إلغاء طلب رقم {ref} لأن حالته '{status}'.",
            "egyptian": f"لأسف مش ممكن إلغاء طلب رقم {ref} لأن حالته '{status}'.",
            "msa": f"لا يمكن إلغاء الطلب رقم {ref} لأن حالته الحالية '{status}'.",
        }
        return msgs.get(dialect, msgs["gulf"])

    msgs = {
        "gulf": "صارت مشكلة أثناء الإلغاء. سأحولك لفريقنا.",
        "egyptian": "حصل مشكلة في الإلغاء. هحولك للفريق.",
        "msa": "حدث خطأ أثناء الإلغاء. سيتولى فريقنا مساعدتك.",
    }
    return msgs.get(dialect, msgs["gulf"])


def format_tracking_response(result: dict, dialect: str = "gulf") -> str:
    """Format shipment tracking result as Arabic message."""
    if not result.get("found"):
        msgs = {
            "gulf": "ما قدرت أجد بيانات الشحن. تأكد من رقم الطلب.",
            "egyptian": "مش لاقي بيانات الشحن. تأكد من رقم الطلب.",
            "msa": "لم أجد بيانات الشحن لهذا الطلب.",
        }
        return msgs.get(dialect, msgs["gulf"])

    tracking = result.get("tracking_number", "")
    carrier = result.get("carrier", "")
    estimated = result.get("estimated_delivery", "")
    url = result.get("tracking_url", "")

    if dialect == "gulf":
        msg = f"شحنتك"
        if carrier:
            msg += f" مع {carrier}"
        if tracking:
            msg += f" — رقم التتبع: {tracking}"
        if estimated:
            msg += f"\nالتوصيل المتوقع: {estimated}"
        if url:
            msg += f"\nتابع شحنتك مباشرة: {url}"
    elif dialect == "egyptian":
        msg = f"شحنتك"
        if carrier:
            msg += f" مع {carrier}"
        if tracking:
            msg += f" — رقم التتبع: {tracking}"
        if estimated:
            msg += f"\nالتوصيل المتوقع: {estimated}"
        if url:
            msg += f"\nتابع شحنتك: {url}"
    else:
        msg = f"معلومات الشحن"
        if carrier:
            msg += f" ({carrier})"
        if tracking:
            msg += f"\nرقم التتبع: {tracking}"
        if estimated:
            msg += f"\nموعد التسليم المتوقع: {estimated}"
        if url:
            msg += f"\nرابط التتبع: {url}"

    return msg
