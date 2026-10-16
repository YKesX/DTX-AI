---
id: architecture
title: System Architecture
sidebar_position: 2
---

# Architecture — DTX-AI v3.0 Final

DTX-AI is a local smart-warehouse anomaly detection and explainability
application. The release includes the FastAPI backend, React console,
seven model families, dataset replay, and ESP32 hardware ingestion.

```text
Dataset replay --------------------+
                                   v
ESP32 -> hardware bridge -> POST /events/ -> AI pipeline
                                              |
                                       SQLite + metrics
                                              |
                                         WebSocket
                                              v
                          Dashboard / Events / AI Validation / Settings
```

## Components

| Component | Responsibility |
| --- | --- |
| `apps/api` | Validate events, run inference, persist records, broadcast updates, and manage demos and operator actions |
| `services/ai` | Registry-based model loading, inference, tree-model SHAP explanations, and documented fallbacks |
| `apps/dashboard` | Live monitoring, saved event history, model validation, operator actions, and local preferences |
| `HW` | ESP32 firmware for the DS18B20 and BMP280 |
| `scripts/hw_demo_bridge.py` | Map hardware readings into model inputs and record real/derived/synthesized provenance |
| `packages/shared` | Canonical Pydantic schemas |

## Request flow

1. Replay or hardware ingestion sends an `EventIn` to `POST /events/`.
2. The API calls `ai.pipeline.run_pipeline` in-process.
3. The result is persisted in SQLite. Dataset replay also updates in-memory accuracy metrics.
4. A `DashboardAlert` is broadcast over `/ws/events`.
5. The console renders the event, explanation, and operator controls.
6. Operator actions are saved through `/alerts/{event_id}/actions`.

The API listens on port 8000; the dashboard development server uses 5173.
The hardware node serves `/health` and `/reading` on port 80.

## Verification and boundaries

`tests/unit`, `tests/smoke`, and `tests/integration` cover helpers, schemas,
model loading, replay, sensor fault handling, and API workflows.

The final release targets a local demonstration environment. Live Isaac Sim
integration, production authentication, and distributed infrastructure are
outside its scope. Dataset limitations and the synthesized hardware channels
are documented in [Known Limitations](/docs/known-issues).
