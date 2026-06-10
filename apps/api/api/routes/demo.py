"""Demo orchestration — start/stop the dataset replay or the IRL hardware
bridge from the dashboard.

The dashboard selects the demo mode ("dataset" replays the leakage-safe
holdout through scripts/replay_dataset_demo.py; "hardware" streams live
ESP32 sensor readings through scripts/hw_demo_bridge.py). Both scripts POST
into this same API, so downstream behaviour — pipeline, persistence,
WebSocket broadcast — is identical for both modes.

Only one demo process runs at a time.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[4]
REPLAY_SCRIPT = REPO_ROOT / "scripts" / "replay_dataset_demo.py"
BRIDGE_SCRIPT = REPO_ROOT / "scripts" / "hw_demo_bridge.py"
REGISTRY_PATH = REPO_ROOT / "services" / "ai" / "ai" / "models" / "shared" / "model_registry.json"
LOG_PATH = Path(os.getenv("DTX_DEMO_LOG", "/tmp/dtx_demo_runner.log"))

_state: dict[str, Any] = {
    "process": None,
    "log_handle": None,
    "mode": None,
    "params": {},
    "started_at": None,
}


class DemoStartRequest(BaseModel):
    mode: Literal["dataset", "hardware"]
    model: str = Field(default="lightgbm", max_length=64)
    # dataset mode
    split: Literal["holdout", "episode_holdout", "temporal", "all"] = "holdout"
    count: int = Field(default=100, ge=0, le=100_000)
    delay: float = Field(default=0.5, ge=0.0, le=60.0)
    strict: bool = False
    # hardware mode
    esp32_url: str = Field(default="http://dtx-esp32.local", max_length=200)
    interval: float = Field(default=1.0, ge=0.05, le=60.0)


def _registry_model_keys() -> list[str]:
    try:
        registry = json.loads(REGISTRY_PATH.read_text())
        return [k for k, cfg in registry.get("models", {}).items() if cfg.get("enabled")]
    except Exception:
        return []


def _process_running() -> bool:
    proc = _state["process"]
    return proc is not None and proc.poll() is None


def _close_log_handle() -> None:
    handle = _state.get("log_handle")
    if handle is not None:
        try:
            handle.close()
        except Exception:
            pass
        _state["log_handle"] = None


def _build_command(req: DemoStartRequest, api_url: str) -> list[str]:
    if req.mode == "dataset":
        cmd = [
            sys.executable, str(REPLAY_SCRIPT),
            "--url", api_url,
            "--model", req.model,
            "--split", req.split,
            "--limit", str(req.count),
            "--delay", str(req.delay),
        ]
        if req.strict:
            cmd.append("--strict")
        return cmd
    cmd = [
        sys.executable, str(BRIDGE_SCRIPT),
        "--url", api_url,
        "--model", req.model,
        "--esp32-url", req.esp32_url,
        "--interval", str(req.interval),
    ]
    if req.count:
        cmd += ["--count", str(req.count)]
    return cmd


@router.get("/models")
async def demo_models():
    """Model keys the demo selector can offer."""
    return {"models": _registry_model_keys()}


@router.get("/status")
async def demo_status():
    running = _process_running()
    proc = _state["process"]
    log_tail: list[str] = []
    if LOG_PATH.exists():
        try:
            log_tail = LOG_PATH.read_text(errors="ignore").splitlines()[-15:]
        except Exception:
            log_tail = []
    return {
        "running": running,
        "mode": _state["mode"] if (running or proc is not None) else None,
        "params": _state["params"] if (running or proc is not None) else {},
        "started_at": _state["started_at"],
        "returncode": (None if proc is None else proc.poll()),
        "log_tail": log_tail,
    }


@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
async def demo_start(req: DemoStartRequest):
    if _process_running():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A '{_state['mode']}' demo is already running — stop it first.",
        )

    script = REPLAY_SCRIPT if req.mode == "dataset" else BRIDGE_SCRIPT
    if not script.exists():
        raise HTTPException(status_code=500, detail=f"Demo script missing: {script}")

    known_models = _registry_model_keys()
    if known_models and req.model not in known_models:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown model '{req.model}'. Enabled models: {known_models}",
        )

    api_port = os.getenv("API_PORT", "8000")
    api_url = f"http://localhost:{api_port}"

    _close_log_handle()
    log_handle = LOG_PATH.open("w", encoding="utf-8")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        _build_command(req, api_url),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        cwd=str(REPO_ROOT),
        env=env,
    )

    _state.update(
        process=proc,
        log_handle=log_handle,
        mode=req.mode,
        params=req.model_dump(),
        started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    return {"started": True, "mode": req.mode, "pid": proc.pid}


@router.post("/stop")
async def demo_stop():
    proc = _state["process"]
    if proc is None or proc.poll() is not None:
        _close_log_handle()
        return {"stopped": False, "detail": "No demo is running."}
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    _close_log_handle()
    return {"stopped": True, "returncode": proc.returncode}
