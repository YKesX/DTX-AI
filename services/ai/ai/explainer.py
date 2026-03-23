"""
XAI explanation generator — MVP stub.

Uses rule-based feature attribution for now.
Replace `explain()` internals with SHAP values once a real model is trained.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../packages"))

from shared.schemas import AnomalyResult, ExplanationResult, EventIn

_THRESHOLDS = {
    "vibration": 10.0,
    "temperature": 75.0,
    "humidity": 85.0,
    "pressure": 1050.0,
}

_RECOMMENDATIONS = {
    "vibration": "Schedule immediate maintenance inspection for the asset.",
    "temperature": "Check cooling system and reduce operational load.",
    "humidity": "Inspect seals and activate dehumidification.",
    "pressure": "Check pneumatic lines for leaks or blockages.",
    "combined": "Multiple sensor readings are elevated — review asset health holistically.",
    "unknown": "Review sensor data and check for calibration issues.",
}


def explain(event: EventIn, anomaly: AnomalyResult) -> ExplanationResult:
    """
    Generate a human-readable explanation for an anomaly result.

    Feature attributions (stub): proportion of each sensor's contribution
    to the total anomaly score.
    TODO: replace with SHAP TreeExplainer / DeepExplainer when model is ready.
    """
    features: dict[str, float] = {}

    sensor_map = {
        "vibration": event.vibration,
        "temperature": event.temperature,
        "humidity": event.humidity,
        "pressure": event.pressure,
    }

    for name, value in sensor_map.items():
        if value is not None and value > _THRESHOLDS[name]:
            # Simple linear attribution stub
            features[name] = round(
                min((value - _THRESHOLDS[name]) / _THRESHOLDS[name], 1.0), 4
            )

    # Normalise attributions to sum to 1
    total = sum(features.values()) or 1.0
    normalised = {k: round(v / total, 4) for k, v in features.items()}

    if not features:
        summary = (
            f"No significant anomaly detected for asset '{event.asset_id}' "
            f"in zone '{event.zone_id}' (score={anomaly.anomaly_score:.2f})."
        )
    else:
        top_feature = max(features, key=lambda k: features[k])
        summary = (
            f"Anomaly detected on asset '{event.asset_id}' in zone '{event.zone_id}'. "
            f"Primary driver: {top_feature} "
            f"(score={anomaly.anomaly_score:.2f}, severity={anomaly.severity.value})."
        )

    recommendation = _RECOMMENDATIONS.get(
        anomaly.anomaly_type.value,
        _RECOMMENDATIONS["unknown"],
    )

    return ExplanationResult(
        event_id=event.event_id,
        summary=summary,
        contributing_features=normalised,
        recommendation=recommendation,
    )
