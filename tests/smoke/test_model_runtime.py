import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/ai"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))

from shared.schemas import EventIn
from ai.detector import detect
from ai.model_loader import _CACHE, _resolve_path, load_runtime_model


def _clear_cache():
    _CACHE.clear()


def test_registry_path_resolution_points_to_existing_artifacts():
    registry_path = _resolve_path("services/ai/models/shared/model_registry.json")
    feature_path = _resolve_path("services/ai/models/shared/feature_order.json")
    assert registry_path.exists()
    assert feature_path.exists()


def test_active_model_selection_from_registry_default():
    _clear_cache()
    runtime = load_runtime_model()
    assert runtime.available is True
    assert runtime.key in {"lightgbm", "random_forest", "xgboost", "lstm_ae"}


def test_explicit_model_selection_falls_back_when_missing_dependency(monkeypatch):
    _clear_cache()
    monkeypatch.setenv("DTX_ACTIVE_MODEL", "lightgbm")
    runtime = load_runtime_model()
    # If lightgbm/xgboost package is absent, loader should still provide a working fallback.
    assert runtime.available is True or runtime.reason != ""


# Profile near the bearing_wear class mean so the trained model sees an
# in-distribution input; keeps these smoke tests stable across retrains.
_BEARING_WEAR_PROFILE = dict(
    imu_lin_acc_x=-9.77, imu_lin_acc_y=0.0, imu_lin_acc_z=0.86,
    imu_ang_vel_x=0.0, imu_ang_vel_y=0.0, imu_ang_vel_z=0.0,
    vibration_magnitude=9.82,
    lift_joint_position=-0.15, lift_force_z=-0.44, lift_joint_velocity=0.0,
    pseudo_pressure_pa=-5.56,
    drive_joint_velocity=0.0, drive_joint_effort=2812.0,
    roller_fl_velocity=0.01, roller_fr_velocity=0.0,
    roller_bl_velocity=0.01, roller_br_velocity=0.0,
    power_dissipated_w=299.0,
    temperature_c=27.2,
)


def test_tree_inference_smoke_with_forced_random_forest(monkeypatch):
    _clear_cache()
    monkeypatch.setenv("DTX_ACTIVE_MODEL", "random_forest")
    monkeypatch.delenv("DTX_FORCE_STUB", raising=False)
    event = EventIn(asset_id="forklift-01", zone_id="zone-A", **_BEARING_WEAR_PROFILE)
    result = detect(event)
    assert 0.0 <= result.anomaly_score <= 1.0
    assert result.event_id == event.event_id


def test_lstm_ae_missing_threshold_graceful(monkeypatch):
    _clear_cache()
    monkeypatch.setenv("DTX_ACTIVE_MODEL", "lstm_ae")
    event = EventIn(asset_id="forklift-02", zone_id="zone-B", **_BEARING_WEAR_PROFILE)
    result = detect(event)
    assert 0.0 <= result.anomaly_score <= 1.0
    assert result.event_id == event.event_id


def test_strict_selection_fails_for_unknown_model():
    _clear_cache()
    runtime = load_runtime_model(requested_model="model_does_not_exist", strict_selection=True)
    assert runtime.available is False
    assert "disabled or missing" in runtime.reason


def test_detect_strict_replay_raises_when_selected_model_missing(monkeypatch):
    _clear_cache()
    monkeypatch.setenv("DTX_REPLAY_STRICT", "1")
    # At least one sensor channel must be non-None or the detector short-circuits
    # to the rule-based stub before evaluating strict-replay model selection.
    event = EventIn(
        asset_id="strict-asset", zone_id="zone-S",
        **_BEARING_WEAR_PROFILE,
        metadata={"active_model": "missing_model", "replay_strict": True},
    )
    try:
        detect(event)
        assert False, "detect() should raise in strict replay mode for missing model"
    except RuntimeError as exc:
        assert "Strict replay mode enabled" in str(exc)
    finally:
        monkeypatch.delenv("DTX_REPLAY_STRICT", raising=False)
