"""XAI explanation generator with tree-model support and graceful fallbacks."""

from __future__ import annotations

from shared.schemas import AnomalyResult, ExplanationResult, EventIn
from ai.model_loader import load_runtime_model

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


def _fallback_explain(event: EventIn, anomaly: AnomalyResult) -> ExplanationResult:
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


def explain(event: EventIn, anomaly: AnomalyResult) -> ExplanationResult:
    runtime = load_runtime_model()
    if runtime.available and runtime.supports_tree_xai and runtime.model is not None:
        try:
            # xai_explainer.py lives under services/ai/, which is on PYTHONPATH
            # in dev/test startup scripts and CI runs.
            from xai_explainer import FEATURES, generate_xai_report

            sensor_values = {
                "Vibration (mm/s)": float(event.vibration or 0.0),
                "Temperature (°C)": float(event.temperature or 0.0),
                "Pressure (bar)": float(event.pressure or 0.0),
            }
            feature_values = {
                "Vibration (mm/s)": sensor_values["Vibration (mm/s)"],
                "Temperature (°C)": sensor_values["Temperature (°C)"],
                "Pressure (bar)": sensor_values["Pressure (bar)"],
                "vib_rolling_mean": sensor_values["Vibration (mm/s)"],
                "vib_rolling_std": 0.0,
                "vib_rolling_max": sensor_values["Vibration (mm/s)"],
                "temp_rolling_mean": sensor_values["Temperature (°C)"],
                "temp_drift": 0.0,
                "pressure_rolling_mean": sensor_values["Pressure (bar)"],
            }
            ordered = [feature_values.get(f, 0.0) for f in runtime.feature_order or FEATURES]
            if runtime.scaler is not None:
                transformed = runtime.scaler.transform([ordered])[0]
            else:
                transformed = ordered
            input_features = {
                (runtime.feature_order or FEATURES)[i]: float(transformed[i])
                for i in range(len(runtime.feature_order or FEATURES))
            }
            class_map = {
                "vibration": "bearing_fault",
                "temperature": "overheating",
                "unknown": "no_fault",
                "combined": "bearing_fault",
                "humidity": "bearing_fault",
                "pressure": "bearing_fault",
            }
            live_json = {
                "timestamp": event.timestamp.isoformat(),
                "anomaly_class": class_map.get(anomaly.anomaly_type.value, "no_fault"),
                "anomaly_score": anomaly.anomaly_score,
                "input_features": input_features,
            }
            report = generate_xai_report(runtime.model, live_json)
            contributing = {
                item["feature"]: float(item.get("shap_value", 0.0))
                for item in report.get("top_features", [])
            }
            return ExplanationResult(
                event_id=event.event_id,
                summary=report.get("explanation_text", ""),
                contributing_features=contributing,
                recommendation=_RECOMMENDATIONS.get(
                    anomaly.anomaly_type.value,
                    _RECOMMENDATIONS["unknown"],
                ),
            )
        except Exception:
            return _fallback_explain(event, anomaly)

    if runtime.available and runtime.family == "lstm_autoencoder_pytorch":
        summary = (
            f"LSTM-AE runtime used for asset '{event.asset_id}'. "
            f"Anomaly score={anomaly.anomaly_score:.2f}, severity={anomaly.severity.value}."
        )
        return ExplanationResult(
            event_id=event.event_id,
            summary=summary,
            contributing_features={},
            recommendation="Review temporal sensor trend and reconstruction error monitor.",
        )

    return _fallback_explain(event, anomaly)
