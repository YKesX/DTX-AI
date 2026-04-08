"""Alert log and operator-action routes."""

from fastapi import APIRouter, HTTPException, Query, status

from shared.schemas import AlertActionIn

from api.database import (
    clear_events,
    event_exists,
    fetch_event_actions,
    fetch_operator_states_for_events,
    fetch_recent_events_with_operator_state,
    insert_event_action,
)
from api.live_metrics import live_metrics

router = APIRouter()


@router.get("/")
async def list_alerts(limit: int = Query(default=50, ge=1, le=200)):
    """Return the most recent processed events, newest first."""
    rows = await fetch_recent_events_with_operator_state(limit=limit)
    return {"alerts": rows, "count": len(rows)}


@router.get("/{event_id}/actions")
async def list_alert_actions(event_id: str):
    """Return action history plus derived operator state for one alert."""
    if not await event_exists(event_id):
        raise HTTPException(status_code=404, detail="Alert event not found")

    actions = await fetch_event_actions(event_id)
    state = (await fetch_operator_states_for_events([event_id])).get(
        event_id,
        {
            "operator_status": "new",
            "assigned_to": "",
            "last_action": None,
            "last_action_at": None,
        },
    )
    return {"event_id": event_id, "state": state, "actions": actions}


@router.post("/{event_id}/actions", status_code=status.HTTP_201_CREATED)
async def create_alert_action(event_id: str, payload: AlertActionIn):
    """Persist a new operator action for an alert event."""
    if not await event_exists(event_id):
        raise HTTPException(status_code=404, detail="Alert event not found")

    assignee = payload.assignee.strip() if payload.action_type.value == "assign" else ""
    action = await insert_event_action(
        event_id=event_id,
        action_type=payload.action_type.value,
        note=payload.note.strip(),
        assignee=assignee,
    )
    state = (await fetch_operator_states_for_events([event_id])).get(
        event_id,
        {
            "operator_status": "new",
            "assigned_to": "",
            "last_action": None,
            "last_action_at": None,
        },
    )
    return {"event_id": event_id, "action": action, "state": state}


@router.delete("/clear")
async def clear_alerts():
    """Clear persisted event logs and reset live replay metrics."""
    deleted = await clear_events()
    live_metrics.reset()
    return {"deleted": deleted, "metrics_reset": True}
