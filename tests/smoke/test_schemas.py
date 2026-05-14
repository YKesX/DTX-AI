"""tests/smoke/test_schemas.py — smoke tests for packages/shared schemas."""

import os
import sys
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))

from shared.schemas import (  # noqa: E402
    AnomalyResult,
    AnomalyType,
    AssetStatus,
    DashboardAlert,
    EventIn,
    ExplanationResult,
    Severity,
    TwinUpdate,
)


def make_event(**kwargs) -> EventIn:
    defaults = dict(asset_id="forklift-01", zone_id="zone-A")
    defaults.update(kwargs)
    return EventIn(**defaults)


class TestEventIn:
    def test_defaults_are_populated(self):
        e = make_event()
        assert e.event_id is not None
        assert e.timestamp is not None

    def test_optional_sensors_accept_none(self):
        e = make_event()
        assert e.vibration_magnitude is None
        assert e.temperature_c is None

    def test_partial_event_valid(self):
        e = make_event(vibration_magnitude=9.8)
        assert e.vibration_magnitude == 9.8
        assert e.temperature_c is None

    def test_all_19_channels_accepted(self):
        e = make_event(
            imu_lin_acc_x=-9.77, imu_lin_acc_y=0.0, imu_lin_acc_z=0.86,
            imu_ang_vel_x=0.0, imu_ang_vel_y=0.0, imu_ang_vel_z=0.0,
            vibration_magnitude=9.81,
            lift_joint_position=-0.15, lift_force_z=0.31, lift_joint_velocity=0.0,
            pseudo_pressure_pa=3.8,
            drive_joint_velocity=-0.01, drive_joint_effort=3082.0,
            roller_fl_velocity=0.06, roller_fr_velocity=-0.02,
            roller_bl_velocity=0.07, roller_br_velocity=0.01,
            power_dissipated_w=0.0,
            temperature_c=25.15,
        )
        assert e.temperature_c == 25.15
        assert e.lift_force_z == 0.31


class TestAnomalyResult:
    def test_score_bounds(self):
        a = AnomalyResult(
            event_id=uuid4(), anomaly_score=0.75, is_anomaly=True,
            anomaly_type=AnomalyType.BEARING_WEAR, severity=Severity.WARNING,
        )
        assert 0.0 <= a.anomaly_score <= 1.0

    def test_score_out_of_range_raises(self):
        with pytest.raises(Exception):
            AnomalyResult(event_id=uuid4(), anomaly_score=1.5, is_anomaly=True)

    def test_all_6_anomaly_types(self):
        # Every canonical class name must round-trip through the enum.
        names = ["nominal", "bearing_wear", "overheat", "overload",
                 "pressure_fault", "wheel_slip"]
        for name in names:
            assert AnomalyType(name).value == name


class TestDashboardAlert:
    def test_composed_alert(self):
        event = make_event(vibration_magnitude=9.82, temperature_c=27.2,
                           power_dissipated_w=299.0)
        anomaly = AnomalyResult(
            event_id=event.event_id, anomaly_score=0.6, is_anomaly=True,
            anomaly_type=AnomalyType.BEARING_WEAR, severity=Severity.WARNING,
        )
        explanation = ExplanationResult(
            event_id=event.event_id,
            summary="Bearing wear detected.",
            contributing_features={"power_dissipated_w": 0.6, "vibration_magnitude": 0.4},
            recommendation="Inspect bearings.",
        )
        alert = DashboardAlert(event=event, anomaly=anomaly, explanation=explanation)
        assert alert.alert_id is not None
        assert alert.event.asset_id == "forklift-01"


class TestTwinUpdate:
    def test_twin_update_has_required_fields(self):
        update = TwinUpdate(
            event_id=uuid4(), asset_id="forklift-01", zone_id="zone-A",
            new_status=AssetStatus.DEGRADED, severity=Severity.WARNING,
            label="bearing_wear / score=0.85",
        )
        assert update.new_status == AssetStatus.DEGRADED
