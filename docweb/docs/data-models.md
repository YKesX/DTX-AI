---
id: data-models
title: Data Models & Schemas
sidebar_position: 6
---

# Data Models & Schemas

All canonical schemas live in `packages/shared/schemas.py` as **Pydantic v2 `BaseModel`** subclasses. Installed as editable package `dtx-ai-shared`.

---

## Enumerations

```python
class AnomalyType(str, Enum):
    VIBRATION | TEMPERATURE | HUMIDITY | PRESSURE | COMBINED | UNKNOWN

class Severity(str, Enum):
    INFO | WARNING | CRITICAL

class AssetStatus(str, Enum):
    NORMAL | DEGRADED | FAULT | OFFLINE

class AlertActionType(str, Enum):
    ACKNOWLEDGE | ASSIGN | ESCALATE | RESOLVE
```

---

## EventIn

Core input schema. Received at `POST /events/`. All sensor readings are optional to allow partial telemetry.

| Field | Type | Required | Validation | Description |
|---|---|---|---|---|
| `event_id` | `UUID` | No (auto-gen) | uuid4 | Unique event identifier |
| `asset_id` | `str` | **Yes** | — | Warehouse asset identifier |
| `zone_id` | `str` | **Yes** | — | Warehouse zone identifier |
| `timestamp` | `datetime` | No (auto-gen) | UTC | Event creation time |
| `vibration` | `float \| None` | No | ≥ 0 | Vibration in mm/s² |
| `temperature` | `float \| None` | No | — | Temperature in °C |
| `humidity` | `float \| None` | No | 0..100 | Relative humidity % |
| `pressure` | `float \| None` | No | ≥ 0 | Pressure in hPa |
| `metadata` | `dict[str, Any]` | No (`{}`) | — | Arbitrary replay/source metadata |

---

## AnomalyResult

AI detection output.

| Field | Type | Validation | Description |
|---|---|---|---|
| `event_id` | `UUID` | — | References `EventIn.event_id` |
| `anomaly_score` | `float` | `0.0..1.0` | Model confidence — ≥ 0.5 triggers `is_anomaly=True` |
| `is_anomaly` | `bool` | — | True when score exceeds threshold |
| `anomaly_type` | `AnomalyType` | — | Fault category |
| `severity` | `Severity` | — | INFO / WARNING / CRITICAL |
| `detected_at` | `datetime` | UTC | Detection timestamp |

---

## ExplanationResult

XAI output from SHAP pipeline.

| Field | Type | Description |
|---|---|---|
| `event_id` | `UUID` | References originating event |
| `summary` | `str` | One-sentence plain-English explanation |
| `contributing_features` | `dict[str, float]` | Feature name → SHAP attribution score |
| `recommendation` | `str` | Short operator action recommendation |
| `generated_at` | `datetime` | UTC generation timestamp |

:::caution Known Limitation
`contributing_features` are **not persisted** to SQLite. Historical `GET /alerts/` responses return `top_features: []`. SHAP values are only available in real-time via WebSocket and `POST /events/` response.
:::

---

## DashboardAlert

Composed broadcast envelope — sent over WebSocket and returned by `POST /events/`.

```json
{
  "alert_id": "uuid4",
  "event": { /* EventIn */ },
  "anomaly": { /* AnomalyResult */ },
  "explanation": { /* ExplanationResult */ },
  "created_at": "2026-04-10T12:00:00Z"
}
```

---

## TwinUpdate

Sent from API to Isaac Sim adapter after each anomaly.

| Field | Type | Description |
|---|---|---|
| `event_id` | `UUID` | References event |
| `asset_id` | `str` | Asset to update in USD scene |
| `zone_id` | `str` | Zone of the asset |
| `new_status` | `AssetStatus` | NORMAL / DEGRADED / FAULT / OFFLINE |
| `severity` | `Severity` | Severity level |
| `label` | `str` | Short display label for sim overlay |
| `timestamp` | `datetime` | Update time |

---

## AlertActionIn

Operator workflow request body.

| Field | Type | Validation | Description |
|---|---|---|---|
| `action_type` | `AlertActionType` | — | acknowledge / assign / escalate / resolve |
| `note` | `str` | max 500 chars | Operator note |
| `assignee` | `str` | max 120 chars | Assignee name (used for `assign` only) |

---

## EventLog

Flat denormalized row persisted to the SQLite `events` table.

| Field | Type | Description |
|---|---|---|
| `event_id` | `UUID` | Primary key |
| `asset_id` | `str` | Asset identifier |
| `zone_id` | `str` | Zone identifier |
| `timestamp` | `datetime` | Event time |
| `anomaly_score` | `float` | Score from AI pipeline |
| `is_anomaly` | `bool` | Anomaly flag (stored as int 0/1) |
| `anomaly_type` | `AnomalyType` | Fault category |
| `severity` | `Severity` | INFO / WARNING / CRITICAL |
| `summary` | `str` | Explanation summary text |
| `raw_payload` | `dict[str, Any]` | Full `EventIn` as JSON string |
