---
id: services
title: Service Breakdown
sidebar_position: 4
---

# Service Breakdown

## apps/api — FastAPI Backend

Central coordination hub. Accepts sensor events, orchestrates the AI pipeline, persists results to SQLite, broadcasts alerts to the dashboard via WebSocket.

- **Entry point:** `uvicorn main:app --reload --port 8000`
- **Port:** HTTP + WebSocket on `:8000`

**Responsibilities:**
- Validate and accept `EventIn` payloads at `POST /events/`
- Lazy-import and call `services/ai` → `run_pipeline(event)`
- Write `EventLog` + `event_actions` rows to SQLite asynchronously
- Update `LiveReplayMetrics` in-memory when `source=dataset_replay`
- Broadcast `DashboardAlert` JSON to all WebSocket clients
- Fire-and-forget `TwinUpdate` to the Isaac Sim adapter
- Serve alert history, operator actions, asset drilldown, live metrics

---

## services/ai — AI / XAI Pipeline

All ML inference and explainability logic. Not a network service — a single async function imported into the API process.

- **Entry point:** `pipeline.py` → `run_pipeline(event: EventIn) → (AnomalyResult, ExplanationResult)`
- **Transport:** Direct Python import via `PYTHONPATH`

**Responsibilities:**
- Load active model from registry on first call (cached in-process)
- Build 5-event rolling window feature vector per `asset:zone` key
- Run inference: LightGBM / XGBoost / Random Forest / LSTM-AE
- Merge model output with rule-based guardrails (non-strict mode)
- Generate SHAP feature attribution via `xai_explainer.py`
- Fall back gracefully to rule-based detection when models fail
- Support strict replay mode (`DTX_REPLAY_STRICT=1`)

---

## apps/dashboard — React Frontend

Operator-facing real-time control panel.

- **Entry point:** `npm run dev` → Vite dev server on `:5173`
- **Communicates to API:** via `VITE_API_BASE_URL` (HTTP) + `VITE_WS_URL` (WebSocket)

**Responsibilities:**
- Live event list from WebSocket + REST initial load
- `EventTable` with Operator and Developer view modes + multi-field filtering
- `ExplanationPanel` with SHAP feature bars and operator action buttons
- `TrendChart` (last 20 anomaly scores) + `AssetDrilldownChart` (per-asset history)
- `/validation` page — confusion matrix, class distributions, per-model counts
- Operator workflow: acknowledge → assign → escalate → resolve

---

## apps/sim — Isaac Sim Adapter *(stub)*

Bridge between the DTX-AI API and NVIDIA Isaac Sim 4.x.

- **Entry point:** `sim/adapter.py::notify(update: TwinUpdate)` — called fire-and-forget from the API
- **Status:** Logging stub only. No real USD/Omniverse calls are made.
- When `ISAAC_SIM_ENABLED=false` (default): logs the update and returns

All `ImportError` and runtime failures from the sim adapter are silently suppressed to ensure the Isaac Sim stub never blocks event processing.

---

## packages/shared — Canonical Schemas

Single source of truth for all inter-service data contracts.

- **Package:** `dtx-ai-shared` v0.1.0 (installed via `pip install -e packages/shared`)
- **Contents:** All Pydantic v2 schemas — `EventIn`, `AnomalyResult`, `ExplanationResult`, `DashboardAlert`, `TwinUpdate`, `EventLog`, `AlertActionIn`, `AlertActionRecord`

See [Data Models](/docs/data-models) for full schema reference.
