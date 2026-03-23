"""
tests/smoke/test_ai_pipeline.py — smoke tests for the AI detection + explanation pipeline.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/ai"))

import asyncio
import pytest
from shared.schemas import EventIn, AnomalyType, Severity
from ai.detector import detect
from ai.explainer import explain


def make_event(**kwargs) -> EventIn:
    defaults = dict(asset_id="test-asset", zone_id="zone-X")
    defaults.update(kwargs)
    return EventIn(**defaults)


class TestDetector:
    def test_normal_event_low_score(self):
        e = make_event(vibration=3.0, temperature=30.0, humidity=50.0, pressure=1010.0)
        result = detect(e)
        assert result.anomaly_score < 0.5
        assert result.is_anomaly is False

    def test_high_vibration_flags_anomaly(self):
        e = make_event(vibration=20.0, temperature=30.0, humidity=50.0, pressure=1010.0)
        result = detect(e)
        assert result.is_anomaly is True
        assert result.anomaly_type == AnomalyType.VIBRATION

    def test_high_temperature_flags_anomaly(self):
        e = make_event(temperature=90.0)
        result = detect(e)
        assert result.is_anomaly is True

    def test_score_is_normalised(self):
        e = make_event(vibration=100.0, temperature=200.0)
        result = detect(e)
        assert 0.0 <= result.anomaly_score <= 1.0

    def test_all_none_sensors_no_anomaly(self):
        e = make_event()
        result = detect(e)
        assert result.anomaly_score == 0.0
        assert result.is_anomaly is False


class TestExplainer:
    def test_explanation_has_summary(self):
        e = make_event(vibration=15.0)
        anomaly = detect(e)
        exp = explain(e, anomaly)
        assert len(exp.summary) > 0

    def test_no_anomaly_has_benign_summary(self):
        e = make_event(vibration=3.0, temperature=30.0)
        anomaly = detect(e)
        exp = explain(e, anomaly)
        assert exp.event_id == e.event_id

    def test_contributing_features_sum_to_one(self):
        e = make_event(vibration=15.0, temperature=80.0)
        anomaly = detect(e)
        exp = explain(e, anomaly)
        if exp.contributing_features:
            total = sum(exp.contributing_features.values())
            assert abs(total - 1.0) < 1e-4


class TestPipeline:
    def test_run_pipeline_async(self):
        from ai.pipeline import run_pipeline
        e = make_event(vibration=15.0, temperature=82.0)
        anomaly, explanation = asyncio.run(run_pipeline(e))
        assert anomaly.is_anomaly is True
        assert explanation.event_id == e.event_id
