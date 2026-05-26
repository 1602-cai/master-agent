"""WebSocket routes and broadcast helper."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from harness.ws_manager import manager

router = APIRouter()


async def ws_event_broadcast(job_id: str, event_dict: dict):
    """Broadcast the raw persisted HarnessEvent to the frontend.

    WS and historical replay share the same event contract.
    The frontend owns the single event-to-UI projection path.
    """
    await manager.broadcast(job_id, {
        "type": "harness_event",
        "job_id": job_id,
        "event": event_dict,
    })


@router.websocket("/ws/progress/{job_id}")
async def ws_progress(ws: WebSocket, job_id: str):
    """WebSocket endpoint for real-time progress push."""
    from routes.deps import runtime

    await manager.connect(job_id, ws)
    try:
        job = runtime().get_job(job_id)
        status = job.get("status", "pending") if job else "unknown"
        if status == "waiting_for_user":
            status = "confirming"

        await ws.send_text(json.dumps({
            "type": "connected",
            "job_id": job_id,
            "status": status,
        }, ensure_ascii=False))

        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30)
                if data == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                try:
                    await ws.send_text(json.dumps({"type": "pong"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect(job_id, ws)
