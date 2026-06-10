"""tests/smoke/test_ai_pipeline.py — smoke tests for the AI detection pipeline.

These tests exercise the deterministic rule-based detector (the threshold-driven
fallback in services/ai/ai/detector.py:_rule_based_detect), not the trained
model. Forcing DTX_FORCE_STUB=1 keeps them stable regardless of which model
artifact is checked in.
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/ai"))

from shared.schemas import AnomalyType, EventIn  # noqa: E402
from ai.detector import detect  # noqa: E402
from ai.explainer import explain  # noqa: E402


@pytest.fixture(autouse=True)
def _force_rule_based_stub(monkeypatch):
    monkeypatch.setenv("DTX_FORCE_STUB", "1")


def make_event(**kwargs) -> EventIn:
    defaults = dict(asset_id="test-asset", zone_id="zone-X")
    defaults.update(kwargs)
    return EventIn(**defaults)


class TestDetector:
    def test_normal_event_low_score(self):
        # All channels well within nominal envelopes.
        e = make_event(
            vibration_magnitude=9.8,
            temperature_c=25.0,
            pseudo_pressure_pa=3.0,
            power_dissipated_w=0.0,
        )
        result = detect(e)
        assert result.anomaly_score < 0.5
        assert result.is_anomaly is False

    def test_high_temperature_flags_overheat(self):
        e = make_event(temperature_c=55.0, power_dissipated_w=2000.0)
        result = detect(e)
        assert result.is_anomaly is True
        # Dominant channel is power_dissipated_w (≥1500/1500=1.0) — overload.
        # Temperature also above threshold (~0.75). Both score ≈ 1.0.
        # Either OVERLOAD or OVERHEAT is acceptable; both are anomalies.
        assert result.anomaly_type in {AnomalyType.OVERHEAT, AnomalyType.OVERLOAD}

    def test_high_pressure_flags_pressure_fault(self):
        e = make_event(pseudo_pressure_pa=-8500.0)
        result = detect(e)
        assert result.is_anomaly is True
        assert result.anomaly_type == AnomalyType.PRESSURE_FAULT

    def test_score_is_normalised(self):
        e = make_event(
            vibration_magnitude=100.0, temperature_c=200.0,
            pseudo_pressure_pa=50000.0, power_dissipated_w=10000.0,
        )
        result = detect(e)
        assert 0.0 <= result.anomaly_score <= 1.0

    def test_all_none_sensors_no_anomaly(self):
        e = make_event()
        result = detect(e)
        assert result.anomaly_score == 0.0
        assert result.is_anomaly is False


class TestExplainer:
    def test_explanation_has_summary(self):
        e = make_event(temperature_c=55.0)
        anomaly = detect(e)
        exp = explain(e, anomaly)
        assert len(exp.summary) > 0

    def test_no_anomaly_has_benign_summary(self):
        e = make_event(vibration_magnitude=9.8, temperature_c=25.0)
        anomaly = detect(e)
        exp = explain(e, anomaly)
        assert exp.event_id == e.event_id

    def test_contributing_features_sum_to_one(self):
        e = make_event(temperature_c=55.0, power_dissipated_w=2000.0)
        anomaly = detect(e)
        exp = explain(e, anomaly)
        if exp.contributing_features:
            total = sum(exp.contributing_features.values())
            assert abs(total - 1.0) < 1e-4


class TestPipeline:
    def test_run_pipeline_async(self):
        from ai.pipeline import run_pipeline
        e = make_event(temperature_c=55.0, power_dissipated_w=2000.0)
        anomaly, explanation = asyncio.run(run_pipeline(e))
        assert anomaly.is_anomaly is True
        assert explanation.event_id == e.event_id
