from __future__ import annotations
"""
WebSocket connection manager.
Tracks per-workspace agent connections.
Broadcasts escalation events, conversation updates, system alerts.
"""
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal

import structlog
from fastapi import WebSocket

logger = structlog.get_logger()

PresenceStatus = Literal["online", "away", "offline"]


class AgentConnection:
    def __init__(self, websocket: WebSocket, user_id: str, workspace_id: str):
        self.websocket = websocket
        self.user_id = user_id
        self.workspace_id = workspace_id
        self.presence: PresenceStatus = "online"
        self.connected_at = datetime.now(timezone.utc)

    async def send(self, data: dict) -> bool:
        """Send JSON message. Returns False if connection is broken."""
        try:
            await self.websocket.send_text(json.dumps(data, default=str))
            return True
        except Exception:
            return False


class WebSocketManager:
    """
    Singleton connection manager.
    Structure: workspace_id → {user_id: [connections]}
    One user can have multiple browser tabs open.
    """

    def __init__(self):
        # workspace_id → list[AgentConnection]
        self._connections: dict[str, list[AgentConnection]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, user_id: str, workspace_id: str) -> AgentConnection:
        await websocket.accept()
        conn = AgentConnection(websocket, user_id, workspace_id)
        self._connections[workspace_id].append(conn)
        logger.info("ws.connected", user_id=user_id, workspace_id=workspace_id)

        # Send presence list to new connection
        await conn.send({
            "type": "presence.list",
            "agents": self._presence_list(workspace_id),
        })

        # Announce to others
        await self.broadcast_to_workspace(
            workspace_id,
            {"type": "presence.online", "user_id": user_id},
            exclude_user=user_id,
        )
        return conn

    def disconnect(self, conn: AgentConnection) -> None:
        workspace_conns = self._connections.get(conn.workspace_id, [])
        if conn in workspace_conns:
            workspace_conns.remove(conn)
        logger.info("ws.disconnected", user_id=conn.user_id, workspace_id=conn.workspace_id)

    async def broadcast_to_workspace(
        self,
        workspace_id: str,
        data: dict,
        exclude_user: str | None = None,
    ) -> int:
        """Broadcast to all agents in a workspace. Returns count of successful sends."""
        conns = self._connections.get(workspace_id, [])
        dead: list[AgentConnection] = []
        sent = 0

        for conn in conns:
            if exclude_user and conn.user_id == exclude_user:
                continue
            ok = await conn.send(data)
            if ok:
                sent += 1
            else:
                dead.append(conn)

        for conn in dead:
            self.disconnect(conn)

        return sent

    async def send_to_user(self, workspace_id: str, user_id: str, data: dict) -> int:
        """Send to all connections for a specific user."""
        conns = [c for c in self._connections.get(workspace_id, []) if c.user_id == user_id]
        dead: list[AgentConnection] = []
        sent = 0
        for conn in conns:
            ok = await conn.send(data)
            if ok:
                sent += 1
            else:
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)
        return sent

    def set_presence(self, workspace_id: str, user_id: str, status: PresenceStatus) -> None:
        for conn in self._connections.get(workspace_id, []):
            if conn.user_id == user_id:
                conn.presence = status

    def _presence_list(self, workspace_id: str) -> list[dict]:
        seen: dict[str, PresenceStatus] = {}
        for conn in self._connections.get(workspace_id, []):
            seen[conn.user_id] = conn.presence
        return [{"user_id": uid, "status": s} for uid, s in seen.items()]

    def online_count(self, workspace_id: str) -> int:
        seen = {c.user_id for c in self._connections.get(workspace_id, [])}
        return len(seen)


# Singleton — imported by escalation router + WS router
ws_manager = WebSocketManager()
