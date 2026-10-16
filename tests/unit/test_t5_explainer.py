from types import SimpleNamespace

import pytest

from ai import explainer, t5_inference
from shared.schemas import AnomalyResult, EventIn


@pytest.mark.parametrize("text,source", [("Temperature rose under load. Inspect cooling.", "t5"), (None, "lstm_template")])
def test_lstm_explanation_records_actual_source(monkeypatch, text, source):
    monkeypatch.delenv("DTX_FORCE_STUB", raising=False)
    monkeypatch.setattr(explainer, "load_runtime_model", lambda **kwargs: SimpleNamespace(
        available=True, supports_tree_xai=False, family="lstm_autoencoder_pytorch"))
    monkeypatch.setattr(t5_inference, "generate_explanation", lambda *args: text)
    event = EventIn(asset_id="forklift-test", zone_id="A")
    anomaly = AnomalyResult(event_id=event.event_id, anomaly_score=0.8, is_anomaly=True)
    result = explainer.explain(event, anomaly)
    assert result.source == source
    assert result.summary == text if text else "LSTM-AE runtime" in result.summary


def test_missing_t5_weights_falls_back_without_download(monkeypatch, tmp_path):
    monkeypatch.setattr(t5_inference, "MODEL_DIR", tmp_path / "missing")
    monkeypatch.setattr(t5_inference, "_load_attempted", False)
    monkeypatch.setattr(t5_inference, "_load_ok", False)
    event = EventIn(asset_id="forklift-test", zone_id="A")
    anomaly = AnomalyResult(event_id=event.event_id, anomaly_score=0.8, is_anomaly=True)
    assert t5_inference.generate_explanation(event, anomaly) is None
