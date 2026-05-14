# Architecture — DTX-AI Smart Warehouse XAI Digital Twin

## System Context

DTX-AI is a university capstone project that demonstrates AI-driven anomaly
detection, explainability (XAI), and operator visibility for a
smart warehouse software stack.

Current critical demo path excludes Isaac Sim and focuses on real API ingestion,
runtime model inference, explanation, and dashboard visibility.

---

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                         │
│  Browser (React + Vite dashboard)  ◄──── WebSocket          │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP / WebSocket
┌─────────────────────▼───────────────────────────────────────┐
│                  apps/api  (FastAPI)                        │
│  POST /events   GET /alerts   GET /health   GET /metrics/live  WS /ws/events   │
│                      │                                      │
│            calls services/ai pipeline                       │
│                      │                                      │
│  ┌───────────────────▼──────────────────┐                   │
│  │          services/ai                 │                   │
│  │  detector.py  ──►  explainer.py      │                   │
│  └───────────────────┬──────────────────┘                   │
│                      │ TwinUpdate                           │
│  ┌───────────────────▼──────────────────┐                   │
│  │      in-memory replay metrics        │                   │
│  └───────────────────┬──────────────────┘                   │
│                      │                                      │
│  ┌───────────────────▼──────────────────┐                   │
│  │          apps/sim adapter            │                   │
│  │   (optional / later integration)     │                   │
│  └───────────────────┬──────────────────┘                   │
└────────────────────────────────────────────────────────────-┘
                       │
              ┌────────▼────────┐
              │  NVIDIA Isaac   │
              │     Sim 4.x     │
              └─────────────────┘
```

---

## Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `apps/api` | Accepts events, orchestrates pipeline, persists to SQLite, broadcasts alerts |
| `services/ai` | Anomaly detection (stub → real model), XAI explanation generator |
| `apps/dashboard` | Real-time alert display, event history, explanation panel |
| `apps/sim` | Isaac Sim adapter — updates digital-twin asset status |
| `packages/shared` | Canonical Pydantic schemas, single source of truth for inter-service contracts |
| `data/` | Synthetic event data and local SQLite database |

---

## Data Flow (MVP)

1. **Event ingested** — `POST /events` receives an `EventIn` JSON payload.
    Source can be synthetic seeding or dataset replay.
2. **AI pipeline** — `services/ai.pipeline.run_pipeline(event)` returns `(AnomalyResult, ExplanationResult)`.
3. **Persistence** — the API inserts an `EventLog` row into SQLite.
4. **Replay metrics** — if `event.metadata.source=dataset_replay`, running metrics are updated in memory.
5. **Broadcast** — a `DashboardAlert` (event + anomaly + explanation) is sent over WebSocket.
6. **Digital twin** — a `TwinUpdate` is passed to `apps/sim.adapter.notify()` (optional).
7. **Dashboard** — the React frontend receives the WebSocket message and updates the UI.

---

## Scalability Notes (post-MVP)

- Replace SQLite with PostgreSQL when data volume grows.
- Replace rule-based detector with a trained Isolation Forest or Autoencoder.
- Add a message queue (Redis Streams or NATS) between API and AI service for high-throughput scenarios.
- Isaac Sim integration can be extended to use Omniverse Nucleus for multi-user scene collaboration.

---

## Verification Layers

The current codebase is verified through three complementary test layers:

1. **Unit tests** — `tests/unit/`
   Covers helper logic in `apps/api/api/routes/events.py`, `apps/api/api/database.py`,
   `apps/api/api/config.py`, `apps/api/api/ws_manager.py`, and the stubbed Isaac Sim
   modules under `apps/sim/sim/`.
2. **Smoke tests** — `tests/smoke/`
   Covers schemas, replay helper utilities, model-loader behavior, and the stable
   rule-based AI fallback path.
3. **Integration tests** — `tests/integration/`
   Exercises the FastAPI app through ASGI requests for ingestion, metrics, timeline,
   alerts, and operator-action workflows.

Recommended repo-root command:

```bash
PYTHONPATH="packages:services:services/ai:apps/api:apps/sim" .venv/bin/pytest -q
```

Current local baseline after the latest unit-test expansion: `54 passed`.
