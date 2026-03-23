"""
Anomaly detector — MVP synthetic rule-based stub.

Replace the body of `detect()` with a trained model (Isolation Forest,
Autoencoder, etc.) without changing the function signature.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../packages"))

from shared.schemas import AnomalyResult, AnomalyType, Severity, EventIn

# Thresholds for the rule-based stub
_THRESHOLDS = {
    "vibration": 10.0,   # mm/s²
    "temperature": 75.0, # °C
    "humidity": 85.0,    # %
    "pressure": 1050.0,  # hPa (upper bound)
}

_ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "0.5"))


def detect(event: EventIn) -> AnomalyResult:
    """
    Score an event and return an AnomalyResult.

    Scoring logic (stub):
    - Each sensor reading that exceeds its threshold contributes a fixed
      weight to the anomaly_score.
    - Score is normalised to [0, 1].
    - TODO: replace with a trained Isolation Forest or Autoencoder.
    """
    scores: dict[str, float] = {}

    if event.vibration is not None and event.vibration > _THRESHOLDS["vibration"]:
        scores["vibration"] = min(event.vibration / _THRESHOLDS["vibration"] - 1.0, 1.0)

    if event.temperature is not None and event.temperature > _THRESHOLDS["temperature"]:
        scores["temperature"] = min(
            (event.temperature - _THRESHOLDS["temperature"]) / 25.0, 1.0
        )

    if event.humidity is not None and event.humidity > _THRESHOLDS["humidity"]:
        scores["humidity"] = min(
            (event.humidity - _THRESHOLDS["humidity"]) / 15.0, 1.0
        )

    if event.pressure is not None and event.pressure > _THRESHOLDS["pressure"]:
        scores["pressure"] = min(
            (event.pressure - _THRESHOLDS["pressure"]) / 50.0, 1.0
        )

    anomaly_score = min(sum(scores.values()), 1.0)
    is_anomaly = anomaly_score >= _ANOMALY_THRESHOLD

    # Determine dominant anomaly type
    if scores:
        dominant = max(scores, key=lambda k: scores[k])
        try:
            anomaly_type = AnomalyType(dominant)
        except ValueError:
            anomaly_type = AnomalyType.COMBINED if len(scores) > 1 else AnomalyType.UNKNOWN
    else:
        anomaly_type = AnomalyType.UNKNOWN

    # Map score to severity
    if anomaly_score >= 0.8:
        severity = Severity.CRITICAL
    elif anomaly_score >= 0.5:
        severity = Severity.WARNING
    else:
        severity = Severity.INFO

    return AnomalyResult(
        event_id=event.event_id,
        anomaly_score=round(anomaly_score, 4),
        is_anomaly=is_anomaly,
        anomaly_type=anomaly_type,
        severity=severity,
    )
