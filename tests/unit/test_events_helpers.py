import os
import sys
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../apps/api"))

from shared.schemas import AnomalyResult, AnomalyType, EventIn, Severity  # noqa: E402
from api.routes.events import (  # noqa: E402
    _anomaly_type_to_label,
    _build_twin_update,
    _normalize_gt_label,
)


def test_anomaly_type_to_label_maps_known_and_unknown_values():
    assert _anomaly_type_to_label("bearing_wear") == "bearing_wear"
    assert _anomaly_type_to_label("nominal") == "nominal"
    assert _anomaly_type_to_label("unknown") == "nominal"
    assert _anomaly_type_to_label("mystery_fault") == "unknown"


def test_normalize_gt_label_handles_numeric_alias_and_passthrough_values():
    assert _normalize_gt_label("1") == "bearing_wear"
    assert _normalize_gt_label(" normal ") == "nominal"
    assert _normalize_gt_label("NO_FAULT") == "nominal"
    assert _normalize_gt_label("wheel_slip") == "wheel_slip"
    assert _normalize_gt_label("novel_fault") == "novel_fault"


def test_build_twin_update_maps_warning_to_degraded_and_formats_label():
    event = EventIn(asset_id="forklift-01", zone_id="zone-A")
    anomaly = AnomalyResult(
        event_id=event.event_id,
        anomaly_score=0.8765,
        is_anomaly=True,
        anomaly_type=AnomalyType.BEARING_WEAR,
        severity=Severity.WARNING,
    )

    update = _build_twin_update(event, anomaly)

    assert update.event_id == event.event_id
    assert update.asset_id == "forklift-01"
    assert update.zone_id == "zone-A"
    assert update.new_status.value == "degraded"
    assert update.label == "bearing_wear / score=0.88"


def test_build_twin_update_defaults_unknown_severity_to_normal_status():
    event = EventIn(asset_id="forklift-02", zone_id="zone-B")
    anomaly = AnomalyResult(
        event_id=uuid4(),
        anomaly_score=0.1,
        is_anomaly=False,
        anomaly_type=AnomalyType.NOMINAL,
        severity=Severity.INFO,
    )

    update = _build_twin_update(event, anomaly)

    assert update.new_status.value == "normal"
