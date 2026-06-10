import os
import sys

import pytest

# Ensure services and packages are importable from tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))

from shared.schemas import EventIn, AnomalyResult  # noqa: E402
import importlib.util


def _load_module_from_repo(relpath: str, mod_name: str):
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), relpath))
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Load ai modules directly from their file paths to avoid package import issues in test runner
detector = _load_module_from_repo("../../services/ai/ai/detector.py", "ai.detector")
model_loader = _load_module_from_repo("../../services/ai/ai/model_loader.py", "ai.model_loader")
preprocessing_module = _load_module_from_repo("../../services/ai/preprocessing.py", "ai.preprocessing")
RuntimeModel = model_loader.RuntimeModel


def make_sample_history(window: int, feature_count: int):
    # simple synthetic increasing rows
    return [[float(i + j * 0.01) for j in range(feature_count)] for i in range(window)]


def test_cnn_replay_uses_provided_history_and_does_not_touch_global_buffer(monkeypatch):
    # Arrange
    initial_buf_len = len(detector._CNN_BUFFER)
    window = 30
    feature_count = len(preprocessing_module.FEATURES)
    history = make_sample_history(window, feature_count)

    # Event must have at least one non-None sensor to avoid the early rule-based short-circuit
    event = EventIn(asset_id="forklift-01", zone_id="zone-A", vibration_magnitude=0.1, metadata={
        "replay_strict": True,
        "replay_history": history,
    })

    # Provide a fake runtime model so detect() proceeds to the CNN path; we will stub out the actual run
    fake_runtime = RuntimeModel(
        key="cnn",
        family="cnn_pytorch",
        model=object(),
        metadata={"best_params": {"window": window}},
        scaler=None,
        feature_order=preprocessing_module.FEATURES,
        supports_tree_xai=False,
        available=True,
    )

    # Patch the detector's reference to load_runtime_model so it returns our fake runtime
    monkeypatch.setattr(detector, "load_runtime_model", lambda requested_model=None, strict_selection=False: fake_runtime)

    # Stub the real _run_cnn_model to assert we received replay_history and did not touch global buffer
    def fake_run_cnn_model(ev, runtime):
        assert ev.metadata.get("replay_history") is history
        # Buffer must remain unchanged in strict replay mode
        assert len(detector._CNN_BUFFER) == initial_buf_len
        ev.metadata["cnn_used_replay_history"] = True
        return AnomalyResult(event_id=ev.event_id, anomaly_score=0.0, is_anomaly=False)

    monkeypatch.setattr(detector, "_run_cnn_model", fake_run_cnn_model)

    # Act
    result = detector.detect(event)

    # Assert
    assert isinstance(result, AnomalyResult)
    assert result.event_id == event.event_id
    assert event.metadata.get("cnn_used_replay_history") is True
    assert len(detector._CNN_BUFFER) == initial_buf_len
