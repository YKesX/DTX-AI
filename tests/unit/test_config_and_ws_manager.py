import importlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../apps/api"))

import api.config as config_module  # noqa: E402
from api.ws_manager import ConnectionManager  # noqa: E402


class _FakeWebSocket:
    def __init__(self, *, should_fail: bool = False):
        self.accepted = False
        self.messages = []
        self.should_fail = should_fail

    async def accept(self):
        self.accepted = True

    async def send_text(self, message: str):
        if self.should_fail:
            raise RuntimeError("socket down")
        self.messages.append(message)


def test_settings_reload_reads_environment_values(monkeypatch):
    monkeypatch.setenv("API_HOST", "127.0.0.1")
    monkeypatch.setenv("API_PORT", "9000")
    monkeypatch.setenv("ANOMALY_THRESHOLD", "0.75")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./custom.db")
    monkeypatch.setenv("AI_DEBUG", "true")
    monkeypatch.setenv("CORS_ORIGINS", "http://one.test, http://two.test")

    module = importlib.reload(config_module)
    module.get_settings.cache_clear()
    settings = module.get_settings()

    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 9000
    assert settings.anomaly_threshold == 0.75
    assert settings.database_url == "sqlite:///./custom.db"
    assert settings.ai_debug is True
    assert settings.cors_origins == ["http://one.test", "http://two.test"]


def test_get_settings_is_cached(monkeypatch):
    monkeypatch.delenv("API_HOST", raising=False)
    module = importlib.reload(config_module)
    module.get_settings.cache_clear()

    first = module.get_settings()
    second = module.get_settings()

    assert first is second


@pytest.mark.asyncio
async def test_connection_manager_connect_and_disconnect():
    manager = ConnectionManager()
    ws = _FakeWebSocket()

    await manager.connect(ws)

    assert ws.accepted is True
    assert manager.active_connections == 1

    manager.disconnect(ws)
    assert manager.active_connections == 0


@pytest.mark.asyncio
async def test_connection_manager_broadcast_serializes_payload_and_drops_dead_connections():
    manager = ConnectionManager()
    alive = _FakeWebSocket()
    dead = _FakeWebSocket(should_fail=True)

    await manager.connect(alive)
    await manager.connect(dead)
    await manager.broadcast({"status": "ok", "value": 3})

    assert len(alive.messages) == 1
    assert json.loads(alive.messages[0]) == {"status": "ok", "value": 3}
    assert manager.active_connections == 1
