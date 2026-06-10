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
{ "status": "ok", "timestamp": "2026-05-14T12:00:00Z" }
```

---

### `POST /events/`
Main ingestion route. Accepts a 19-channel telemetry frame, runs the AI pipeline, persists to SQLite, broadcasts over WebSocket.

**Request body:** [`EventIn`](/docs/data-models#eventin)

**Response 202:** [`DashboardAlert`](/docs/data-models#dashboardalert)

```bash
curl -X POST http://localhost:8000/events/ \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "forklift-01",
    "zone_id": "zone-A",
    "imu_lin_acc_x": -9.77, "imu_lin_acc_y": 0.0, "imu_lin_acc_z": 0.86,
    "imu_ang_vel_x":  0.0,  "imu_ang_vel_y": 0.0, "imu_ang_vel_z": 0.0,
    "vibration_magnitude": 9.82,
    "lift_joint_position": -0.15, "lift_force_z": -0.44,
    "lift_joint_velocity": 0.0,
    "pseudo_pressure_pa": -5.56,
    "drive_joint_velocity": 0.0,  "drive_joint_effort": 2812.0,
    "roller_fl_velocity": 0.01,   "roller_fr_velocity": 0.0,
    "roller_bl_velocity": 0.01,   "roller_br_velocity": 0.0,
    "power_dissipated_w": 299.0,
    "temperature_c": 27.2,
    "metadata": { "source": "isaac_sim", "active_model": "lightgbm" }
  }'
```

The example above is a `bearing_wear` profile drawn from per-class training-data means. See [Data Models](/docs/data-models) for the full field list and units.

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
  "state": {
    "operator_status": "assigned",
    "assigned_to": "Hakki",
    "last_action": "assign",
    "last_action_at": "2026-05-14T12:05:00Z"
  },
  "actions": [ /* AlertActionRecord[] */ ]
}
```

---

### `POST /alerts/{event_id}/actions`
Create an operator action on an alert.

**Request body:** [`AlertActionIn`](/docs/data-models#alertactionin)

**Response 201:**
```json
{
  "event_id": "uuid",
  "action": {
    "id": 12,
    "event_id": "uuid",
    "action_type": "assign",
    "note": "Assign to shift lead",
    "assignee": "Hakki",
    "created_at": "2026-05-14T12:05:00Z"
  },
  "state": {
    "operator_status": "assigned",
    "assigned_to": "Hakki",
    "last_action": "assign",
    "last_action_at": "2026-05-14T12:05:00Z"
  }
}
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
Per-asset history, oldest to newest. Each point surfaces the most operator-relevant channels (`vibration_magnitude`, `temperature_c`, `pseudo_pressure_pa`, `power_dissipated_w`) plus the prediction; the full 19 channels remain available in `raw_payload`.

**Query params:** `?limit=50` (1–200)

**Response 200:** `AssetTimelineResponse`.

---

### `GET /metrics/live`
In-memory replay validation metrics snapshot.

**Response 200:**
```json
{
  "total_replayed": 200,
  "total_correct": 198,
  "running_accuracy": 0.99,
  "per_class_ground_truth": { "bearing_wear": 36, "nominal": 36, "overheat": 36, "overload": 36, "pressure_fault": 28, "wheel_slip": 28 },
  "per_class_predicted":    { "bearing_wear": 36, "nominal": 36, "overheat": 36, "overload": 36, "pressure_fault": 28, "wheel_slip": 28 },
  "confusion_counts":       { "bearing_wear->bearing_wear": 36, "overheat->overheat": 36 },
  "per_model":              { "lightgbm": 200 },
  "last_updated": "2026-05-14T12:00:00Z"
}
```

---

### `GET /demo/models`
Model registry keys the demo selector can offer (enabled models only).

**Response 200:**
```json
{ "models": ["lightgbm", "lstm_ae", "random_forest", "xgboost", "cnn", "tabnet", "bilstm"] }
```

---

### `GET /demo/status`
State of the demo runner process plus the tail of its log.

**Response 200:**
```json
{
  "running": true,
  "mode": "dataset",
  "params": { "mode": "dataset", "model": "lightgbm", "split": "holdout", "count": 100, "delay": 0.5, "strict": false, "esp32_url": "http://dtx-esp32.local", "interval": 1.0 },
  "started_at": "2026-06-10T12:00:00+00:00",
  "returncode": null,
  "log_tail": ["[12/100] gt=overheat pred=overheat ok"]
}
```

`mode` and `params` are `null`/empty when no demo has been started; `returncode` is set once the subprocess exits.

---

### `POST /demo/start`
Start a demo run. Spawns `scripts/replay_dataset_demo.py` (`mode: "dataset"`) or `scripts/hw_demo_bridge.py` (`mode: "hardware"`) as a subprocess. Only one demo runs at a time.

**Request body:**

| Field | Type | Default | Applies to | Description |
|---|---|---|---|---|
| `mode` | `"dataset"` or `"hardware"` | — (required) | both | Demo type |
| `model` | `str` | `lightgbm` | both | Must be an enabled registry key (422 otherwise) |
| `split` | `"holdout"` / `"episode_holdout"` / `"temporal"` / `"all"` | `holdout` | dataset | Replay split — `holdout` is the leakage-safe per-episode temporal tail |
| `count` | `int` (0–100000) | `100` | both | Events to send (0 = unlimited for hardware mode) |
| `delay` | `float` (0–60) | `0.5` | dataset | Seconds between events |
| `strict` | `bool` | `false` | dataset | Strict replay mode |
| `esp32_url` | `str` | `http://dtx-esp32.local` | hardware | ESP32 node base URL |
| `interval` | `float` (0.05–60) | `1.0` | hardware | Polling interval in seconds |

**Response 202:**
```json
{ "started": true, "mode": "dataset", "pid": 12345 }
```

**Response 409** if a demo is already running.

---

### `POST /demo/stop`
Terminate the running demo subprocess.

**Response 200:**
```json
{ "stopped": true, "returncode": -15 }
```

Returns `{ "stopped": false, "detail": "No demo is running." }` when nothing is running.

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

## Fault classes returned in `anomaly.anomaly_type`

| Code | Label             | Default severity | Operator action |
|------|-------------------|------------------|-----------------|
| 0    | `nominal`         | info             | none |
| 1    | `bearing_wear`    | warning          | inspect bearings |
| 2    | `overheat`        | critical         | reduce load, verify cooling |
| 3    | `overload`        | warning          | check payload vs rating |
| 4    | `pressure_fault`  | warning          | inspect hydraulic / pneumatic line |
| 5    | `wheel_slip`      | warning          | check traction / surface |

---

## Internal Service Communication

### API → AI Pipeline (in-process)
The API lazy-imports `ai.pipeline.run_pipeline` inside the route handler. No network call — direct Python function call via shared `PYTHONPATH`. CPU-bound inference is offloaded to `asyncio.to_thread`.

### API → Isaac Sim Adapter (fire-and-forget)
After broadcasting, `_try_notify_sim(twin_update)` attempts to import and call the sim adapter. All failures are silently swallowed so a missing or down sim never blocks event processing.

### Dashboard polling cadence
| Trigger | Endpoint |
|---|---|
| On mount | `GET /alerts/` |
| Every 2 s (Dashboard) | `GET /metrics/live` |
| Every 4 s (Validation) | `GET /metrics/live` + `GET /alerts/?limit=100` |
| Every 3 s (Demo Control panel) | `GET /demo/status` |
| On Validation mount | `GET /demo/models` |
| Demo start/stop | `POST /demo/start` / `POST /demo/stop` |
| On event select | `GET /assets/{id}/timeline` + `GET /alerts/{id}/actions` |
| Operator action | `POST /alerts/{id}/actions` |
| Clear Logs | `DELETE /alerts/clear` |
