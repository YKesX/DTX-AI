"""POST /positions - receives entity position updates and moves them in Isaac Sim."""

from fastapi import APIRouter
from shared.schemas import PositionUpdate
from api.ws_manager import manager

router = APIRouter()

# Son pozisyonları bellekte tut (entity_id dict)
_latest: dict[str, dict] = {}

@router.post("/", status_code=202)
async def update_position(pos: PositionUpdate):
    payload = {
        "type": "position_update",
        "entity_id": pos.entity_id,
        "entity_type": pos.entity_type,
        "x": pos.x,
        "y": pos.y,
        "z": pos.z,
        "heading": pos.heading,
        "zone_id": pos.zone_id,
        "timestamp": pos.timestamp.isoformat(),
    }
    # Bellekte sakla
    _latest[pos.entity_id] = payload
    # WebSocket'e gönder
    await manager.broadcast(payload)
    # Isaac Sim'e gönder
    _try_move_entity(pos)
    return {"status": "accepted", "entity_id": pos.entity_id}

@router.get("/latest")
async def get_latest_positions():
    """Isaac Sim listener'ı buradan poll eder."""
    return list(_latest.values())

def _try_move_entity(pos: PositionUpdate) -> None:
    try:
        from sim.adapter import move_entity
        move_entity(pos)
    except Exception:
        pass