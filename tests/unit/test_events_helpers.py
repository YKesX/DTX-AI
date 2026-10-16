import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../apps/api"))

from api.routes.events import (  # noqa: E402
    _anomaly_type_to_label,
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
