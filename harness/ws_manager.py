"""WebSocket connection manager for real-time progress broadcast."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per job_id."""

    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, job_id: str, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(job_id, []).append(ws)
        log.info("[WS] Client connected to job %s (%d total)",
                 job_id, len(self.connections[job_id]))

    def disconnect(self, job_id: str, ws: WebSocket):
        if job_id in self.connections:
            try:
                self.connections[job_id].remove(ws)
            except ValueError:
                pass
            if not self.connections[job_id]:
                del self.connections[job_id]

    async def broadcast(self, job_id: str, message: dict[str, Any]):
        """Send a JSON message to all clients watching this job."""
        if job_id not in self.connections:
            return
        data = json.dumps(message, ensure_ascii=False, default=str)
        dead: list[WebSocket] = []
        for ws in list(self.connections.get(job_id, [])):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            try:
                self.connections[job_id].remove(ws)
            except ValueError:
                pass
        if job_id in self.connections and not self.connections[job_id]:
            del self.connections[job_id]


manager = ConnectionManager()
