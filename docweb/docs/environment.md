---
id: environment
title: Environment & Configuration
sidebar_position: 10
---

# Environment & Configuration

## apps/api

Create `apps/api/.env` (copy from `.env.example`):

| Variable | Default | Required | Description |
|---|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./dtx_ai.db` | Yes | SQLite file path |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | No | ⚠️ Unused — hardcoded `*` in `main.py` |
| `ISAAC_SIM_ENABLED` | `false` | No | Enable Isaac Sim adapter |
| `ISAAC_SIM_HOST` | `localhost` | No | Isaac Sim host address |
| `MODEL_NAME` | `lightgbm` | No | Active model: `lightgbm` \| `xgboost` \| `random_forest` \| `lstm_ae` |
| `DTX_REPLAY_STRICT` | `0` | No | `1` = disable all fallbacks in replay mode |

## apps/dashboard

Create `apps/dashboard/.env` (copy from `.env.example`):

| Variable | Default | Required | Description |
|---|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Yes | Backend REST base URL |
| `VITE_WS_URL` | `ws://localhost:8000/ws/events` | Yes | Backend WebSocket URL |

## Service Discovery

No service registry or DNS-based discovery. Services find each other via env vars with fixed localhost ports:

| Service | Default URL |
|---|---|
| API | `http://localhost:8000` |
| Dashboard | `http://localhost:5173` |
| Isaac Sim | `localhost` (via `ISAAC_SIM_HOST`) |

## Model Selection

Change the active model at runtime by setting `MODEL_NAME` before starting the API:

```bash
MODEL_NAME=xgboost uvicorn main:app --reload --port 8000
```

Or switch mid-session via `model_registry.json` — the loader caches per-process on first call.
