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
    if intent != "order_status":
        return None

    from radd.actions.salla import extract_order_number, get_order_status, format_order_status_response

    order_number = extract_order_number(message)
    if not order_number:
        return None  # No order number — fall through to RAG

    salla_token = workspace_config.get("salla_access_token", "")
    if not salla_token:
        return None  # Salla not configured — fall through to template

    order_data = await get_order_status(order_number, salla_token)
    response = format_order_status_response(order_data, dialect)

    return ActionResult(
        action="order_status",
        response_text=response,
        data=order_data,
    )
