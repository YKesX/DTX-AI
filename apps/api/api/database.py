"""
SQLite persistence layer using aiosqlite.

For the MVP we keep a single `events` table.
Replace with a proper ORM (SQLAlchemy async) when the schema grows.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from api.config import settings

# Strip the "sqlite:///" prefix to get the file path and normalize it
_raw_db_path = settings.database_url.replace("sqlite:///", "", 1)
_DB_PATH = Path(_raw_db_path)
if not _DB_PATH.is_absolute():
    # Resolve relative paths against this module's directory to avoid CWD sensitivity
    _DB_PATH = (Path(__file__).resolve().parent / _DB_PATH).resolve()


async def init_db() -> None:
    """Create the events table if it does not exist."""
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


async def clear_events() -> int:
    """Delete all persisted events and return deleted row count."""
    async with aiosqlite.connect(_DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) AS count FROM events") as cursor:
            row = await cursor.fetchone()
            before_count = int(row[0] if row else 0)
        await db.execute("DELETE FROM events")
        await db.commit()
    return before_count
