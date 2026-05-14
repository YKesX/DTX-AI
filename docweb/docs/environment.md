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
| `API_HOST` | `0.0.0.0` | No | uvicorn bind host |
| `API_PORT` | `8000` | No | uvicorn bind port |
| `DATABASE_URL` | `sqlite:///./dtx_ai.db` | Yes | SQLite file path; resolved relative to `apps/api/api/` |
| `ANOMALY_THRESHOLD` | `0.5` | No | Minimum class-confidence to flag an anomaly |
| `AI_DEBUG` | `false` | No | Verbose AI logging |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | No | ⚠️ Currently unused — `main.py` hardcodes `allow_origins=["*"]` |

Runtime model selection (read by `services/ai/ai/detector.py`):

| Variable | Default | Description |
|---|---|---|
| `DTX_ACTIVE_MODEL` | from `model_registry.json` `active_model` | One of `lightgbm`, `xgboost`, `random_forest`, `lstm_ae` |
| `DTX_REPLAY_STRICT` | `0` | `1` = disable all fallbacks; selected model must load |
| `DTX_FORCE_STUB` | `0` | `1` = always use the rule-based stub (used by smoke tests) |

Selection precedence at request time: `event.metadata.active_model` > `DTX_ACTIVE_MODEL` > registry's `active_model`.

---

## apps/dashboard

Create `apps/dashboard/.env` (copy from `.env.example`):

| Variable | Default | Required | Description |
|---|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Yes | Backend REST base URL |
| `VITE_WS_URL` | `ws://localhost:8000/ws/events` | Yes | Backend WebSocket URL |

---

## apps/sim

| Variable | Default | Description |
|---|---|---|
| `ISAAC_SIM_PATH` | `/opt/isaac-sim` | Path to Isaac Sim install root |
| `ISAAC_SIM_ENABLED` | `false` | Enable the real adapter call into the USD scene |
| `ISAAC_WS_URL` | `ws://localhost:8211/isaac` | Optional Nucleus / live-sync URL |

The adapter is a logging stub when `ISAAC_SIM_ENABLED=false`. See [docs/isaac_sim_integration.md](https://github.com/YKesX/DTX-AI/blob/main/docs/isaac_sim_integration.md) for what to implement on the Isaac Sim side.

---

## Service Discovery

No service registry or DNS-based discovery. Services find each other via env vars with fixed localhost ports:

| Service | Default URL |
|---|---|
| API | `http://localhost:8000` |
| Dashboard | `http://localhost:5173` |
| Isaac Sim | local install via `ISAAC_SIM_PATH` |

## Switching Models at Runtime

```bash
DTX_ACTIVE_MODEL=xgboost uvicorn main:app --reload --port 8000
```

Or per-request via the event payload:

```json
{ "asset_id": "...", "zone_id": "...", "metadata": { "active_model": "lstm_ae" } }
```

The loader caches per-process on first call, so switching mid-process via `model_registry.json` requires restarting the API.
