"""tests/integration/test_api.py — integration tests for the FastAPI app.

Requires: ``pip install httpx pytest-asyncio`` (covered by apps/api/requirements.txt).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/ai"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../apps/api"))

import pytest

try:
    from httpx import AsyncClient, ASGITransport
    from main import app
    from api.database import clear_events, init_db
    from api.live_metrics import live_metrics
    from api.routes.events import _normalize_gt_label
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not _HTTPX_AVAILABLE,
    reason="httpx not installed — run: pip install -r apps/api/requirements.txt",
)


# ── Sensor profiles drawn from the training data's per-class means so the
#    trained model sees in-distribution inputs and predicts the expected class.
def _bearing_wear_event(**overrides):
    payload = {
        "asset_id": "test-forklift-01",
        "zone_id": "zone-A",
        "imu_lin_acc_x": -9.77252, "imu_lin_acc_y": 0.00003, "imu_lin_acc_z": 0.856711,
        "imu_ang_vel_x": 0.0, "imu_ang_vel_y": 0.0, "imu_ang_vel_z": 0.0,
        "vibration_magnitude": 9.81,
        "lift_joint_position": -0.045975, "lift_force_z": -738.923773, "lift_joint_velocity": 0.073892,
        "pseudo_pressure_pa": -9236.5472,
        "drive_joint_velocity": 0.010401, "drive_joint_effort": 3028.383545,
        "roller_fl_velocity": 0.017542, "roller_fr_velocity": 0.029011,
        "roller_bl_velocity": 0.017779, "roller_br_velocity": 0.017592,
        "power_dissipated_w": 0.0,
        "temperature_c": 25.5379,
    }
    payload.update(overrides)
    return payload


def _nominal_event(**overrides):
    payload = {
        "asset_id": "test-forklift-02",
        "zone_id": "zone-A",
        "imu_lin_acc_x": -9.77, "imu_lin_acc_y": 0.0, "imu_lin_acc_z": 0.86,
        "imu_ang_vel_x": 0.0, "imu_ang_vel_y": 0.0, "imu_ang_vel_z": 0.0,
        "vibration_magnitude": 9.81,
        "lift_joint_position": -0.15, "lift_force_z": 0.31, "lift_joint_velocity": 0.0,
        "pseudo_pressure_pa": 3.82,
        "drive_joint_velocity": -0.01, "drive_joint_effort": 3082.0,
        "roller_fl_velocity": 0.06, "roller_fr_velocity": -0.02,
        "roller_bl_velocity": 0.07, "roller_br_velocity": 0.01,
        "power_dissipated_w": 0.0,
        "temperature_c": 25.15,
    }
    payload.update(overrides)
    return payload


_CANONICAL_LABELS = {
    "nominal", "bearing_wear", "overheat", "overload",
    "pressure_fault", "wheel_slip", "unknown",
}


@pytest.fixture(autouse=True)
async def setup_db():
    """Initialise the SQLite DB before each test."""
    await init_db()
    await clear_events()
    live_metrics.reset()


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_post_event_returns_alert():
    payload = _bearing_wear_event()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/events/", json=payload)
    assert resp.status_code == 202
    data = resp.json()
    assert "anomaly" in data
    assert "explanation" in data
    # Bearing-wear profile should classify as a fault, not nominal.
    assert data["anomaly"]["is_anomaly"] is True


@pytest.mark.asyncio
async def test_post_event_dataset_replay_metadata_and_metrics():
    payload = _bearing_wear_event(metadata={
        "source": "dataset_replay",
        "dataset": "dtx_ai_master_dataset",
        "split": "test",
        "row_id": 99,
        "ground_truth_label": "1",
        "ground_truth_name": "bearing_wear",
        "active_model": "lightgbm",
        "replay_strict": False,
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/events/", json=payload)
        assert resp.status_code == 202
        body = resp.json()
        assert body["event"]["metadata"]["source"] == "dataset_replay"
        assert "predicted_label" in body["event"]["metadata"]
        assert "prediction_correct" in body["event"]["metadata"]

        metrics_resp = await client.get("/metrics/live")
        assert metrics_resp.status_code == 200
        metrics = metrics_resp.json()
        assert metrics["total_replayed"] >= 1
        assert "running_accuracy" in metrics


@pytest.mark.asyncio
async def test_post_event_dataset_replay_numeric_gt_label_normalized():
    """Numeric ground_truth_label (e.g. '1') must be normalised to the canonical
    class name (e.g. 'bearing_wear') before comparing against predicted_label so
    correct predictions are not falsely marked incorrect."""
    payload = _bearing_wear_event(metadata={
        "source": "dataset_replay",
        # Only the numeric code is provided — name intentionally omitted.
        "ground_truth_label": "1",
        "active_model": "lightgbm",
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/events/", json=payload)
        assert resp.status_code == 202
        meta = resp.json()["event"]["metadata"]
        assert "prediction_correct" in meta
        # predicted_label is always a canonical fault_label string.
        assert meta["predicted_label"] in _CANONICAL_LABELS
        predicted = meta["predicted_label"]
        expected_correct = predicted == _normalize_gt_label("1")
        assert meta["prediction_correct"] == expected_correct


@pytest.mark.asyncio
async def test_get_alerts():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/alerts/")
    assert resp.status_code == 200
    assert "alerts" in resp.json()


@pytest.mark.asyncio
async def test_clear_alerts_resets_logs_and_metrics():
    payload = _bearing_wear_event(metadata={
        "source": "dataset_replay",
        "ground_truth_name": "bearing_wear",
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        post_resp = await client.post("/events/", json=payload)
        assert post_resp.status_code == 202

        before_resp = await client.get("/alerts/")
        assert before_resp.status_code == 200
        assert before_resp.json().get("count", 0) >= 1

        clear_resp = await client.delete("/alerts/clear")
        assert clear_resp.status_code == 200
        assert clear_resp.json().get("metrics_reset") is True

        after_resp = await client.get("/alerts/")
        assert after_resp.status_code == 200
        assert after_resp.json().get("count", 0) == 0

        metrics_resp = await client.get("/metrics/live")
        assert metrics_resp.status_code == 200
        metrics = metrics_resp.json()
        assert metrics.get("total_replayed") == 0
        assert metrics.get("total_correct") == 0


@pytest.mark.asyncio
async def test_asset_timeline_returns_sensor_history_in_time_order():
    payloads = [
        _nominal_event(
            asset_id="timeline-asset-01",
            zone_id="zone-T",
            temperature_c=25.0,
            timestamp="2026-04-09T10:00:00Z",
        ),
        _nominal_event(
            asset_id="timeline-asset-01",
            zone_id="zone-T",
            temperature_c=30.0,
            vibration_magnitude=9.85,
            timestamp="2026-04-09T10:01:00Z",
        ),
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for payload in payloads:
            resp = await client.post("/events/", json=payload)
            assert resp.status_code == 202

        timeline_resp = await client.get("/assets/timeline-asset-01/timeline?limit=10")

    assert timeline_resp.status_code == 200
    body = timeline_resp.json()
    assert body["asset_id"] == "timeline-asset-01"
    assert len(body["points"]) == 2
    assert body["points"][0]["timestamp"] < body["points"][1]["timestamp"]
    assert body["points"][0]["temperature_c"] == 25.0
    assert body["points"][1]["temperature_c"] == 30.0


@pytest.mark.asyncio
async def test_alert_actions_persist_and_derive_operator_state():
    payload = _bearing_wear_event(asset_id="operator-asset-01", zone_id="zone-O")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        event_resp = await client.post("/events/", json=payload)
        assert event_resp.status_code == 202
        event_id = event_resp.json()["event"]["event_id"]

        assign_resp = await client.post(
            f"/alerts/{event_id}/actions",
            json={"action_type": "assign", "assignee": "Hakki", "note": "Forward to maintenance"},
        )
        assert assign_resp.status_code == 201
        assign_body = assign_resp.json()
        assert assign_body["state"]["operator_status"] == "assigned"
        assert assign_body["state"]["assigned_to"] == "Hakki"

        resolve_resp = await client.post(
            f"/alerts/{event_id}/actions",
            json={"action_type": "resolve", "note": "Issue cleared after inspection"},
        )
        assert resolve_resp.status_code == 201
        assert resolve_resp.json()["state"]["operator_status"] == "resolved"
        assert resolve_resp.json()["state"]["assigned_to"] == "Hakki"

        actions_resp = await client.get(f"/alerts/{event_id}/actions")
        assert actions_resp.status_code == 200
        actions_body = actions_resp.json()
        assert actions_body["state"]["operator_status"] == "resolved"
        assert len(actions_body["actions"]) == 2
        assert actions_body["actions"][0]["action_type"] == "resolve"

        alerts_resp = await client.get("/alerts/")
        assert alerts_resp.status_code == 200
        alert_row = alerts_resp.json()["alerts"][0]
        assert alert_row["operator_status"] == "resolved"
        assert alert_row["assigned_to"] == "Hakki"
