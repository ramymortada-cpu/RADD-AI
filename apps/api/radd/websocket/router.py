from __future__ import annotations
"""
WebSocket endpoint for agent real-time connection.
Authenticates via JWT query param (browsers can't set WS headers).
"""
import json

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from radd.auth.service import decode_token
from radd.websocket.manager import ws_manager

logger = structlog.get_logger()
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/agent")
async def agent_websocket(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """
    Agent WebSocket endpoint.
    Connect: ws://host/ws/agent?token=<jwt>
    Messages received: presence updates, ping/pong.
    Messages sent: escalation.new, escalation.accepted, conversation.updated, system.alert.
    """
    # Authenticate
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001, reason="Not an access token")
            return
        user_id = payload["sub"]
        workspace_id = payload["workspace_id"]
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    conn = await ws_manager.connect(websocket, user_id, workspace_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await conn.send({"type": "pong"})

            elif msg_type == "presence.update":
                new_status = msg.get("status", "online")
                if new_status in ("online", "away", "offline"):
                    ws_manager.set_presence(workspace_id, user_id, new_status)
                    await ws_manager.broadcast_to_workspace(
                        workspace_id,
                        {"type": "presence.update", "user_id": user_id, "status": new_status},
                        exclude_user=user_id,
                    )

            elif msg_type == "typing":
                # Agent is typing a response in conversation
                conv_id = msg.get("conversation_id", "")
                await ws_manager.broadcast_to_workspace(
                    workspace_id,
                    {"type": "agent.typing", "user_id": user_id, "conversation_id": conv_id},
                    exclude_user=user_id,
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(conn)
        await ws_manager.broadcast_to_workspace(
            workspace_id,
            {"type": "presence.offline", "user_id": user_id},
            exclude_user=user_id,
        )
        logger.info("ws.agent_disconnected", user_id=user_id)
