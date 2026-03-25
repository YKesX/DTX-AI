from typing import Dict, List, Any

import numpy as np
import pandas as pd
import shap


FEATURES = [
    "Vibration (mm/s)",
    "Temperature (°C)",
    "Pressure (bar)",
    "vib_rolling_mean",
    "vib_rolling_std",
    "vib_rolling_max",
    "temp_rolling_mean",
    "temp_drift",
    "pressure_rolling_mean",
]

CLASS_DISPLAY_MAP = {
    "no_fault": "Normal",
    "bearing_fault": "Vibration Anomaly",
    "overheating": "Temperature Anomaly",
}

CLASS_INDEX_MAP = {
    "no_fault": 0,
    "bearing_fault": 1,
    "overheating": 2,
}

FEATURE_DISPLAY_MAP = {
    "Vibration (mm/s)": "current vibration",
    "Temperature (°C)": "current temperature",
    "Pressure (bar)": "current pressure",
    "vib_rolling_mean": "average vibration",
    "vib_rolling_std": "vibration fluctuation",
    "vib_rolling_max": "peak vibration",
    "temp_rolling_mean": "average temperature",
    "temp_drift": "temperature drift",
    "pressure_rolling_mean": "average pressure",
}


def _format_feature_name(feature_name: str) -> str:
    return FEATURE_DISPLAY_MAP.get(feature_name, feature_name)


def _get_severity(anomaly_class: str, anomaly_score: float) -> str:
    if anomaly_class == "no_fault":
        return "info"
    if anomaly_score >= 0.85:
        return "critical"
    if anomaly_score >= 0.60:
        return "warning"
    return "caution"


def _build_input_dataframe(input_features: Dict[str, Any]) -> pd.DataFrame:
    missing = [feature for feature in FEATURES if feature not in input_features]
    if missing:
        raise ValueError(f"Missing required input feature(s): {missing}")

    row = {feature: input_features[feature] for feature in FEATURES}
    return pd.DataFrame([row], columns=FEATURES)


def _extract_class_shap_values(shap_output: Any, class_idx: int) -> np.ndarray:
    """
    Handles different SHAP output formats for tree-based models.
    Returns 1D SHAP values for the selected class and single sample.
    """
    values = shap_output.values if hasattr(shap_output, "values") else shap_output

    if isinstance(values, list):
        class_values = np.asarray(values[class_idx])[0]
        return np.abs(class_values)

    values = np.asarray(values)

    if values.ndim == 3:
        if values.shape[2] == len(CLASS_INDEX_MAP):
            class_values = values[0, :, class_idx]
            return np.abs(class_values)

        if values.shape[1] == len(CLASS_INDEX_MAP):
            class_values = values[0, class_idx, :]
            return np.abs(class_values)

        raise ValueError(f"Unsupported 3D SHAP output shape: {values.shape}")

    if values.ndim == 2:
        class_values = values[0]
        return np.abs(class_values)

    if values.ndim == 1:
        return np.abs(values)

    raise ValueError(f"Unsupported SHAP output shape: {values.shape}")


def _compute_top_features(
    model: Any,
    input_features: Dict[str, Any],
    anomaly_class: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    # input_features are already scaled by the inference pipeline
    X_scaled_df = _build_input_dataframe(input_features)

    explainer = shap.TreeExplainer(model)
    shap_output = explainer.shap_values(X_scaled_df)

    class_idx = CLASS_INDEX_MAP.get(anomaly_class, 0)
    shap_values_for_class = _extract_class_shap_values(shap_output, class_idx)

    top_indices = np.argsort(shap_values_for_class)[-top_k:][::-1]

    top_features = []
    for idx in top_indices:
        feature_name = FEATURES[idx]
        top_features.append(
            {
                "feature": feature_name,
                "display_name": _format_feature_name(feature_name),
                "shap_value": round(float(shap_values_for_class[idx]), 4),
            }
        )

    return top_features


def _build_explanation_text(
    anomaly_class: str,
    anomaly_score: float,
    top_features: List[Dict[str, Any]],
) -> str:
    confidence_pct = int(round(anomaly_score * 100))
    readable_features = [
        item.get(
            "display_name", _format_feature_name(item.get("feature", "unknown_feature"))
        )
        for item in top_features
    ]
    feature_text = (
        ", ".join(readable_features) if readable_features else "sensor patterns"
    )

    if anomaly_class == "no_fault":
        return "Status: System is operating normally. No anomalies detected."

    if anomaly_class == "bearing_fault":
        return (
            f"Critical Warning: Vibration Anomaly detected with "
            f"{confidence_pct}% confidence. Primary contributing factors: {feature_text}."
        )

    if anomaly_class == "overheating":
        return (
            f"Alert: Temperature Anomaly detected with "
            f"{confidence_pct}% confidence. Primary contributing factors: {feature_text}."
        )

    return (
        f"Warning: An anomaly was detected with {confidence_pct}% confidence. "
        f"Primary contributing factors: {feature_text}."
    )


def generate_xai_report(model: Any, live_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates SHAP-based top feature explanations from model and live input.

    Expected input schema:
    {
        "timestamp": "2026-03-25T02:15:00",
        "anomaly_class": "bearing_fault",
        "anomaly_score": 0.87,
        "input_features": {
            "Vibration (mm/s)": ...,
            "Temperature (°C)": ...,
            "Pressure (bar)": ...,
            "vib_rolling_mean": ...,
            "vib_rolling_std": ...,
            "vib_rolling_max": ...,
            "temp_rolling_mean": ...,
            "temp_drift": ...,
            "pressure_rolling_mean": ...
        }
    }

    Note:
    - input_features are expected to be the final scaled feature values
      produced by the inference pipeline.
    """
    timestamp = live_json.get("timestamp")
    anomaly_class = live_json.get("anomaly_class", "no_fault")
    anomaly_score = float(live_json.get("anomaly_score", 0.0))
    input_features = live_json.get("input_features", {})

    severity = _get_severity(anomaly_class, anomaly_score)

    if anomaly_class == "no_fault":
        top_features = []
    else:
        top_features = _compute_top_features(
            model=model,
            input_features=input_features,
            anomaly_class=anomaly_class,
            top_k=3,
        )

    explanation_text = _build_explanation_text(
        anomaly_class=anomaly_class,
        anomaly_score=anomaly_score,
        top_features=top_features,
    )

    return {
        "timestamp": timestamp,
        "anomaly_class": anomaly_class,
        "anomaly_label": CLASS_DISPLAY_MAP.get(anomaly_class, anomaly_class),
        "anomaly_score": anomaly_score,
        "severity": severity,
        "top_features": top_features,
        "explanation_text": explanation_text,
    }
