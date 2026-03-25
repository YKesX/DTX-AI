"""Runtime anomaly detector backed by model registry with safe fallbacks."""

from __future__ import annotations

import os
from collections import deque

from shared.schemas import AnomalyResult, AnomalyType, EventIn, Severity

from ai.model_loader import RuntimeModel, load_runtime_model

# Thresholds for the rule-based stub
_THRESHOLDS = {
    "vibration": 10.0,   # mm/s²
    "temperature": 75.0, # °C
    "humidity": 85.0,    # %
    "pressure": 1050.0,  # hPa (upper bound)
}

_ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "0.5"))
_WINDOW_BUFFER: dict[str, deque] = {}
_WINDOW_SIZE = 5

_CLASS_MAP = {
    0: (AnomalyType.UNKNOWN, Severity.INFO),
    1: (AnomalyType.VIBRATION, Severity.WARNING),
    2: (AnomalyType.TEMPERATURE, Severity.CRITICAL),
}
_SEVERITY_WEIGHT = {
    Severity.INFO: 0,
    Severity.WARNING: 1,
    Severity.CRITICAL: 2,
}


def _event_to_raw_features(event: EventIn) -> dict[str, float]:
    return {
        "Vibration (mm/s)": float(event.vibration or 0.0),
        "Temperature (°C)": float(event.temperature or 0.0),
        "Pressure (bar)": float(event.pressure or 0.0),
    }


def _build_window_features(event: EventIn, feature_order: list[str]) -> list[float]:
    key = f"{event.asset_id}:{event.zone_id}"
    if key not in _WINDOW_BUFFER:
        _WINDOW_BUFFER[key] = deque(maxlen=_WINDOW_SIZE)

    raw = _event_to_raw_features(event)
    history = _WINDOW_BUFFER[key]
    history.append(raw)
    rows = list(history)

    vibration_values = [r["Vibration (mm/s)"] for r in rows]
    temp_values = [r["Temperature (°C)"] for r in rows]
    pressure_values = [r["Pressure (bar)"] for r in rows]

    vib_last = vibration_values[-1]
    temp_last = temp_values[-1]
    pressure_last = pressure_values[-1]
    vib_mean = sum(vibration_values) / len(vibration_values)
    temp_mean = sum(temp_values) / len(temp_values)
    pressure_mean = sum(pressure_values) / len(pressure_values)
    if len(vibration_values) > 1:
        variance = sum((v - vib_mean) ** 2 for v in vibration_values) / len(vibration_values)
        vib_std = variance**0.5
    else:
        vib_std = 0.0

    return [
        vib_last,
        temp_last,
        pressure_last,
        vib_mean,
        vib_std,
        max(vibration_values),
        temp_mean,
        temp_last - temp_values[0],
        pressure_mean,
    ][: len(feature_order) or 9]


def _run_tree_model(event: EventIn, runtime: RuntimeModel) -> AnomalyResult:
    if runtime.model is None:
        return _rule_based_detect(event)

    features = _build_window_features(event, runtime.feature_order)
    x = [features]
    if runtime.scaler is not None:
        x = runtime.scaler.transform(x)

    model = runtime.model
    pred_class = int(model.predict(x)[0])
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(x)[0]
        anomaly_score = float(max(probs[1:])) if len(probs) > 1 else float(probs[0])
    else:
        anomaly_score = float(pred_class != 0)

    anomaly_type, severity = _CLASS_MAP.get(pred_class, (AnomalyType.COMBINED, Severity.WARNING))
    is_anomaly = pred_class != 0 and anomaly_score >= 0.3
    if not is_anomaly:
        anomaly_type, severity = AnomalyType.UNKNOWN, Severity.INFO

    return AnomalyResult(
        event_id=event.event_id,
        anomaly_score=round(min(max(anomaly_score, 0.0), 1.0), 4),
        is_anomaly=is_anomaly,
        anomaly_type=anomaly_type,
        severity=severity,
    )


def _merge_with_guardrails(primary: AnomalyResult, fallback: AnomalyResult) -> AnomalyResult:
    if fallback.is_anomaly and not primary.is_anomaly:
        return fallback

    if not fallback.is_anomaly and primary.is_anomaly:
        return primary

    if fallback.is_anomaly and primary.is_anomaly:
        anomaly_type = (
            fallback.anomaly_type
            if fallback.anomaly_type != AnomalyType.UNKNOWN
            else primary.anomaly_type
        )
        severity = (
            primary.severity
            if _SEVERITY_WEIGHT[primary.severity] >= _SEVERITY_WEIGHT[fallback.severity]
            else fallback.severity
        )
        return AnomalyResult(
            event_id=primary.event_id,
            anomaly_score=max(primary.anomaly_score, fallback.anomaly_score),
            is_anomaly=True,
            anomaly_type=anomaly_type,
            severity=severity,
        )

    return fallback


def _run_lstm_autoencoder(event: EventIn, runtime: RuntimeModel) -> AnomalyResult:
    threshold = runtime.metadata.get("default_threshold")
    if threshold is None:
        return _rule_based_detect(event)

    try:
        import torch
    except Exception:
        return _rule_based_detect(event)

    features = _build_window_features(event, runtime.feature_order)
    x = [features]
    if runtime.scaler is not None:
        x = runtime.scaler.transform(x)
    tensor = torch.tensor(x, dtype=torch.float32).unsqueeze(1)

    model = runtime.model
    if model is None:
        return _rule_based_detect(event)

    with torch.no_grad():
        reconstructed = model(tensor)
        mse = float(torch.mean((reconstructed - tensor) ** 2).item())

    t = float(threshold)
    is_anomaly = mse >= t
    anomaly_score = 1.0 if is_anomaly and t <= 0 else min(mse / t, 1.0)
    severity = Severity.CRITICAL if anomaly_score >= 0.8 else Severity.WARNING if is_anomaly else Severity.INFO

    return AnomalyResult(
        event_id=event.event_id,
        anomaly_score=round(min(max(anomaly_score, 0.0), 1.0), 4),
        is_anomaly=is_anomaly,
        anomaly_type=AnomalyType.COMBINED if is_anomaly else AnomalyType.UNKNOWN,
        severity=severity,
    )


def _rule_based_detect(event: EventIn) -> AnomalyResult:
    """Rule-based detector kept as fallback when registry model is unavailable."""
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


def detect(event: EventIn) -> AnomalyResult:
    if os.getenv("DTX_FORCE_STUB", "0") == "1":
        return _rule_based_detect(event)

    if all(value is None for value in (event.vibration, event.temperature, event.humidity, event.pressure)):
        return _rule_based_detect(event)

    fallback = _rule_based_detect(event)
    runtime = load_runtime_model()
    if not runtime.available:
        return fallback

    if runtime.family in {"lightgbm", "random_forest", "xgboost"}:
        try:
            return _merge_with_guardrails(_run_tree_model(event, runtime), fallback)
        except Exception:
            return fallback

    if runtime.family == "lstm_autoencoder_pytorch":
        try:
            return _merge_with_guardrails(_run_lstm_autoencoder(event, runtime), fallback)
        except Exception:
            return fallback

    return fallback
