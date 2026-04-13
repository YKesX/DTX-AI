"""
tests/integration/test_api.py — integration tests for the FastAPI app.

Requires:  httpx (pip install httpx pytest-asyncio)
"""
import sys
import os
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
    reason="httpx not installed — run: pip install httpx pytest-asyncio",
)


@pytest.fixture(autouse=True)
async def setup_db():
    """Initialise the SQLite DB before each test (mirrors the lifespan)."""
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
    payload = {
        "asset_id": "conveyor-belt-01",
        "zone_id": "zone-A",
        "vibration": 14.0,
        "temperature": 80.0,
        "humidity": 45.0,
        "pressure": 1012.0,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/events/", json=payload)
    assert resp.status_code == 202
    data = resp.json()
    assert "anomaly" in data
    assert "explanation" in data
    assert data["anomaly"]["is_anomaly"] is True


@pytest.mark.asyncio
async def test_post_event_dataset_replay_metadata_and_metrics():
    payload = {
        "asset_id": "replay-machine-01",
        "zone_id": "zone-R",
        "vibration": 16.0,
        "temperature": 85.0,
        "humidity": 35.0,
        "pressure": 1015.0,
        "metadata": {
            "source": "dataset_replay",
            "dataset": "ziya",
            "split": "test",
            "row_id": 99,
            "ground_truth_label": "1",
            "ground_truth_name": "bearing_fault",
            "active_model": "random_forest",
            "replay_strict": False,
        },
    }
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
    """Numeric ground_truth_label (e.g. '1') must be normalized to the canonical
    label name (e.g. 'bearing_fault') before comparing against predicted_label so
    that correct predictions are not falsely marked as incorrect."""
    payload = {
        "asset_id": "replay-machine-02",
        "zone_id": "zone-R",
        "vibration": 16.0,
        "temperature": 85.0,
        "humidity": 35.0,
        "pressure": 1015.0,
        "metadata": {
            "source": "dataset_replay",
            # Only provide the numeric code — ground_truth_name intentionally absent.
            "ground_truth_label": "1",
            "active_model": "random_forest",
        },
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/events/", json=payload)
        assert resp.status_code == 202
        meta = resp.json()["event"]["metadata"]
        assert "prediction_correct" in meta
        # predicted_label should always be a canonical name, never a raw numeric code.
        assert meta["predicted_label"] in {"no_fault", "bearing_fault", "overheating", "combined", "unknown"}
        # prediction_correct must reflect the normalized comparison, not a raw-vs-canonical mismatch.
        predicted = meta["predicted_label"]
        # ground_truth_label "1" normalizes to "bearing_fault" via _normalize_gt_label.
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
    payload = {
        "asset_id": "replay-machine-01",
        "zone_id": "zone-R",
        "vibration": 16.0,
        "temperature": 85.0,
        "humidity": 35.0,
        "pressure": 1015.0,
        "metadata": {
            "source": "dataset_replay",
            "ground_truth_name": "bearing_fault",
        },
    }

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
        {
            "asset_id": "timeline-asset-01",
            "zone_id": "zone-T",
            "vibration": 2.0,
            "temperature": 32.0,
            "humidity": 45.0,
            "pressure": 1009.0,
            "timestamp": "2026-04-09T10:00:00Z",
        },
        {
            "asset_id": "timeline-asset-01",
            "zone_id": "zone-T",
            "vibration": 7.5,
            "temperature": 38.0,
            "humidity": 46.0,
            "pressure": 1010.0,
            "timestamp": "2026-04-09T10:01:00Z",
        },
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
    assert body["points"][0]["vibration"] == 2.0
    assert body["points"][1]["temperature"] == 38.0


@pytest.mark.asyncio
async def test_alert_actions_persist_and_derive_operator_state():
    payload = {
        "asset_id": "operator-asset-01",
        "zone_id": "zone-O",
        "vibration": 14.0,
        "temperature": 80.0,
        "humidity": 45.0,
        "pressure": 1012.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        event_resp = await client.post("/events/", json=payload)
        assert event_resp.status_code == 202
        event_id = event_resp.json()["event"]["event_id"]

        assign_resp = await client.post(
            f"/alerts/{event_id}/actions",
            json={
                "action_type": "assign",
                "assignee": "Hakki",
                "note": "Forward to maintenance",
            },
        )
        assert assign_resp.status_code == 201
        assign_body = assign_resp.json()
        assert assign_body["state"]["operator_status"] == "assigned"
        assert assign_body["state"]["assigned_to"] == "Hakki"

        resolve_resp = await client.post(
            f"/alerts/{event_id}/actions",
            json={
                "action_type": "resolve",
                "note": "Issue cleared after inspection",
            },
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
