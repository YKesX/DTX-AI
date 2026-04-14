---
id: api-reference
title: API Reference
sidebar_position: 5
---

# API Reference

Base URL: `http://localhost:8000`

:::warning Authentication
All endpoints are unauthenticated in the current MVP. `CORS` is set to `allow_origins=["*"]` — must be tightened before production deployment.
:::

---

## Endpoints

### `GET /health`
Liveness check.

**Response 200:**
```json
{ "status": "ok", "timestamp": "2026-04-10T12:00:00Z" }
```

---

### `POST /events/`
Main ingestion route. Accepts a sensor event, runs the full AI pipeline, persists to SQLite, broadcasts over WebSocket.

**Request body:** [`EventIn`](/docs/data-models#eventin)

**Response 202:** [`DashboardAlert`](/docs/data-models#dashboardalert)

```bash
curl -X POST http://localhost:8000/events/ \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "conveyor-belt-01",
    "zone_id": "zone-A",
    "vibration": 14.7,
    "temperature": 82.3
  }'
```

---

### `GET /alerts/`
Recent events with operator state, newest first.

**Query params:** `?limit=50` (1–200, default 50)

**Response 200:**
```json
{
  "alerts": [ /* EventLog[] */ ],
  "count": 42
}
```

---

### `GET /alerts/{event_id}/actions`
Action history + derived operator state for a single alert.

**Response 200:**
```json
{
  "event_id": "uuid",
  "state": { "status": "assigned", "assignee": "Hakkı" },
  "actions": [ /* AlertActionRecord[] */ ]
}
```

---

### `POST /alerts/{event_id}/actions`
Create an operator action on an alert.

**Request body:** [`AlertActionIn`](/docs/data-models#alertactionin)

**Response 201:**
```json
{ "event_id": "uuid", "action": "assign", "state": { ... } }
```

---

### `DELETE /alerts/clear`
Delete all events + operator actions from SQLite. Resets `LiveReplayMetrics`.

**Response 200:**
```json
{ "deleted": 127, "metrics_reset": true }
```

---

### `GET /assets/{asset_id}/timeline`
Per-asset sensor history, oldest to newest.

**Query params:** `?limit=50` (1–200)

**Response 200:** `AssetTimelineResponse` — array of historical readings with anomaly scores.

---

### `GET /metrics/live`
In-memory replay validation metrics snapshot.

**Response 200:**
```json
{
  "total_events": 200,
  "correct_predictions": 174,
  "accuracy": 0.87,
  "per_class_ground_truth": { "bearing_fault": 80, "no_fault": 70, ... },
  "per_class_predicted": { "bearing_fault": 75, "no_fault": 72, ... },
  "confusion_matrix": { "bearing_fault": { "bearing_fault": 70, "no_fault": 8 }, ... },
  "per_model_counts": { "lightgbm": 200 }
}
```

---

### `WS /ws/events`
Real-time push endpoint. Each ingested event broadcasts a full [`DashboardAlert`](/docs/data-models#dashboardalert) JSON object to all connected clients.

```js
const ws = new WebSocket('ws://localhost:8000/ws/events');
ws.onmessage = (e) => {
  const alert = JSON.parse(e.data);
  // alert is a DashboardAlert object
};
```

---

## Internal Service Communication

### API → AI Pipeline (in-process)
The API lazy-imports `ai.pipeline.run_pipeline` inside the route handler (`events.py:94–108`). No network call — direct Python function call via shared `PYTHONPATH`. CPU-bound inference is offloaded to `asyncio.to_thread`.

### API → Isaac Sim Adapter (fire-and-forget)
After broadcasting, `_try_notify_sim(twin_update)` attempts to import and call the sim adapter. All failures are silently swallowed via bare `try/except`.

### Dashboard polling cadence
| Trigger | Endpoint |
|---|---|
| On mount | `GET /alerts/` |
| Every 2s (Dashboard) | `GET /metrics/live` |
| Every 4s (Validation) | `GET /metrics/live` + `GET /alerts/?limit=100` |
| On event select | `GET /assets/{id}/timeline` + `GET /alerts/{id}/actions` |
| Operator action | `POST /alerts/{id}/actions` |
| Clear Logs | `DELETE /alerts/clear` |
