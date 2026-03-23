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

### `POST /events`

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

**Response 202** (`DashboardAlert`)
```json
{
  "alert_id": "...",
  "event": { ... },
  "anomaly": {
    "event_id": "...",
    "anomaly_score": 0.6250,
    "is_anomaly": true,
    "anomaly_type": "vibration",
    "severity": "warning",
    "detected_at": "..."
  },
  "explanation": {
    "event_id": "...",
    "summary": "Anomaly detected on asset 'conveyor-belt-01' ...",
    "contributing_features": { "vibration": 0.8, "temperature": 0.2 },
    "recommendation": "Schedule immediate maintenance inspection.",
    "generated_at": "..."
  },
  "created_at": "..."
}
```

---

### `GET /alerts?limit=50`

Returns the most recent processed events.

**Response 200**
```json
{
  "alerts": [ { "event_id": "...", "asset_id": "...", ... } ],
  "count": 12
}
```

---

### `WebSocket /ws/events`

Real-time push channel.  Connect to receive `DashboardAlert` JSON objects
as they are produced by `POST /events`.

**Message format**: same as the `DashboardAlert` schema above.

---

## Schemas

See `packages/shared/schemas.py` for the full Pydantic definitions.

| Schema | Purpose |
|--------|---------|
| `EventIn` | Inbound sensor event |
| `AnomalyResult` | AI anomaly detection output |
| `ExplanationResult` | XAI explanation |
| `TwinUpdate` | Digital-twin status change |
| `DashboardAlert` | Composed alert sent to dashboard |
| `EventLog` | Persisted SQLite row |
