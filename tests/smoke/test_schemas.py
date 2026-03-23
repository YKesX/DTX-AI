"""
tests/smoke/test_schemas.py — smoke tests for packages/shared schemas.

Run with:
    pytest tests/
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))

import pytest
from shared.schemas import (
    EventIn,
    AnomalyResult,
    ExplanationResult,
    TwinUpdate,
    DashboardAlert,
    AnomalyType,
    Severity,
    AssetStatus,
)
from uuid import uuid4


def make_event(**kwargs) -> EventIn:
    defaults = dict(asset_id="conveyor-belt-01", zone_id="zone-A")
    defaults.update(kwargs)
    return EventIn(**defaults)


class TestEventIn:
    def test_defaults_are_populated(self):
        e = make_event()
        assert e.event_id is not None
        assert e.timestamp is not None

    def test_optional_sensors_accept_none(self):
        e = make_event()
        assert e.vibration is None

    def test_partial_event_valid(self):
        e = make_event(vibration=5.0)
        assert e.vibration == 5.0
        assert e.temperature is None

    def test_humidity_bounds(self):
        with pytest.raises(Exception):
            make_event(humidity=110.0)


class TestAnomalyResult:
    def test_score_bounds(self):
        event_id = uuid4()
        a = AnomalyResult(
            event_id=event_id,
            anomaly_score=0.75,
            is_anomaly=True,
            anomaly_type=AnomalyType.VIBRATION,
            severity=Severity.WARNING,
        )
        assert 0.0 <= a.anomaly_score <= 1.0

    def test_score_out_of_range_raises(self):
        with pytest.raises(Exception):
            AnomalyResult(
                event_id=uuid4(),
                anomaly_score=1.5,
                is_anomaly=True,
            )


class TestDashboardAlert:
    def test_composed_alert(self):
        event = make_event(vibration=15.0, temperature=80.0)
        anomaly = AnomalyResult(
            event_id=event.event_id,
            anomaly_score=0.6,
            is_anomaly=True,
            anomaly_type=AnomalyType.VIBRATION,
            severity=Severity.WARNING,
        )
        explanation = ExplanationResult(
            event_id=event.event_id,
            summary="High vibration detected.",
            contributing_features={"vibration": 0.8},
            recommendation="Inspect motor bearings.",
        )
        alert = DashboardAlert(event=event, anomaly=anomaly, explanation=explanation)
        assert alert.alert_id is not None
        assert alert.event.asset_id == "conveyor-belt-01"
