# Architecture — DTX-AI Smart Warehouse XAI Digital Twin

## System Context

DTX-AI is a university capstone project that demonstrates AI-driven anomaly
detection, explainability (XAI), and digital-twin synchronisation for a
simulated smart warehouse.

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
│  POST /events   GET /alerts   GET /health   WS /ws/events   │
│                      │                                      │
│            calls services/ai pipeline                       │
│                      │                                      │
│  ┌───────────────────▼──────────────────┐                   │
│  │          services/ai                 │                   │
│  │  detector.py  ──►  explainer.py      │                   │
│  └───────────────────┬──────────────────┘                   │
│                      │ TwinUpdate                           │
│  ┌───────────────────▼──────────────────┐                   │
│  │          apps/sim adapter            │                   │
│  │  (optional — skipped if not present) │                   │
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
2. **AI pipeline** — `services/ai.pipeline.run_pipeline(event)` returns `(AnomalyResult, ExplanationResult)`.
3. **Persistence** — the API inserts an `EventLog` row into SQLite.
4. **Broadcast** — a `DashboardAlert` (event + anomaly + explanation) is sent over WebSocket.
5. **Digital twin** — a `TwinUpdate` is passed to `apps/sim.adapter.notify()`.
6. **Dashboard** — the React frontend receives the WebSocket message and updates the UI.

---

## Scalability Notes (post-MVP)

- Replace SQLite with PostgreSQL when data volume grows.
- Replace rule-based detector with a trained Isolation Forest or Autoencoder.
- Add a message queue (Redis Streams or NATS) between API and AI service for high-throughput scenarios.
- Isaac Sim integration can be extended to use Omniverse Nucleus for multi-user scene collaboration.
