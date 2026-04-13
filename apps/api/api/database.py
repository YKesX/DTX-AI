"""
SQLite persistence layer using aiosqlite.

The current dashboard iteration stores processed events plus operator actions.
Replace with a proper ORM (SQLAlchemy async) when the schema grows.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from api.config import settings

# Strip the "sqlite:///" prefix to get the file path and normalize it
_raw_db_path = settings.database_url.replace("sqlite:///", "", 1)
_DB_PATH = Path(_raw_db_path)
if not _DB_PATH.is_absolute():
    # Resolve relative paths against this module's directory to avoid CWD sensitivity
    _DB_PATH = (Path(__file__).resolve().parent / _DB_PATH).resolve()


async def init_db() -> None:
    """Create the events and operator-action tables if they do not exist."""
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id    TEXT PRIMARY KEY,
                asset_id    TEXT NOT NULL,
                zone_id     TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                anomaly_score REAL NOT NULL,
                is_anomaly  INTEGER NOT NULL,
                anomaly_type TEXT NOT NULL,
                severity    TEXT NOT NULL,
                summary     TEXT NOT NULL,
                raw_payload TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS event_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                assignee TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(event_id) REFERENCES events(event_id) ON DELETE CASCADE
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_event_actions_event_id_created_at
            ON event_actions(event_id, created_at DESC)
            """
        )
        await db.commit()


async def insert_event(row: dict) -> None:
    """Persist a processed event row."""
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO events
            (event_id, asset_id, zone_id, timestamp, anomaly_score,
             is_anomaly, anomaly_type, severity, summary, raw_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row["event_id"]),
                row["asset_id"],
                row["zone_id"],
                row["timestamp"].isoformat() if isinstance(row["timestamp"], datetime) else row["timestamp"],
                row["anomaly_score"],
                int(row["is_anomaly"]),
                row["anomaly_type"],
                row["severity"],
                row["summary"],
                json.dumps(row.get("raw_payload", {})),
            ),
        )
        await db.commit()


async def fetch_recent_events(limit: int = 50) -> list[dict]:
    """Return the most recent events ordered by timestamp descending."""
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


def _parse_payload(raw_payload: Any) -> dict[str, Any]:
    if isinstance(raw_payload, dict):
        return raw_payload
    if isinstance(raw_payload, str):
        try:
            return json.loads(raw_payload)
        except json.JSONDecodeError:
            return {}
    return {}


def _operator_status_from_action(action_type: str | None) -> str:
    mapping = {
        "acknowledge": "acknowledged",
        "assign": "assigned",
        "escalate": "escalated",
        "resolve": "resolved",
    }
    return mapping.get(str(action_type or "").strip().lower(), "new")


async def event_exists(event_id: str) -> bool:
    async with aiosqlite.connect(_DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM events WHERE event_id = ? LIMIT 1",
            (str(event_id),),
        ) as cursor:
            row = await cursor.fetchone()
    return row is not None


async def insert_event_action(
    *,
    event_id: str,
    action_type: str,
    note: str = "",
    assignee: str = "",
) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(_DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO event_actions (event_id, action_type, note, assignee, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(event_id), action_type, note, assignee, created_at),
        )
        await db.commit()
        action_id = cursor.lastrowid
    return {
        "id": int(action_id),
        "event_id": str(event_id),
        "action_type": action_type,
        "note": note,
        "assignee": assignee,
        "created_at": created_at,
    }


async def fetch_event_actions(event_id: str) -> list[dict[str, Any]]:
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, event_id, action_type, note, assignee, created_at
            FROM event_actions
            WHERE event_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            """,
            (str(event_id),),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def fetch_operator_states_for_events(event_ids: list[str]) -> dict[str, dict[str, Any]]:
    normalized_ids = [str(event_id) for event_id in event_ids if str(event_id)]
    if not normalized_ids:
        return {}

    placeholders = ",".join("?" for _ in normalized_ids)
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""
            SELECT event_id, action_type, note, assignee, created_at
            FROM event_actions
            WHERE event_id IN ({placeholders})
            ORDER BY event_id ASC, datetime(created_at) DESC, id DESC
            """,
            tuple(normalized_ids),
        ) as cursor:
            rows = await cursor.fetchall()

    states: dict[str, dict[str, Any]] = {}
    for row in rows:
        event_id = str(row["event_id"])
        state = states.setdefault(
            event_id,
            {
                "operator_status": "new",
                "assigned_to": "",
                "last_action": None,
                "last_action_at": None,
            },
        )
        if state["last_action"] is None:
            state["last_action"] = row["action_type"]
            state["last_action_at"] = row["created_at"]
            state["operator_status"] = _operator_status_from_action(row["action_type"])
        if not state["assigned_to"] and str(row["assignee"] or "").strip():
            state["assigned_to"] = str(row["assignee"]).strip()

    for event_id in normalized_ids:
        states.setdefault(
            event_id,
            {
                "operator_status": "new",
                "assigned_to": "",
                "last_action": None,
                "last_action_at": None,
            },
        )
    return states


async def fetch_recent_events_with_operator_state(limit: int = 50) -> list[dict[str, Any]]:
    rows = await fetch_recent_events(limit=limit)
    states = await fetch_operator_states_for_events(
        [str(row.get("event_id", "")) for row in rows]
    )
    enriched: list[dict[str, Any]] = []
    for row in rows:
        event_id = str(row.get("event_id", ""))
        enriched.append({**row, **states.get(event_id, {})})
    return enriched


async def fetch_asset_timeline(asset_id: str, limit: int = 50) -> list[dict[str, Any]]:
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT event_id, timestamp, anomaly_score, severity, raw_payload
            FROM events
            WHERE asset_id = ?
            ORDER BY datetime(timestamp) DESC
            LIMIT ?
            """,
            (asset_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()

    points: list[dict[str, Any]] = []
    for row in reversed(rows):
        payload = _parse_payload(row["raw_payload"])
        metadata = payload.get("metadata") or {}
        points.append(
            {
                "event_id": row["event_id"],
                "timestamp": row["timestamp"],
                "vibration": payload.get("vibration"),
                "temperature": payload.get("temperature"),
                "humidity": payload.get("humidity"),
                "pressure": payload.get("pressure"),
                "anomaly_score": row["anomaly_score"],
                "severity": row["severity"],
                "predicted_label": metadata.get("predicted_label"),
            }
        )
    return points


async def clear_events() -> int:
    """Delete all persisted events and return deleted row count."""
    async with aiosqlite.connect(_DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) AS count FROM events") as cursor:
            row = await cursor.fetchone()
            before_count = int(row[0] if row else 0)
        await db.execute("DELETE FROM event_actions")
        await db.execute("DELETE FROM events")
        await db.commit()
    return before_count
