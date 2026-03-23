"""WebSocket /ws/events — pushes DashboardAlert messages to connected clients."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.ws_manager import manager

router = APIRouter()


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    """
    Connect to receive real-time DashboardAlert JSON objects.

    The server pushes a message every time POST /events produces an alert.
    No client-to-server messages are expected in the MVP.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive; discard any client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
