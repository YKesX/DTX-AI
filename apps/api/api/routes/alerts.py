"""GET /alerts — returns recent event log entries."""

from fastapi import APIRouter, Query

from api.database import fetch_recent_events

router = APIRouter()


@router.get("/")
async def list_alerts(limit: int = Query(default=50, ge=1, le=200)):
    """Return the most recent processed events, newest first."""
    rows = await fetch_recent_events(limit=limit)
    return {"alerts": rows, "count": len(rows)}
