"""SHAP-based XAI report builder for the tree-model runtime path."""

from typing import Any, Dict, List

import numpy as np
import pandas as pd
import shap

# FEATURES must match preprocessing.FEATURES one-for-one — the runtime
# explainer aligns SHAP outputs to this order positionally.
FEATURES = [
    "imu_lin_acc_x",
    "imu_lin_acc_y",
    "imu_lin_acc_z",
    "imu_ang_vel_x",
    "imu_ang_vel_y",
    "imu_ang_vel_z",
    "vibration_magnitude",
    "lift_joint_position",
    "lift_force_z",
    "pseudo_pressure_pa",
    "drive_joint_velocity",
    "drive_joint_effort",
    "lift_joint_velocity",
    "roller_fl_velocity",
    "roller_fr_velocity",
    "roller_bl_velocity",
    "roller_br_velocity",
    "power_dissipated_w",
    "temperature_c",
]

# Canonical class string → SHAP class index. Order matches
# preprocessing.CLASS_NAMES so model output and explainer agree.
CLASS_INDEX_MAP = {
    "nominal": 0,
    "bearing_wear": 1,
    "overheat": 2,
    "overload": 3,
    "pressure_fault": 4,
    "wheel_slip": 5,
}

CLASS_DISPLAY_MAP = {
    "nominal": "Nominal",
    "bearing_wear": "Bearing Wear",
    "overheat": "Overheat",
    "overload": "Overload",
    "pressure_fault": "Pressure Fault",
    "wheel_slip": "Wheel Slip",
}

# Human-readable feature names for the operator-facing summary text.
FEATURE_DISPLAY_MAP = {
    "imu_lin_acc_x": "linear accel X",
    "imu_lin_acc_y": "linear accel Y",
    "imu_lin_acc_z": "linear accel Z",
    "imu_ang_vel_x": "angular velocity X",
    "imu_ang_vel_y": "angular velocity Y",
    "imu_ang_vel_z": "angular velocity Z",
    "vibration_magnitude": "vibration magnitude",
    "lift_joint_position": "lift joint position",
    "lift_force_z": "vertical lift force",
    "pseudo_pressure_pa": "hydraulic pressure",
    "drive_joint_velocity": "drive velocity",
    "drive_joint_effort": "drive effort",
    "lift_joint_velocity": "lift velocity",
    "roller_fl_velocity": "front-left roller",
    "roller_fr_velocity": "front-right roller",
    "roller_bl_velocity": "back-left roller",
    "roller_br_velocity": "back-right roller",
    "power_dissipated_w": "power dissipation",
    "temperature_c": "temperature",
}


def _format_feature_name(feature_name: str) -> str:
    return FEATURE_DISPLAY_MAP.get(feature_name, feature_name)


def _get_severity(anomaly_class: str, anomaly_score: float) -> str:
    if anomaly_class == "nominal":
        return "info"
    if anomaly_score >= 0.85:
        return "critical"
    if anomaly_score >= 0.60:
        return "warning"
    return "caution"


def _build_input_dataframe(input_features: Dict[str, Any]) -> pd.DataFrame:
    missing = [f for f in FEATURES if f not in input_features]
    if missing:
        raise ValueError(f"Missing required input feature(s): {missing}")
    row = {f: input_features[f] for f in FEATURES}
    return pd.DataFrame([row], columns=FEATURES)


def _extract_class_shap_values(shap_output: Any, class_idx: int) -> np.ndarray:
    """Handle the various SHAP output shapes (list / 2-D / 3-D)."""
    values = shap_output.values if hasattr(shap_output, "values") else shap_output

    if isinstance(values, list):
        return np.abs(np.asarray(values[class_idx])[0])

    values = np.asarray(values)
    if values.ndim == 3:
        n_classes = len(CLASS_INDEX_MAP)
        if values.shape[2] == n_classes:
            return np.abs(values[0, :, class_idx])
        if values.shape[1] == n_classes:
            return np.abs(values[0, class_idx, :])
        raise ValueError(f"Unsupported 3D SHAP output shape: {values.shape}")
    if values.ndim == 2:
        return np.abs(values[0])
    if values.ndim == 1:
        return np.abs(values)
    raise ValueError(f"Unsupported SHAP output shape: {values.shape}")


def _compute_top_features(
    model: Any,
    input_features: Dict[str, Any],
    anomaly_class: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    X_scaled_df = _build_input_dataframe(input_features)
    explainer = shap.TreeExplainer(model)
    shap_output = explainer.shap_values(X_scaled_df)

    class_idx = CLASS_INDEX_MAP.get(anomaly_class, 0)
    shap_values_for_class = _extract_class_shap_values(shap_output, class_idx)

    top_indices = np.argsort(shap_values_for_class)[-top_k:][::-1]
    return [
        {
            "feature": FEATURES[idx],
            "display_name": _format_feature_name(FEATURES[idx]),
            "shap_value": round(float(shap_values_for_class[idx]), 4),
        }
        for idx in top_indices
    ]


def _build_explanation_text(
    anomaly_class: str,
    anomaly_score: float,
    top_features: List[Dict[str, Any]],
) -> str:
    if anomaly_class == "nominal":
        return "Status: System is operating normally. No anomalies detected."

    confidence_pct = int(round(anomaly_score * 100))
    readable = [
        item.get("display_name", _format_feature_name(item.get("feature", "?")))
        for item in top_features
    ]
    feature_text = ", ".join(readable) if readable else "sensor patterns"

    display_label = CLASS_DISPLAY_MAP.get(anomaly_class, anomaly_class)
    severity_word = (
        "Critical Warning"
        if anomaly_class in {"overheat"}
        else "Alert"
    )
    return (
        f"{severity_word}: {display_label} detected with "
        f"{confidence_pct}% confidence. Primary contributing factors: {feature_text}."
    )


def generate_xai_report(model: Any, live_json: Dict[str, Any]) -> Dict[str, Any]:
    """Build a SHAP-backed explanation report for a single tree-model prediction."""
    timestamp = live_json.get("timestamp")
    anomaly_class = live_json.get("anomaly_class", "nominal")
    anomaly_score = float(live_json.get("anomaly_score", 0.0))
    input_features = live_json.get("input_features", {})

    severity = _get_severity(anomaly_class, anomaly_score)

    if anomaly_class == "nominal":
        top_features: List[Dict[str, Any]] = []
    else:
        top_features = _compute_top_features(
            model=model,
            input_features=input_features,
            anomaly_class=anomaly_class,
            top_k=3,
        )

    return {
        "timestamp": timestamp,
        "anomaly_class": anomaly_class,
        "anomaly_label": CLASS_DISPLAY_MAP.get(anomaly_class, anomaly_class),
        "anomaly_score": anomaly_score,
        "severity": severity,
        "top_features": top_features,
        "explanation_text": _build_explanation_text(anomaly_class, anomaly_score, top_features),
    }
