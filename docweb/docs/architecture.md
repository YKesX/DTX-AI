---
id: architecture
title: System Architecture
sidebar_position: 2
---

# System Architecture

## Pipeline Overview

The system follows a **synchronous request-driven pipeline** with a WebSocket broadcast layer.

1. A client (dataset replayer or Isaac Sim adapter) sends a 19-channel sensor frame to FastAPI via `POST /events/`
2. The backend calls the AI service pipeline **in-process** (via Python import) — anomaly detection + SHAP explanation
3. Results are persisted to SQLite, broadcast over WebSocket to all dashboard clients, and forwarded to the Isaac Sim adapter (fire-and-forget)
4. The React dashboard receives events via WebSocket and allows operators to take workflow actions

---

## Component Communication Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│  Data Sources                                                    │
│  scripts/replay_dataset_demo.py ──► POST /events/  (HTTP)        │
│  Isaac Sim adapter (you write)   ──► POST /events/  (HTTP)       │
│  [future] ESP32 / hardware       ──► POST /events/  (HTTP)       │
└──────────────────────────────┬───────────────────────────────────┘
                               │ HTTP :8000
┌──────────────────────────────▼───────────────────────────────────┐
│  apps/api  (FastAPI + uvicorn, port 8000)                        │
│                                                                  │
│  POST /events/      ──► services/ai pipeline (in-process)       │
│  GET  /alerts/      ──► SQLite (aiosqlite)                      │
│  GET/POST /alerts/{id}/actions ──► SQLite                       │
│  DELETE /alerts/clear ──► SQLite + live_metrics reset           │
│  GET  /assets/{id}/timeline ──► SQLite                          │
│  GET  /metrics/live ──► LiveReplayMetrics (in-memory)           │
│  WS   /ws/events    ──► ConnectionManager (broadcast)           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  services/ai  (imported into API process via PYTHONPATH) │   │
│  │  ai/pipeline.py → detector.py → explainer.py            │   │
│  │  model_loader.py  (loads .pkl / .pth from disk)         │   │
│  │  xai_explainer.py (SHAP TreeExplainer)                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  apps/sim adapter (fire-and-forget, optional)                   │
│  ISAAC_SIM_ENABLED=false → stub log only                        │
└──────────┬───────────────────────────────────────────────────────┘
           │ WebSocket ws://localhost:8000/ws/events
           │ HTTP      http://localhost:8000
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  apps/dashboard  (React + Vite, port 5173)                       │
│  useWebSocket.js → pushes DashboardAlert into event list         │
│  GET /alerts/    → initial historical load                       │
│  GET /metrics/live → polled every 2s (Dashboard), 4s (Validation)│
│  GET /assets/{id}/timeline → on event select                     │
│  GET/POST /alerts/{id}/actions → operator workflow               │
└──────────────────────────────────────────────────────────────────┘
           │
           ▼ (future — currently stub only)
┌──────────────────────────────────────────────────────────────────┐
│  NVIDIA Isaac Sim 4.x  (digital twin)                            │
│  Receives TwinUpdate via apps/sim/sim/adapter.py::notify()       │
└──────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| Backend framework | FastAPI | 0.136.1 | REST API + WebSocket server |
| ASGI server | uvicorn[standard] | 0.46.0 | Async server |
| Database driver | aiosqlite | 0.22.1 | Async SQLite |
| Schema validation | Pydantic v2 | 2.13.3 | Request/response models |
| ML — trees | LightGBM | 4.6.0 | Multi-class fault classification |
| ML — trees | XGBoost | 3.2.0 | Multi-class fault classification |
| ML — trees | scikit-learn RF | 1.8.0 | Multi-class fault classification |
| ML — deep | PyTorch (+CUDA) | 2.11.0+cu128 | LSTM-AE + classifier head |
| XAI | SHAP | ≥ 0.45 | Feature attribution |
| Data processing | pandas / numpy | 3.0.2 / 2.4.4 | Dataset I/O |
| Frontend | React | 18.3.1 | UI |
| Build tool | Vite | 5.3.4 | Dev server + bundler |
| CSS | TailwindCSS | 3.4.6 | Styling |
| Charts | Recharts | 2.12.7 | Line/bar charts |
| Routing | React Router v6 | 6.24.0 | Client-side navigation |
| Shared schemas | dtx-ai-shared | 2.0.0 | Inter-service contracts |

---

## Design Decisions

### Why in-process AI?
The AI pipeline is imported directly into the FastAPI process rather than running as a separate microservice. This eliminates network latency and serialization overhead for the demo path. A message queue (Redis Streams / NATS) is flagged for high-throughput production use.

### Why SQLite?
SQLite is zero-configuration and sufficient for single-node demo throughput. The architecture notes flag PostgreSQL as the upgrade path when concurrent write volume grows.

### Why WebSocket for real-time?
Server-Sent Events would work for read-only push, but WebSocket allows bidirectional communication and is simpler to manage under the existing FastAPI stack.
