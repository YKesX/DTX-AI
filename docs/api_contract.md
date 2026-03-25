# API Contract — DTX-AI

Base URL: `http://localhost:8000`

---

## Endpoints

### `GET /health`

Returns API liveness status.

**Response 200**
```json
{ "status": "ok", "timestamp": "2025-01-01T12:00:00Z" }
```

---

### `POST /events/`

Ingest a warehouse sensor event and trigger the AI pipeline.

**Request body** (`EventIn`)
```json
{
  "asset_id": "conveyor-belt-01",
  "zone_id": "zone-A",
  "vibration": 14.7,
  "temperature": 82.3,
  "humidity": 41.0,
  "pressure": 1012.0,
  "metadata": {}
}
```

**Response 202** (`DashboardAlert` — nested)
```json
{
  "alert_id": "uuid",
  "event": {
    "event_id": "uuid",
    "asset_id": "conveyor-belt-01",
    "zone_id": "zone-A",
    "timestamp": "2026-01-01T12:00:00Z",
    "vibration": 14.7,
    "temperature": 82.3,
    "humidity": 41.0,
    "pressure": 1012.0,
    "metadata": {}
  },
  "anomaly": {
    "event_id": "uuid",
    "anomaly_score": 0.625,
    "is_anomaly": true,
    "anomaly_type": "vibration",
    "severity": "warning",
    "detected_at": "2026-01-01T12:00:00Z"
  },
  "explanation": {
    "event_id": "uuid",
    "summary": "Anomaly detected on asset 'conveyor-belt-01' ...",
    "contributing_features": { "vibration": 0.8, "temperature": 0.2 },
    "recommendation": "Schedule immediate maintenance inspection.",
    "generated_at": "2026-01-01T12:00:00Z"
  },
  "created_at": "2026-01-01T12:00:00Z"
}
```

**Severity values**: `info` | `warning` | `critical`

---

### `GET /alerts/?limit=50`

Returns the most recent processed events from the database, newest first.
This is an `EventLog` flat shape — it does not include `contributing_features`
since those are not persisted to the database in the current MVP.

**Response 200**
```json
{
  "alerts": [
    {
      "event_id": "uuid",
      "asset_id": "conveyor-belt-01",
      "zone_id": "zone-A",
      "timestamp": "2026-01-01T12:00:00Z",
      "anomaly_score": 0.625,
      "is_anomaly": 1,
      "anomaly_type": "vibration",
      "severity": "warning",
      "summary": "Anomaly detected on asset 'conveyor-belt-01'...",
      "raw_payload": "{...}"
    }
  ],
  "count": 1
}
```

> **Note:** `is_anomaly` is stored as an integer (`0`/`1`) in SQLite.
> The dashboard `normalizeAlert` helper coerces this to a boolean.
> `raw_payload` is a JSON string of the original `EventIn`.

---

### `WebSocket /ws/events`

Real-time push channel. Connect to receive `DashboardAlert` JSON objects
as they are produced by `POST /events/`.

**Message format**: same nested `DashboardAlert` schema as `POST /events/` response above.

---

## Dashboard payload normalisation

The frontend (`src/lib/normalizeAlert.js`) converts every backend payload
into a flat **view-model** before passing it to React components:

| View-model field | Source (DashboardAlert) | Source (EventLog row) |
|---|---|---|
| `id` | `alert_id` | `event_id` |
| `event_id` | `event.event_id` | `event_id` |
| `timestamp` | `event.timestamp` | `timestamp` |
| `entity_id` | `event.asset_id` | `asset_id` |
| `zone_id` | `event.zone_id` | `zone_id` |
| `anomaly_type` | `anomaly.anomaly_type` | `anomaly_type` |
| `anomaly_score` | `anomaly.anomaly_score` | `anomaly_score` |
| `severity` | `anomaly.severity` | `severity` |
| `is_anomaly` | `anomaly.is_anomaly` | `is_anomaly` (bool coerced) |
| `top_features` | derived from `explanation.contributing_features` dict | `[]` (not stored) |
| `explanation` | `summary + " " + recommendation` | `summary` |

---

## Severity mapping

| Backend value | Badge label (TR) | Badge colour |
|---|---|---|
| `info` | Bilgi | blue |
| `warning` | Uyarı | yellow |
| `critical` | Kritik | red |

Legacy mock values (`low`, `medium`, `high`) also work for backward compatibility.

---

## Schemas

See `packages/shared/schemas.py` for the full Pydantic definitions.

| Schema | Purpose |
|--------|---------|
| `EventIn` | Inbound sensor event (asset_id, zone_id, vibration, temperature, humidity, pressure) |
| `AnomalyResult` | AI anomaly detection output |
| `ExplanationResult` | XAI explanation (summary + contributing_features dict) |
| `TwinUpdate` | Digital-twin status change (Isaac Sim adapter) |
| `DashboardAlert` | Composed nested alert sent to dashboard |
| `EventLog` | Flat persisted SQLite row |

---

## Demo event seeder

```bash
# Quick mixed demo (10 events, 0.8 s apart)
python scripts/seed_demo_events.py

# Specific fault scenario
python scripts/seed_demo_events.py --scenario overheating --count 5

# All options
python scripts/seed_demo_events.py --help
```

Available scenarios: `normal`, `bearing_fault`, `overheating`, `combined`, `mixed`

---

## Plugging in real trained model artifacts

When training is complete:

1. Place `model_best.pkl` and `scaler.pkl` in `services/ai/` (or configure via env var).
2. Update `services/ai/ai/detector.py` — replace the rule-based stub with
   `joblib.load("model_best.pkl").predict(...)` using features preprocessed by
   `services/ai/preprocessing.py::preprocess_single(...)`.
3. Update `services/ai/ai/explainer.py` — replace stub attributions with
   `services/ai/xai_explainer.py::generate_xai_report(model, live_json)`.
4. The `contributing_features` dict in `ExplanationResult` maps directly to
   the SHAP values returned by `xai_explainer.py`.
5. No changes to `api/routes/events.py`, `DashboardAlert`, or the dashboard
   normalisation layer are needed.

---

## Future Isaac Sim integration

Synthetic events from Isaac Sim can enter the system through the same
`POST /events/` endpoint. The `apps/sim/sim/adapter.py` already has a
`notify(TwinUpdate)` hook that is called (fire-and-forget) by the API on
every anomaly. No changes to the dashboard or normalisation layer are needed.

