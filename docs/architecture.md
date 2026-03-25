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
