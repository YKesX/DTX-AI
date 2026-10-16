"""Sensor faults must not turn into fabricated real readings or invalid JSON."""
import importlib.util
import json
from pathlib import Path
import random

import pytest

spec = importlib.util.spec_from_file_location("hw_demo_bridge", Path(__file__).resolve().parents[2] / "scripts/hw_demo_bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def payload(reading, **overrides):
    kwargs = dict(temp_baseline=20.0, pressure_baseline=100000.0,
                  pressure_gain=200.0, power_per_degree=40.0,
                  model="lightgbm", sequence=1, rng=random.Random(1))
    kwargs.update(overrides)
    stats = {key: {"median": 10.0, "std": 0.0} for key in bridge.FEATURES}
    return bridge.build_event_payload(reading, stats, **kwargs)


def test_physical_units_and_channel_provenance():
    result = payload({"temperature_c": 25, "pressure_pa": 100010})
    assert result["temperature_c"] == 25
    assert result["pseudo_pressure_pa"] == 2000
    assert result["power_dissipated_w"] == 210
    assert result["metadata"]["real_channels"] == ["pseudo_pressure_pa", "temperature_c"]
    assert result["metadata"]["derived_channels"] == ["power_dissipated_w"]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("reading", [
    {}, {"temperature_c": -127}, {"temperature_c": float("inf")},
    {"temperature_c": 126}, {"temperature_c": True},
    {"pressure_pa": float("nan")}, {"pressure_pa": 120000},
    {"temperature_c": 25, "ds18b20_ok": False},
    {"pressure_pa": 100000, "bmp280_ok": False},
    {"temperature_c": 25, "sample_age_ms": 3001},
])
def test_missing_invalid_or_stale_sensors_do_not_generate_events(reading):
    with pytest.raises(ValueError, match="No valid"):
        payload(reading)


def test_partial_failure_is_declared_as_synthetic():
    result = payload({"temperature_c": None, "pressure_pa": 100010}, temp_baseline=float("nan"))
    meta = result["metadata"]
    assert meta["real_channels"] == ["pseudo_pressure_pa"]
    assert meta["derived_channels"] == []
    assert "temperature_c" in meta["synthesized_channels"]
    assert "power_dissipated_w" in meta["synthesized_channels"]
    json.dumps(result, allow_nan=False)


def test_recovered_pressure_requires_baseline_before_mapping():
    with pytest.raises(ValueError, match="baseline"):
        payload({"temperature_c": 25, "pressure_pa": 100010}, pressure_baseline=float("nan"))


def test_calibration_ignores_disconnected_and_nonfinite_values(monkeypatch):
    readings = iter([
        {"temperature_c": -127, "pressure_pa": float("nan")},
        {"temperature_c": 20, "pressure_pa": 100000},
        {"temperature_c": 22, "pressure_pa": 100020},
    ])
    monkeypatch.setattr(bridge, "fetch_json", lambda _: next(readings))
    monkeypatch.setattr(bridge.time, "sleep", lambda _: None)
    assert bridge.calibrate("http://device", 3, 1) == (21, 100010)


def test_actual_85_degree_reading_is_not_arbitrarily_discarded():
    assert payload({"temperature_c": 85})["temperature_c"] == 85
