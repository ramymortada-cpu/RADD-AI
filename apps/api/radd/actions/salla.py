from __future__ import annotations
"""
Salla API integration.
get_order_status: fetches real order data and formats Arabic response.
"""
import re

import httpx
import structlog

logger = structlog.get_logger()

SALLA_API_BASE = "https://api.salla.dev/admin/v2"

ORDER_STATUS_AR = {
    "pending": "قيد الانتظار",
    "processing": "جاري التجهيز",
    "in_transit": "في الطريق إليك",
    "delivered": "تم التسليم",
    "canceled": "ملغي",
    "refunded": "مسترجع",
    "on_hold": "موقوف مؤقتاً",
    "incomplete": "غير مكتمل",
}


async def get_order_status(
    order_reference: str,
    access_token: str,
) -> dict:
    """
    Fetch order status from Salla API.
    Returns structured order data or error dict.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Try by reference number first
            response = await client.get(
                f"{SALLA_API_BASE}/orders",
                headers=headers,
                params={"reference_id": order_reference, "per_page": 1},
            )
            response.raise_for_status()
            data = response.json()

            orders = data.get("data", [])
            if not orders:
                return {"found": False, "reference": order_reference}

            order = orders[0]
            status_key = order.get("status", {}).get("slug", "")
            status_ar = ORDER_STATUS_AR.get(status_key, status_key)

            shipping = order.get("shipping", {})
            tracking = shipping.get("tracking_number", "")
            carrier = shipping.get("company", {}).get("name", "")
            estimated = shipping.get("estimated_delivery", "")

            return {
                "found": True,
                "order_id": str(order.get("id", "")),
                "reference": order_reference,
                "status": status_key,
                "status_ar": status_ar,
                "tracking_number": tracking,
                "carrier": carrier,
                "estimated_delivery": estimated,
                "total": order.get("amounts", {}).get("total", {}).get("formatted", ""),
            }

        except httpx.HTTPStatusError as e:
            logger.warning("salla.http_error", status=e.response.status_code, ref=order_reference)
            return {"found": False, "error": "api_error", "reference": order_reference}
        except Exception as e:
            logger.error("salla.fetch_failed", error=str(e), ref=order_reference)
            return {"found": False, "error": "network_error", "reference": order_reference}


def format_order_status_response(order_data: dict, dialect: str = "msa") -> str:
    """Format Salla order data into an Arabic response string."""
    if not order_data.get("found"):
        if dialect == "gulf":
            return "ما قدرت أجد طلبك. تأكد من رقم الطلب وحاول مرة ثانية أو تواصل معنا."
        elif dialect == "egyptian":
            return "مش لاقي الطلب ده. تأكد من رقم الطلب وحاول تاني أو كلمنا."
        else:
            return "لم أتمكن من العثور على طلبك. يرجى التأكد من رقم الطلب والمحاولة مجدداً."

    status_ar = order_data.get("status_ar", "")
    tracking = order_data.get("tracking_number", "")
    carrier = order_data.get("carrier", "")
    estimated = order_data.get("estimated_delivery", "")
    ref = order_data.get("reference", "")

    if dialect == "gulf":
        msg = f"طلبك رقم {ref} حالته: {status_ar}."
        if tracking:
            msg += f" رقم التتبع: {tracking}"
            if carrier:
                msg += f" ({carrier})"
            msg += "."
        if estimated:
            msg += f" التوصيل المتوقع: {estimated}."
    elif dialect == "egyptian":
        msg = f"طلبك رقم {ref} حالته: {status_ar}."
        if tracking:
            msg += f" رقم التتبع: {tracking}"
            if carrier:
                msg += f" عن طريق {carrier}"
            msg += "."
        if estimated:
            msg += f" التوصيل المتوقع: {estimated}."
    else:
        msg = f"طلبك رقم {ref} — الحالة: {status_ar}."
        if tracking:
            msg += f" رقم التتبع: {tracking}"
            if carrier:
                msg += f" ({carrier})"
            msg += "."
        if estimated:
            msg += f" الوصول المتوقع: {estimated}."

    return msg


def extract_order_number(text: str) -> str | None:
    """
    Extract order/reference number from Arabic message.
    Matches patterns like: 12345, #12345, رقم 12345, طلب 12345
    Also handles Arabic-Indic numerals (٠-٩).
    """
    # Normalize Arabic-Indic to Western digits
    arabic_indic = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    text_normalized = text.translate(arabic_indic)

    patterns = [
        r"(?:رقم|طلب|order|#)\s*(\d{4,10})",
        r"\b(\d{5,10})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_normalized, re.IGNORECASE)
        if match:
            return match.group(1)
    return None
