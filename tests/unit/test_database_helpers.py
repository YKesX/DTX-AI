import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../apps/api"))

from api import database  # noqa: E402


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "unit_test.db"
    monkeypatch.setattr(database, "_DB_PATH", Path(db_path))
    return db_path


@pytest.mark.asyncio
async def test_database_round_trip_with_operator_state_and_timeline(isolated_db):
    await database.init_db()
    await database.insert_event(
        {
            "event_id": "evt-1",
            "asset_id": "asset-01",
            "zone_id": "zone-A",
            "timestamp": datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc),
            "anomaly_score": 0.73,
            "is_anomaly": True,
            "anomaly_type": "bearing_wear",
            "severity": "warning",
            "summary": "Bearing wear detected.",
            "raw_payload": {
                "temperature_c": 27.2,
                "vibration_magnitude": 9.82,
                "pseudo_pressure_pa": -5.56,
                "power_dissipated_w": 299.0,
                "metadata": {
                    "predicted_label": "bearing_wear",
                },
            },
        }
    )

    assert await database.event_exists("evt-1") is True

    action = await database.insert_event_action(
        event_id="evt-1",
        action_type="assign",
        assignee="Hakki",
        note="Forward to maintenance",
    )
    assert action["action_type"] == "assign"

    await database.insert_event_action(
        event_id="evt-1",
        action_type="resolve",
        note="Cleared after inspection",
    )

    actions = await database.fetch_event_actions("evt-1")
    assert len(actions) == 2
    assert actions[0]["action_type"] == "resolve"
    assert actions[1]["action_type"] == "assign"

    state = await database.fetch_operator_states_for_events(["evt-1"])
    assert state["evt-1"]["operator_status"] == "resolved"
    assert state["evt-1"]["assigned_to"] == "Hakki"
    assert state["evt-1"]["last_action"] == "resolve"

    rows = await database.fetch_recent_events_with_operator_state(limit=10)
    assert len(rows) == 1
    assert rows[0]["operator_status"] == "resolved"
    assert rows[0]["assigned_to"] == "Hakki"

    points = await database.fetch_asset_timeline("asset-01", limit=10)
    assert len(points) == 1
    assert points[0]["predicted_label"] == "bearing_wear"
    assert points[0]["temperature_c"] == 27.2

    deleted = await database.clear_events()
    assert deleted == 1
    assert await database.event_exists("evt-1") is False


def test_parse_payload_handles_dict_json_and_invalid_input():
    assert database._parse_payload({"a": 1}) == {"a": 1}
    assert database._parse_payload('{"a": 1}') == {"a": 1}
    assert database._parse_payload("{invalid") == {}
    assert database._parse_payload(None) == {}


def test_operator_status_mapping_uses_safe_default():
    assert database._operator_status_from_action("acknowledge") == "acknowledged"
    assert database._operator_status_from_action("assign") == "assigned"
    assert database._operator_status_from_action("escalate") == "escalated"
    assert database._operator_status_from_action("resolve") == "resolved"
    assert database._operator_status_from_action("mystery") == "new"
