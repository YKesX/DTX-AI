"""POST /events — accepts warehouse sensor events and runs the AI pipeline."""

import sys
from pathlib import Path

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
from api.live_metrics import live_metrics
from api.ws_manager import manager

router = APIRouter()


def _anomaly_type_to_label(anomaly_type: str) -> str:
    """Map AnomalyType.value → canonical fault_label string used everywhere
    downstream (live_metrics keys, dashboard tags, replay comparisons)."""
    mapping = {
        "unknown": "nominal",
        # 6-class canonical identities (match preprocessing.CLASS_NAMES)
        "nominal": "nominal",
        "bearing_wear": "bearing_wear",
        "overheat": "overheat",
        "overload": "overload",
        "pressure_fault": "pressure_fault",
        "wheel_slip": "wheel_slip",
    }
    return mapping.get(anomaly_type, "unknown")


# Maps numeric class codes (as emitted by dataset CSVs) and any human aliases
# to the canonical fault_label name so ground-truth ↔ prediction comparisons
# in the replay flow line up cleanly. Identity entries ensure already-canonical
# values pass through unchanged after lowercasing/stripping.
_GT_LABEL_MAP: dict[str, str] = {
    # Numeric class codes — order matches preprocessing.CLASS_NAMES.
    "0": "nominal",
    "1": "bearing_wear",
    "2": "overheat",
    "3": "overload",
    "4": "pressure_fault",
    "5": "wheel_slip",
    # Canonical names — identity.
    "nominal": "nominal",
    "bearing_wear": "bearing_wear",
    "overheat": "overheat",
    "overload": "overload",
    "pressure_fault": "pressure_fault",
    "wheel_slip": "wheel_slip",
    # Common human aliases.
    "normal": "nominal",
    "no_fault": "nominal",
}


def _normalize_gt_label(raw: str) -> str:
    """Translate a raw ground-truth label to a canonical label name.

    Handles numeric class codes (e.g. ``"1"``), human-readable aliases
    (e.g. ``"normal"``, ``"vibration"``), and already-canonical names
    (e.g. ``"bearing_fault"``).  Any value not found in the map is returned
    as-is (lowercased and stripped) so that novel labels surface rather than
    being silently swallowed.
    """
    key = str(raw).strip().lower()
    return _GT_LABEL_MAP.get(key, key)


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
        # Fallback when API is started without scripts that set PYTHONPATH.
        repo_root = Path(__file__).resolve().parents[4]
        ai_runtime_path = str(repo_root / "services" / "ai")
        if ai_runtime_path not in sys.path:
            sys.path.insert(0, ai_runtime_path)
        try:
            from ai.pipeline import run_pipeline
        except ImportError as inner_exc:
            raise HTTPException(
                status_code=500,
                detail=f"AI pipeline unavailable: {inner_exc}",
            ) from inner_exc

    anomaly, explanation = await run_pipeline(event)

    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    source = str(metadata.get("source", ""))
    predicted_label = _anomaly_type_to_label(anomaly.anomaly_type.value)
    metadata["predicted_label"] = predicted_label
    metadata["predicted_anomaly_type"] = anomaly.anomaly_type.value
    metadata["predicted_is_anomaly"] = bool(anomaly.is_anomaly)
    metadata["predicted_score"] = float(anomaly.anomaly_score)
    metadata["recommendation"] = explanation.recommendation

    if source == "dataset_replay":
        gt_raw = str(
            metadata.get("ground_truth_name")
            or metadata.get("ground_truth_label")
            or "unknown"
        )
        gt_name = _normalize_gt_label(gt_raw)
        correct = gt_name == predicted_label
        metadata["prediction_correct"] = correct
        live_metrics.update(
            ground_truth=gt_name,
            predicted=predicted_label,
            correct=correct,
            model_key=str(metadata.get("runtime_model") or metadata.get("active_model") or "unknown"),
        )

    event.metadata = metadata

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
