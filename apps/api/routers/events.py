"""
events router
─────────────
POST /events       Accept a sensor event, run the AI stub, store & broadcast.
GET  /events       Return the last 50 processed results.
WS   /ws/events    Stream AnomalyResult JSON to all connected dashboard clients.
"""

from __future__ import annotations

import json
from collections import deque
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from schemas.events import AnomalyResult, EventIn
from services.ai_stub import process_event

router = APIRouter()

# ── In-memory store ────────────────────────────────────────────────────────────

_results: deque[dict[str, Any]] = deque(maxlen=50)


# ── WebSocket connection manager ───────────────────────────────────────────────

class _ConnectionManager:
    def __init__(self) -> None:
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients = [c for c in self._clients if c is not ws]

    async def broadcast(self, payload: dict[str, Any]) -> None:
        message = json.dumps(payload, default=str)
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


_manager = _ConnectionManager()


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/events", response_model=AnomalyResult, status_code=201)
async def ingest_event(event: EventIn) -> AnomalyResult:
    """
    Process an incoming sensor event through the AI stub and return
    an AnomalyResult. The result is stored in memory and broadcast
    to all connected WebSocket clients.
    """
    result = process_event(event)
    payload = result.model_dump(mode="json")
    _results.appendleft(payload)
    await _manager.broadcast(payload)
    return result


@router.get("/events", response_model=list[AnomalyResult])
async def list_events() -> list[dict[str, Any]]:
    """Return the last 50 processed anomaly results (newest first)."""
    return list(_results)


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    """
    WebSocket endpoint.  Connect to receive real-time AnomalyResult JSON
    objects whenever POST /events is called.
    """
    await _manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive; discard any client ping frames.
            await websocket.receive_text()
    except WebSocketDisconnect:
        _manager.disconnect(websocket)
