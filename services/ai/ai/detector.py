"""Runtime anomaly detector backed by the model registry with rule-based fallback."""

from __future__ import annotations

import collections
import os
import sys
from pathlib import Path

import pandas as pd

from shared.schemas import AnomalyResult, AnomalyType, EventIn, Severity

# preprocessing.py owns the FEATURES list and CLASS_NAMES — single source of truth.
_SERVICES_AI_ROOT = Path(__file__).resolve().parents[1]
if str(_SERVICES_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVICES_AI_ROOT))
from preprocessing import CLASS_NAMES, FEATURES  # noqa: E402

from ai.model_loader import RuntimeModel, load_runtime_model

_ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "0.5"))


# Each class id → (AnomalyType, default Severity). Order must match
# preprocessing.CLASS_NAMES so the model's argmax → AnomalyType lookup stays
# correct without a name-based round-trip.
def _build_class_map() -> dict[int, tuple[AnomalyType, Severity]]:
    severity_for = {
        "nominal":        Severity.INFO,
        "bearing_wear":   Severity.WARNING,
        "overheat":       Severity.CRITICAL,
        "overload":       Severity.WARNING,
        "pressure_fault": Severity.WARNING,
        "wheel_slip":     Severity.WARNING,
    }
    out: dict[int, tuple[AnomalyType, Severity]] = {}
    for idx, name in enumerate(CLASS_NAMES):
        out[idx] = (AnomalyType(name), severity_for.get(name, Severity.WARNING))
    return out


_CLASS_MAP = _build_class_map()

_SEVERITY_WEIGHT = {
    Severity.INFO: 0,
    Severity.WARNING: 1,
    Severity.CRITICAL: 2,
}


# Rule-based thresholds derived from per-class means in the training data
# (see docs/isaac_sim_integration.md §2.x for the full ranges).
_RULE_THRESHOLDS = {
    "temperature_c": 40.0,       # nominal ~25, overheat ~49, wheel_slip ~52
    "pseudo_pressure_pa": 1000.0,  # nominal ~4, overheat ~2487, pressure_fault ~-8558
    "power_dissipated_w": 500.0,  # nominal ~0, overheat ~1966, wheel_slip ~1158
    "vibration_magnitude": 15.0,  # nominal ~9.8, faults around the same — weak signal
}

# CNN requires sliding window buffer to accumulate 30 timesteps of context.
# Buffer lifecycle:
#  - Production (default): accumulates streaming sensor events, CNN uses full 30-step context
#  - Testing (strict_replay): buffer bypassed, single-event evaluation for determinism
#  - Dashboard/demo: reset_cnn_buffer() called before test suite
_CNN_BUFFER = collections.deque(maxlen=30)
_BILSTM_BUFFER = collections.deque(maxlen=30)


def reset_all_buffers() -> None:
    """Clear all deep learning buffers for testing or dashboard use. Call before non-production workflows."""
    _CNN_BUFFER.clear()
    _BILSTM_BUFFER.clear()


def _feature_vector(event: EventIn) -> list[float]:
    """Extract the 19 sensor channels in canonical FEATURES order.

    Missing sensors become NaN — scaled models impute medians inside their
    pipeline and LightGBM/XGBoost consume NaN natively, exactly matching how
    the models were trained on the dataset's real sensor dropouts.
    """
    return [
        float(value) if (value := getattr(event, name)) is not None else float("nan")
        for name in FEATURES
    ]


def _feature_columns(runtime: RuntimeModel, feature_count: int) -> list[str]:
    if runtime.feature_order:
        return runtime.feature_order[:feature_count]
    scaler_names = getattr(runtime.scaler, "feature_names_in_", None)
    if scaler_names is not None:
        return [str(n) for n in list(scaler_names)[:feature_count]]
    return FEATURES[:feature_count]


def _build_model_input_df(features: list[float], runtime: RuntimeModel) -> pd.DataFrame:
    columns = _feature_columns(runtime, len(features))
    return pd.DataFrame([features], columns=columns)


def _run_tree_model(event: EventIn, runtime: RuntimeModel) -> AnomalyResult:
    if runtime.model is None:
        return _rule_based_detect(event)

    features = _feature_vector(event)
    x = _build_model_input_df(features, runtime)
    if runtime.scaler is not None:
        x = runtime.scaler.transform(x)
        x = pd.DataFrame(x, columns=_feature_columns(runtime, x.shape[1]))

    model = runtime.model
    
    # TabNet explicitly requires numpy arrays; tree models use DataFrames.
    x_input = x.values if runtime.family == "tabnet_pytorch" else x

    pred_class = int(model.predict(x_input)[0])
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(x_input)[0]
        anomaly_score = float(max(probs[1:])) if len(probs) > 1 else float(probs[0])
    else:
        anomaly_score = float(pred_class != 0)

    anomaly_type, severity = _CLASS_MAP.get(pred_class, (AnomalyType.UNKNOWN, Severity.WARNING))
    threshold = runtime.metadata.get("default_threshold")
    threshold = float(threshold) if threshold is not None else _ANOMALY_THRESHOLD
    is_anomaly = pred_class != 0 and anomaly_score >= threshold
    if not is_anomaly:
        anomaly_type, severity = AnomalyType.NOMINAL, Severity.INFO

    return AnomalyResult(
        event_id=event.event_id,
        anomaly_score=round(min(max(anomaly_score, 0.0), 1.0), 4),
        is_anomaly=is_anomaly,
        anomaly_type=anomaly_type,
        severity=severity,
    )


def _run_lstm_autoencoder(event: EventIn, runtime: RuntimeModel) -> AnomalyResult:
    try:
        import torch
        import torch.nn.functional as F
    except Exception:
        return _rule_based_detect(event)

    model = runtime.model
    if model is None:
        return _rule_based_detect(event)

    features = _feature_vector(event)
    x = _build_model_input_df(features, runtime)
    if runtime.scaler is not None:
        x_array = runtime.scaler.transform(x)
    else:
        x_array = x.values
    tensor = torch.tensor(x_array, dtype=torch.float32).unsqueeze(1)

    with torch.no_grad():
        out = model(tensor)
        if not isinstance(out, tuple) or len(out) != 2:
            raise RuntimeError(
                "LSTM-AE checkpoint does not expose a classification head. "
                "Retrain via scripts/train_models.py against ai.lstm_classifier."
            )
        reconstructed, logits = out
        probs = F.softmax(logits, dim=-1)[0]
        pred_class = int(torch.argmax(probs).item())
        class_confidence = float(probs[pred_class].item())
        mse = float(torch.mean((reconstructed - tensor) ** 2).item())

    anomaly_type, severity = _CLASS_MAP.get(pred_class, (AnomalyType.UNKNOWN, Severity.WARNING))
    threshold = runtime.metadata.get("default_threshold")
    threshold = float(threshold) if threshold is not None else _ANOMALY_THRESHOLD
    is_anomaly = pred_class != 0 and class_confidence >= threshold
    if not is_anomaly:
        anomaly_type, severity = AnomalyType.NOMINAL, Severity.INFO

    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    metadata["lstm_predicted_class"] = pred_class
    metadata["lstm_class_confidence"] = round(class_confidence, 6)
    metadata["lstm_reconstruction_mse"] = round(mse, 6)
    metadata["lstm_raw_logits"] = {
        str(i): round(float(lg.item()), 6) for i, lg in enumerate(logits[0])
    }
    event.metadata = metadata

    return AnomalyResult(
        event_id=event.event_id,
        anomaly_score=round(min(max(class_confidence, 0.0), 1.0), 4),
        is_anomaly=is_anomaly,
        anomaly_type=anomaly_type,
        severity=severity,
    )


def _run_cnn_model(event: EventIn, runtime: RuntimeModel) -> AnomalyResult:
    try:
        import torch
        import torch.nn.functional as F
    except Exception:
        return _rule_based_detect(event)

    model = runtime.model
    if model is None:
        return _rule_based_detect(event)

    features = _feature_vector(event)

    # Window size used both for production buffer and for replay_history validation.
    window_size = int(runtime.metadata.get("best_params", {}).get("window", 30))

    # Strict replay mode: use an isolated replay_history provided by the caller
    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    strict_replay = bool(
        os.getenv("DTX_REPLAY_STRICT", "0") == "1"
        or metadata.get("replay_strict") is True
    )

    if strict_replay:
        # Expect caller to pass an isolated history matching training window length.
        replay_history = metadata.get("replay_history")
        if not replay_history or len(replay_history) < window_size:
            # Test didn't provide sufficient history: fall back to rule-based detector
            return _rule_based_detect(event)

        # Use the last `window_size` rows from the provided history only — do NOT touch global buffer.
        history_data = replay_history[-window_size:]
        x_history = pd.DataFrame(history_data, columns=_feature_columns(runtime, len(features)))
        if runtime.scaler is not None:
            x_array = runtime.scaler.transform(x_history)
        else:
            x_array = x_history.values

        tensor = torch.tensor(x_array, dtype=torch.float32).unsqueeze(0)
        # Debug metadata for tests/dashboards
        metadata["cnn_used_replay_history"] = True
        metadata["cnn_replay_history_len"] = len(replay_history)
    else:
        # Production mode: accumulate sliding window context.
        _CNN_BUFFER.append(features)

        if len(_CNN_BUFFER) < window_size:
            # Insufficient context: model trained on window steps. Fall back to rules.
            return _rule_based_detect(event)

        x_history = pd.DataFrame(list(_CNN_BUFFER), columns=_feature_columns(runtime, len(features)))
        if runtime.scaler is not None:
            x_array = runtime.scaler.transform(x_history)
        else:
            x_array = x_history.values

        # Shape: [1, window_size, features] — exactly as trained in train_models.py.
        tensor = torch.tensor(x_array, dtype=torch.float32).unsqueeze(0)

    with torch.no_grad():
        logits = model(tensor)
        probs = F.softmax(logits, dim=-1)[0]
        pred_class = int(torch.argmax(probs).item())
        class_confidence = float(probs[pred_class].item())

    anomaly_type, severity = _CLASS_MAP.get(pred_class, (AnomalyType.UNKNOWN, Severity.WARNING))
    threshold = runtime.metadata.get("default_threshold")
    threshold = float(threshold) if threshold is not None else _ANOMALY_THRESHOLD
    is_anomaly = pred_class != 0 and class_confidence >= threshold
    if not is_anomaly:
        anomaly_type, severity = AnomalyType.NOMINAL, Severity.INFO

    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    metadata["cnn_predicted_class"] = pred_class
    metadata["cnn_class_confidence"] = round(class_confidence, 6)
    metadata["cnn_raw_logits"] = {
        str(i): round(float(lg.item()), 6) for i, lg in enumerate(logits[0])
    }
    if not strict_replay:
        metadata["cnn_buffer_size"] = len(_CNN_BUFFER)  # Debug: show accumulated context
    event.metadata = metadata

    return AnomalyResult(
        event_id=event.event_id,
        anomaly_score=round(min(max(class_confidence, 0.0), 1.0), 4),
        is_anomaly=is_anomaly,
        anomaly_type=anomaly_type,
        severity=severity,
    )


def _run_bilstm_model(event: EventIn, runtime: RuntimeModel) -> AnomalyResult:
    try:
        import torch
        import torch.nn.functional as F
    except Exception:
        return _rule_based_detect(event)

    model = runtime.model
    if model is None:
        return _rule_based_detect(event)

    features = _feature_vector(event)
    window_size = int(runtime.metadata.get("best_params", {}).get("window", 30))
    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    strict_replay = bool(
        os.getenv("DTX_REPLAY_STRICT", "0") == "1"
        or metadata.get("replay_strict") is True
    )

    if strict_replay:
        replay_history = metadata.get("replay_history")
        if not replay_history or len(replay_history) < window_size:
            return _rule_based_detect(event)
        history_data = replay_history[-window_size:]
        x_history = pd.DataFrame(history_data, columns=_feature_columns(runtime, len(features)))
        if runtime.scaler is not None:
            x_array = runtime.scaler.transform(x_history)
        else:
            x_array = x_history.values
            
        tensor = torch.tensor(x_array, dtype=torch.float32).unsqueeze(0)
        metadata["bilstm_used_replay_history"] = True
        metadata["bilstm_replay_history_len"] = len(replay_history)
    else:
        _BILSTM_BUFFER.append(features)
        if len(_BILSTM_BUFFER) < window_size:
            return _rule_based_detect(event)
        x_history = pd.DataFrame(list(_BILSTM_BUFFER), columns=_feature_columns(runtime, len(features)))
        if runtime.scaler is not None:
            x_array = runtime.scaler.transform(x_history)
        else:
            x_array = x_history.values
            
        tensor = torch.tensor(x_array, dtype=torch.float32).unsqueeze(0)

    with torch.no_grad():
        logits = model(tensor)
        probs = F.softmax(logits, dim=-1)[0]
        pred_class = int(torch.argmax(probs).item())
        class_confidence = float(probs[pred_class].item())

    anomaly_type, severity = _CLASS_MAP.get(pred_class, (AnomalyType.UNKNOWN, Severity.WARNING))
    threshold = runtime.metadata.get("default_threshold")
    threshold = float(threshold) if threshold is not None else _ANOMALY_THRESHOLD
    is_anomaly = pred_class != 0 and class_confidence >= threshold
    if not is_anomaly:
        anomaly_type, severity = AnomalyType.NOMINAL, Severity.INFO

    metadata["bilstm_predicted_class"] = pred_class
    metadata["bilstm_class_confidence"] = round(class_confidence, 6)
    if not strict_replay:
        metadata["bilstm_buffer_size"] = len(_BILSTM_BUFFER)
    event.metadata = metadata

    return AnomalyResult(
        event_id=event.event_id,
        anomaly_score=round(min(max(class_confidence, 0.0), 1.0), 4),
        is_anomaly=is_anomaly,
        anomaly_type=anomaly_type,
        severity=severity,
    )


def _merge_with_guardrails(primary: AnomalyResult, fallback: AnomalyResult) -> AnomalyResult:
    """Combine model output with rule-based fallback. Same contract as before."""
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


def _rule_based_detect(event: EventIn) -> AnomalyResult:
    """Threshold-based fallback used when no model is loadable.

    Picks the dominant abnormal channel and maps it to the nearest fault class.
    Severity scales with how many channels are above threshold.
    """
    scores: dict[str, float] = {}

    temp = event.temperature_c
    if temp is not None and temp > _RULE_THRESHOLDS["temperature_c"]:
        scores["temperature_c"] = min((temp - _RULE_THRESHOLDS["temperature_c"]) / 20.0, 1.0)

    pressure = event.pseudo_pressure_pa
    if pressure is not None and abs(pressure) > _RULE_THRESHOLDS["pseudo_pressure_pa"]:
        scores["pseudo_pressure_pa"] = min(
            (abs(pressure) - _RULE_THRESHOLDS["pseudo_pressure_pa"]) / 5000.0, 1.0,
        )

    power = event.power_dissipated_w
    if power is not None and power > _RULE_THRESHOLDS["power_dissipated_w"]:
        scores["power_dissipated_w"] = min(
            (power - _RULE_THRESHOLDS["power_dissipated_w"]) / 1500.0, 1.0,
        )

    vibration = event.vibration_magnitude
    if vibration is not None and vibration > _RULE_THRESHOLDS["vibration_magnitude"]:
        scores["vibration_magnitude"] = min(
            (vibration - _RULE_THRESHOLDS["vibration_magnitude"]) / 5.0, 1.0,
        )

    anomaly_score = min(sum(scores.values()), 1.0)
    is_anomaly = anomaly_score >= _ANOMALY_THRESHOLD

    # Coarse mapping from dominant rule-channel → AnomalyType.
    if scores:
        dominant = max(scores, key=lambda k: scores[k])
        anomaly_type = {
            "temperature_c": AnomalyType.OVERHEAT,
            "pseudo_pressure_pa": AnomalyType.PRESSURE_FAULT,
            "power_dissipated_w": AnomalyType.OVERLOAD,
            "vibration_magnitude": AnomalyType.BEARING_WEAR,
        }.get(dominant, AnomalyType.UNKNOWN)
    else:
        anomaly_type = AnomalyType.NOMINAL

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

    # If every sensor is None, the rule-based detector is the only sensible answer.
    if all(getattr(event, name) is None for name in FEATURES):
        return _rule_based_detect(event)

    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    requested_model = metadata.get("active_model") or os.getenv("DTX_ACTIVE_MODEL")
    strict_replay = bool(
        os.getenv("DTX_REPLAY_STRICT", "0") == "1"
        or metadata.get("replay_strict") is True
    )

    fallback = _rule_based_detect(event)
    runtime = load_runtime_model(
        requested_model=str(requested_model) if requested_model else None,
        strict_selection=strict_replay,
    )

    metadata["requested_model"] = str(requested_model) if requested_model else runtime.key
    metadata["runtime_model"] = runtime.key
    metadata["runtime_model_family"] = runtime.family
    metadata["runtime_model_available"] = bool(runtime.available)
    if runtime.reason:
        metadata["runtime_model_reason"] = runtime.reason
    event.metadata = metadata

    if strict_replay and not runtime.available:
        raise RuntimeError(
            f"Strict replay mode enabled and model is unavailable: {runtime.reason or runtime.key}"
        )

    if not runtime.available:
        return fallback

    if runtime.family in {"lightgbm", "random_forest", "xgboost", "tabnet_pytorch"}:
        try:
            result = _run_tree_model(event, runtime)
            return result
        except Exception:
            if strict_replay:
                raise
            return fallback

    if runtime.family == "cnn_pytorch":
        try:
            result = _run_cnn_model(event, runtime)
            return result
        except Exception:
            if strict_replay:
                raise
            return fallback

    if runtime.family == "bilstm_pytorch":
        try:
            result = _run_bilstm_model(event, runtime)
            return result
        except Exception:
            if strict_replay:
                raise
            return fallback

    if runtime.family == "lstm_autoencoder_pytorch":
        if strict_replay and not runtime.metadata.get("class_mapping"):
            raise RuntimeError(
                "Strict replay mode requires LSTM-AE metadata.class_mapping for multi-class output."
            )
        try:
            result = _run_lstm_autoencoder(event, runtime)
            return result
        except Exception:
            if strict_replay:
                raise
            return fallback

    if strict_replay:
        raise RuntimeError(f"Strict replay mode does not support model family '{runtime.family}'")
    return fallback
