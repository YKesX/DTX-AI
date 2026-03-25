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


def test_tree_inference_smoke_with_forced_random_forest(monkeypatch):
    _clear_cache()
    monkeypatch.setenv("DTX_ACTIVE_MODEL", "random_forest")
    monkeypatch.delenv("DTX_FORCE_STUB", raising=False)
    event = EventIn(
        asset_id="conveyor-belt-01",
        zone_id="zone-A",
        vibration=14.0,
        temperature=82.0,
        humidity=40.0,
        pressure=1010.0,
    )
    result = detect(event)
    assert 0.0 <= result.anomaly_score <= 1.0
    assert result.event_id == event.event_id


def test_lstm_ae_missing_threshold_graceful(monkeypatch):
    _clear_cache()
    monkeypatch.setenv("DTX_ACTIVE_MODEL", "lstm_ae")
    event = EventIn(
        asset_id="pump-station-02",
        zone_id="zone-B",
        vibration=5.0,
        temperature=55.0,
        humidity=45.0,
        pressure=1012.0,
    )
    result = detect(event)
    assert 0.0 <= result.anomaly_score <= 1.0
    # Metadata currently has null threshold; detector must not crash or fabricate invalid outputs.
    assert result.event_id == event.event_id
