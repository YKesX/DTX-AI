import importlib
import os
import sys
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../apps/sim"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))

import sim.hooks as sim_hooks  # noqa: E402
import sim.scene as sim_scene  # noqa: E402
from shared.schemas import AssetStatus, Severity, TwinUpdate  # noqa: E402


def _make_update() -> TwinUpdate:
    return TwinUpdate(
        event_id=uuid4(),
        asset_id="forklift-01",
        zone_id="zone-A",
        new_status=AssetStatus.DEGRADED,
        severity=Severity.WARNING,
        label="bearing_wear / score=0.85",
    )


def _reload_adapter(monkeypatch, enabled: str):
    monkeypatch.setenv("ISAAC_SIM_ENABLED", enabled)
    import sim.adapter as sim_adapter  # noqa: E402

    return importlib.reload(sim_adapter)


def test_notify_disabled_skips_scene_update(monkeypatch):
    sim_adapter = _reload_adapter(monkeypatch, "false")
    calls = []

    monkeypatch.setattr(
        sim_scene,
        "update_asset_status",
        lambda **kwargs: calls.append(kwargs),
    )

    sim_adapter.notify(_make_update())

    assert calls == []


def test_notify_enabled_calls_scene_update(monkeypatch):
    sim_adapter = _reload_adapter(monkeypatch, "true")
    calls = []

    monkeypatch.setattr(
        sim_scene,
        "update_asset_status",
        lambda **kwargs: calls.append(kwargs),
    )

    sim_adapter.notify(_make_update())

    assert len(calls) == 1
    assert calls[0]["asset_id"] == "forklift-01"
    assert calls[0]["zone_id"] == "zone-A"
    assert calls[0]["status"] == "degraded"
    assert calls[0]["severity"] == "warning"
    assert calls[0]["label"] == "bearing_wear / score=0.85"


def test_notify_enabled_swallows_scene_failure(monkeypatch, caplog):
    sim_adapter = _reload_adapter(monkeypatch, "true")

    def _boom(**kwargs):
        raise RuntimeError("scene exploded")

    monkeypatch.setattr(sim_scene, "update_asset_status", _boom)

    sim_adapter.notify(_make_update())

    assert "Failed to update Isaac Sim scene" in caplog.text


def test_scene_stubs_and_hooks_do_not_raise(caplog):
    caplog.set_level("INFO")

    sim_scene.update_asset_status(
        asset_id="forklift-01",
        zone_id="zone-A",
        status="degraded",
        severity="warning",
        label="bearing_wear / score=0.85",
    )
    sim_scene.reset_scene()
    sim_hooks.on_simulation_start()
    sim_hooks.on_simulation_step(0.016)
    sim_hooks.on_simulation_stop()

    assert "[STUB] update_asset_status" in caplog.text
    assert "[STUB] reset_scene" in caplog.text
    assert "Simulation started" in caplog.text
    assert "Simulation stopped" in caplog.text
