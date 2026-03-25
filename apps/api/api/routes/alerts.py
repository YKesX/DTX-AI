"""GET /alerts — returns recent event log entries."""

from fastapi import APIRouter, Query

from api.database import clear_events, fetch_recent_events
from api.live_metrics import live_metrics

router = APIRouter()


@router.get("/")
async def list_alerts(limit: int = Query(default=50, ge=1, le=200)):
    """Return the most recent processed events, newest first."""
    rows = await fetch_recent_events(limit=limit)
    return {"alerts": rows, "count": len(rows)}


@router.delete("/clear")
async def clear_alerts():
    """Clear persisted event logs and reset live replay metrics."""
    deleted = await clear_events()
    live_metrics.reset()
    return {"deleted": deleted, "metrics_reset": True}
