---
id: services
title: Service Breakdown
sidebar_position: 4
---

# Service Breakdown

## apps/api — FastAPI Backend

Central coordination hub. Accepts sensor frames, orchestrates the AI pipeline, persists results to SQLite, broadcasts alerts to the dashboard via WebSocket.

- **Entry point:** `uvicorn main:app --reload --port 8000`
- **Port:** HTTP + WebSocket on `:8000`

**Responsibilities:**
- Validate and accept 19-channel `EventIn` payloads at `POST /events/`
- Lazy-import and call `services/ai` → `run_pipeline(event)`
- Write `EventLog` + `event_actions` rows to SQLite asynchronously
- Update `LiveReplayMetrics` in-memory when `metadata.source = "dataset_replay"`
- Broadcast `DashboardAlert` JSON to all WebSocket clients
- Fire-and-forget `TwinUpdate` to the Isaac Sim adapter
- Serve alert history, operator actions, asset drilldown, live metrics

---

## services/ai — AI / XAI Pipeline

All ML inference and explainability logic. Not a network service — a single async function imported into the API process.

- **Entry point:** `pipeline.py` → `run_pipeline(event: EventIn) → (AnomalyResult, ExplanationResult)`
- **Transport:** Direct Python import via `PYTHONPATH`

**Responsibilities:**
- Load active model from `model_registry.json` on first call (cached in-process)
- Extract the 19 sensor channels from `EventIn` and scale them with `scaler.pkl`
- Run inference: LightGBM / XGBoost / Random Forest / LSTM-AE+CLS
- Merge model output with rule-based guardrails (non-strict mode)
- Generate SHAP feature attribution via `xai_explainer.py`
- Fall back gracefully to the rule-based detector when models fail
- Support strict replay mode (`DTX_REPLAY_STRICT=1`)
- Expose architecture in `ai/lstm_classifier.py` so the training notebook and the runtime always agree on `state_dict` keys

---

## apps/dashboard — React Frontend

Operator-facing real-time control panel.

- **Entry point:** `npm run dev` → Vite dev server on `:5173`
- **Communicates with API** via `VITE_API_BASE_URL` (HTTP) + `VITE_WS_URL` (WebSocket)

**Responsibilities:**
- Live event list from WebSocket + REST initial load
- `EventTable` with Operator and Developer view modes + multi-field filtering
- `ExplanationPanel` with SHAP feature bars and operator action buttons
- `TrendChart` (last 20 anomaly scores) + `AssetDrilldownChart` (per-asset history)
- `/validation` page — confusion matrix, class distributions, per-model counts
- Operator workflow: acknowledge → assign → escalate → resolve

---

## apps/sim — Isaac Sim Adapter

Bridge between the DTX-AI API and NVIDIA Isaac Sim 4.x.

- **Entry point:** `sim/adapter.py::notify(update: TwinUpdate)` — called fire-and-forget from the API
- **Status:** Logging stub. When `ISAAC_SIM_ENABLED=true` it calls into `sim.scene.update_asset_status`, which is itself a placeholder. The Isaac Sim team owns the implementation — see [docs/isaac_sim_integration.md](https://github.com/YKesX/DTX-AI/blob/main/docs/isaac_sim_integration.md).

All `ImportError`s and runtime failures from the sim adapter are silently suppressed so a missing or down sim never blocks event processing.

---

## packages/shared — Canonical Schemas

Single source of truth for all inter-service data contracts.

- **Package:** `dtx-ai-shared` (installed via `pip install -e packages/shared`)
- **Contents:** All Pydantic v2 schemas — `EventIn`, `AnomalyResult`, `ExplanationResult`, `DashboardAlert`, `TwinUpdate`, `EventLog`, `AlertActionIn`, `AlertActionRecord`, `AssetTimelinePoint`, `AssetTimelineResponse`

See [Data Models](/docs/data-models) for the full schema reference.
