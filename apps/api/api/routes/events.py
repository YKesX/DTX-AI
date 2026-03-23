"""POST /events — accepts warehouse sensor events and runs the AI pipeline."""

from fastapi import APIRouter, HTTPException, status

from shared.schemas import (
    EventIn,
    AnomalyResult,
    ExplanationResult,
    DashboardAlert,
    TwinUpdate,
    AssetStatus,
)
from api.database import insert_event
from api.ws_manager import manager

router = APIRouter()


def _build_twin_update(event: EventIn, anomaly: AnomalyResult) -> TwinUpdate:
    status_map = {
        "critical": AssetStatus.FAULT,
        "warning": AssetStatus.DEGRADED,
        "info": AssetStatus.NORMAL,
    }
    return TwinUpdate(
        event_id=event.event_id,
        asset_id=event.asset_id,
        zone_id=event.zone_id,
        new_status=status_map.get(anomaly.severity.value, AssetStatus.NORMAL),
        severity=anomaly.severity,
        label=f"{anomaly.anomaly_type.value} / score={anomaly.anomaly_score:.2f}",
    )


@router.post("/", status_code=status.HTTP_202_ACCEPTED, response_model=DashboardAlert)
async def ingest_event(event: EventIn):
    """
    Accept a warehouse sensor event, run anomaly detection and XAI,
    persist the result, broadcast to WebSocket clients, and trigger
    the Isaac Sim adapter.
    """
    # Lazy import to keep services/ai decoupled
    try:
        from ai.pipeline import run_pipeline
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"AI pipeline unavailable: {exc}",
        ) from exc

    anomaly, explanation = await run_pipeline(event)

    alert = DashboardAlert(event=event, anomaly=anomaly, explanation=explanation)

    # Persist
    await insert_event(
        {
            "event_id": event.event_id,
            "asset_id": event.asset_id,
            "zone_id": event.zone_id,
            "timestamp": event.timestamp,
            "anomaly_score": anomaly.anomaly_score,
            "is_anomaly": anomaly.is_anomaly,
            "anomaly_type": anomaly.anomaly_type.value,
            "severity": anomaly.severity.value,
            "summary": explanation.summary,
            "raw_payload": event.model_dump(mode="json"),
        }
    )

    # Broadcast to dashboard
    await manager.broadcast(alert.model_dump(mode="json"))

    # Trigger digital-twin update (fire-and-forget; sim may not be running)
    twin_update = _build_twin_update(event, anomaly)
    _try_notify_sim(twin_update)

    return alert


def _try_notify_sim(update: TwinUpdate) -> None:
    """
    Attempt to notify the Isaac Sim adapter.
    Silently skips if the adapter is not installed or reachable.
    """
    try:
        from sim.adapter import notify  # type: ignore[import]
        notify(update)
    except Exception:
        # Sim is optional — do not fail the API request
        pass
