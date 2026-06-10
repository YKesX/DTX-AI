"""XAI explanation generator with tree-model support and graceful fallbacks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

from shared.schemas import AnomalyResult, EventIn, ExplanationResult
from ai.model_loader import load_runtime_model

_SERVICES_AI_ROOT = Path(__file__).resolve().parents[1]
if str(_SERVICES_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVICES_AI_ROOT))
from preprocessing import FEATURES  # noqa: E402

# Operator-facing recommendation per canonical fault class.
_RECOMMENDATIONS = {
    "nominal": "No action required — asset operating within nominal envelope.",
    "bearing_wear": "Schedule bearing inspection; vibration / power dissipation trending up.",
    "overheat": "Reduce load and verify cooling; temperature and power are both elevated.",
    "overload": "Check payload weight and drive-joint effort against rated capacity.",
    "pressure_fault": "Inspect hydraulic / pneumatic line — pseudo-pressure is out of range.",
    "wheel_slip": "Check tyre/roller traction and surface conditions; roller speeds desynchronised.",
    "unknown": "Review sensor data and check calibration.",
}

# Rule-based attribution thresholds for the fallback explainer — same channels
# as services/ai/ai/detector.py:_RULE_THRESHOLDS, kept independent to allow
# tuning the explainer's "what looks abnormal" view without touching detection.
_ATTRIBUTION_THRESHOLDS = {
    "temperature_c": 40.0,
    "pseudo_pressure_pa": 1000.0,
    "power_dissipated_w": 500.0,
    "vibration_magnitude": 15.0,
}


def _fallback_explain(event: EventIn, anomaly: AnomalyResult) -> ExplanationResult:
    """Rule-based explanation when no model with SHAP support is available."""
    contributions: dict[str, float] = {}
    for name, threshold in _ATTRIBUTION_THRESHOLDS.items():
        value = getattr(event, name, None)
        if value is None:
            continue
        magnitude = abs(value) if name == "pseudo_pressure_pa" else value
        if magnitude > threshold:
            contributions[name] = round(min((magnitude - threshold) / threshold, 1.0), 4)

    total = sum(contributions.values()) or 1.0
    normalised = {k: round(v / total, 4) for k, v in contributions.items()}

    if not contributions:
        summary = (
            f"No significant anomaly detected for asset '{event.asset_id}' "
            f"in zone '{event.zone_id}' (score={anomaly.anomaly_score:.2f})."
        )
    else:
        top_feature = max(contributions, key=lambda k: contributions[k])
        summary = (
            f"Anomaly detected on asset '{event.asset_id}' in zone '{event.zone_id}'. "
            f"Primary driver: {top_feature} "
            f"(score={anomaly.anomaly_score:.2f}, severity={anomaly.severity.value})."
        )

    return ExplanationResult(
        event_id=event.event_id,
        summary=summary,
        contributing_features=normalised,
        recommendation=_RECOMMENDATIONS.get(
            anomaly.anomaly_type.value, _RECOMMENDATIONS["unknown"],
        ),
    )


def _feature_vector(event: EventIn) -> list[float]:
    # NaN for missing sensors, mirroring ai.detector — scaled models impute
    # medians in their pipeline, LightGBM/XGBoost consume NaN natively.
    return [
        float(value) if (value := getattr(event, name)) is not None else float("nan")
        for name in FEATURES
    ]


def explain(event: EventIn, anomaly: AnomalyResult) -> ExplanationResult:
    # Mirror the detector: when the stub is forced, the explanation must come
    # from the rule-based path too — never from a model the detector ignored.
    if os.getenv("DTX_FORCE_STUB", "0") == "1":
        return _fallback_explain(event, anomaly)

    strict_replay = bool(
        os.getenv("DTX_REPLAY_STRICT", "0") == "1"
        or (event.metadata or {}).get("replay_strict") is True
    )
    requested_model = (event.metadata or {}).get("active_model") or os.getenv("DTX_ACTIVE_MODEL")
    runtime = load_runtime_model(
        requested_model=str(requested_model) if requested_model else None,
        strict_selection=strict_replay,
    )

    if runtime.available and runtime.supports_tree_xai and runtime.model is not None:
        try:
            from ai.xai_explainer import generate_xai_report

            ordered = _feature_vector(event)
            feature_names = runtime.feature_order or FEATURES
            input_df = pd.DataFrame([ordered], columns=feature_names)
            if runtime.scaler is not None:
                transformed = runtime.scaler.transform(input_df)[0]
            else:
                transformed = ordered
            input_features = {feature_names[i]: float(transformed[i]) for i in range(len(feature_names))}

            live_json = {
                "timestamp": event.timestamp.isoformat(),
                "anomaly_class": anomaly.anomaly_type.value,
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
                    anomaly.anomaly_type.value, _RECOMMENDATIONS["unknown"],
                ),
            )
        except Exception:
            if strict_replay and hasattr(runtime.model, "feature_importances_"):
                names = runtime.feature_order or FEATURES
                importances = list(getattr(runtime.model, "feature_importances_", []))
                pairs = [
                    (names[i], float(importances[i]))
                    for i in range(min(len(names), len(importances)))
                ]
                pairs = sorted(pairs, key=lambda item: item[1], reverse=True)[:5]
                total = sum(v for _, v in pairs) or 1.0
                normalized = {k: round(v / total, 4) for k, v in pairs}
                return ExplanationResult(
                    event_id=event.event_id,
                    summary=(
                        "Strict replay explanation degraded to model feature_importances_ "
                        "because SHAP generation failed."
                    ),
                    contributing_features=normalized,
                    recommendation=_RECOMMENDATIONS.get(
                        anomaly.anomaly_type.value, _RECOMMENDATIONS["unknown"],
                    ),
                )
            if strict_replay:
                raise
            return _fallback_explain(event, anomaly)

    if runtime.available and runtime.family == "lstm_autoencoder_pytorch":
        summary = (
            f"LSTM-AE runtime used for asset '{event.asset_id}'. "
            f"Predicted class={anomaly.anomaly_type.value}, "
            f"score={anomaly.anomaly_score:.2f}, severity={anomaly.severity.value}."
        )
        return ExplanationResult(
            event_id=event.event_id,
            summary=summary,
            contributing_features={},
            recommendation=_RECOMMENDATIONS.get(
                anomaly.anomaly_type.value, _RECOMMENDATIONS["unknown"],
            ),
        )

    return _fallback_explain(event, anomaly)
