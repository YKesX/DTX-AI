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
    from api.database import init_db
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
async def test_get_alerts():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/alerts/")
    assert resp.status_code == 200
    assert "alerts" in resp.json()
