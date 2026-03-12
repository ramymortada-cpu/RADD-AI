from __future__ import annotations
"""Action protocol + dispatcher. Detects when pipeline should call external APIs."""
from dataclasses import dataclass


@dataclass
class ActionResult:
    action: str           # "order_status" | "none"
    response_text: str    # Pre-formatted Arabic response
    data: dict            # Raw API response for logging


async def detect_and_run_action(
    intent: str,
    message: str,
    dialect: str,
    workspace_config: dict,
) -> ActionResult | None:
    """
    Check if an intent maps to an external action. If so, run it.
    Returns ActionResult if action was taken, None if no action applies.
    """
    salla_token = workspace_config.get("salla_access_token", "")

    # ── Order Status ──────────────────────────────────────────────────────────
    if intent == "order_status":
        from radd.actions.salla import extract_order_number, get_order_status, format_order_status_response
        order_number = extract_order_number(message)
        if not order_number or not salla_token:
            return None

        order_data = await get_order_status(order_number, salla_token)
        response = format_order_status_response(order_data, dialect)
        return ActionResult(action="order_status", response_text=response, data=order_data)

    # ── Shipping Tracking ─────────────────────────────────────────────────────
    if intent == "shipping":
        from radd.actions.salla import extract_order_number
        from radd.actions.salla_advanced import track_shipment, format_tracking_response
        order_number = extract_order_number(message)
        if not order_number or not salla_token:
            return None

        result = await track_shipment(order_number, salla_token)
        if result.get("found") and result.get("tracking_number"):
            response = format_tracking_response(result, dialect)
            return ActionResult(action="track_shipment", response_text=response, data=result)
        return None

    # ── Cancel Order ──────────────────────────────────────────────────────────
    cancel_keywords = ["ألغي", "الغاء", "إلغاء", "ابغى الغي", "ابي الغي", "عايز الغي"]
    if any(kw in message for kw in cancel_keywords):
        from radd.actions.salla import extract_order_number
        from radd.actions.salla_advanced import cancel_order, format_cancel_response
        order_number = extract_order_number(message)
        if order_number and salla_token:
            result = await cancel_order(order_number, salla_token)
            response = format_cancel_response(result, dialect)
            return ActionResult(action="cancel_order", response_text=response, data=result)

    # ── Create Return ─────────────────────────────────────────────────────────
    return_keywords = ["أرجع", "إرجاع", "ارجع", "ابي ارجع", "ابغى ارجع", "عايز ارجع", "طلب إرجاع", "استرجاع"]
    if any(kw in message for kw in return_keywords):
        from radd.actions.salla import extract_order_number
        from radd.actions.salla_advanced import create_return_request, format_return_response
        order_number = extract_order_number(message)
        if order_number and salla_token:
            result = await create_return_request(order_number, salla_token)
            if result.get("success"):
                response = format_return_response(result, dialect)
                return ActionResult(action="create_return", response_text=response, data=result)

    return None
