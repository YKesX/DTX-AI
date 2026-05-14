---
id: data-models
title: Data Models & Schemas
sidebar_position: 6
---

# Data Models & Schemas

All canonical schemas live in [`packages/shared/schemas.py`](https://github.com/YKesX/DTX-AI/blob/main/packages/shared/schemas.py) as **Pydantic v2 `BaseModel`** subclasses. Installed as the editable package `dtx-ai-shared`.

The 19-channel sensor set is the single source of truth for what models see — both the dataset CSV columns and `services/ai/preprocessing.py:FEATURES` mirror these field names exactly.

---

## Enumerations

```python
class AnomalyType(str, Enum):
    # Faults the trained classifier emits
    UNKNOWN | NOMINAL | BEARING_WEAR | OVERHEAT |
    OVERLOAD | PRESSURE_FAULT | WHEEL_SLIP

class Severity(str, Enum):
    INFO | WARNING | CRITICAL

class AssetStatus(str, Enum):
    NORMAL | DEGRADED | FAULT | OFFLINE

class AlertActionType(str, Enum):
    ACKNOWLEDGE | ASSIGN | ESCALATE | RESOLVE
```

---

## EventIn

Core input schema received at `POST /events/`. Every sensor channel is optional — partial frames are accepted; missing channels are treated as zero by the runtime.

### Identity & metadata

| Field | Type | Required | Description |
|---|---|---|---|
| `event_id` | `UUID` | No (auto-gen) | Unique event identifier |
| `asset_id` | `str` | **Yes** | Asset / forklift identifier |
| `zone_id` | `str` | **Yes** | Warehouse zone identifier |
| `timestamp` | `datetime` | No (auto-gen) | UTC event time |
| `metadata` | `dict[str, Any]` | No (`{}`) | Arbitrary replay/source metadata |

### Sensor channels (all optional, all `float \| None`)

| Field | Unit | Channel source |
|---|---|---|
| `imu_lin_acc_x`, `_y`, `_z` | m/s² | IMU linear acceleration |
| `imu_ang_vel_x`, `_y`, `_z` | rad/s | IMU angular velocity |
| `vibration_magnitude` | m/s² | Scalar L2 of the IMU linear-accel vector |
| `lift_joint_position` | m or rad | Lift-joint generalized coordinate |
| `lift_force_z` | N | Vertical lift force |
| `lift_joint_velocity` | m/s or rad/s | Lift-joint generalized velocity |
| `pseudo_pressure_pa` | Pa | Hydraulic-line proxy (negative under suction) |
| `drive_joint_velocity` | rad/s | Drive-joint angular velocity |
| `drive_joint_effort` | N·m | Drive-joint torque |
| `roller_fl_velocity`, `_fr_`, `_bl_`, `_br_` | rad/s | Four wheel-roller angular velocities |
| `power_dissipated_w` | W | Electrical power dissipation |
| `temperature_c` | °C | Motor / drive surface temperature |

---

## AnomalyResult

AI detection output.

| Field | Type | Validation | Description |
|---|---|---|---|
| `event_id` | `UUID` | — | References `EventIn.event_id` |
| `anomaly_score` | `float` | `0.0..1.0` | Model confidence — for trees this is `max(predict_proba)` over the non-nominal classes; for the LSTM-AE this is the softmax probability of the argmax class |
| `is_anomaly` | `bool` | — | True when the predicted class is not `nominal` and score ≥ threshold |
| `anomaly_type` | `AnomalyType` | — | Predicted fault class |
| `severity` | `Severity` | — | INFO (nominal) / WARNING / CRITICAL |
| `detected_at` | `datetime` | UTC | Detection timestamp |

---

## ExplanationResult

XAI output from the SHAP pipeline (tree models) or fallback rule-based attribution.

| Field | Type | Description |
|---|---|---|
| `event_id` | `UUID` | References originating event |
| `summary` | `str` | One-sentence plain-English explanation |
| `contributing_features` | `dict[str, float]` | Feature name → SHAP attribution score (top-3 for tree models, all above-threshold channels for the fallback) |
| `recommendation` | `str` | Short operator action recommendation |
| `generated_at` | `datetime` | UTC generation timestamp |

:::caution Known Limitation
`contributing_features` are **not persisted** to SQLite. Historical `GET /alerts/` responses do not include them. SHAP values are only available in real time via the WebSocket push and the `POST /events/` response.
:::

---

## DashboardAlert

Composed broadcast envelope — sent over WebSocket and returned by `POST /events/`.

```json
{
  "alert_id": "uuid4",
  "event":       { /* EventIn */ },
  "anomaly":     { /* AnomalyResult */ },
  "explanation": { /* ExplanationResult */ },
  "created_at":  "2026-05-14T12:00:00Z"
}
```

---

## TwinUpdate

Sent from the API to the Isaac Sim adapter after each anomaly.

| Field | Type | Description |
|---|---|---|
| `event_id` | `UUID` | References event |
| `asset_id` | `str` | Asset to update in the USD scene |
| `zone_id` | `str` | Zone of the asset |
| `new_status` | `AssetStatus` | NORMAL / DEGRADED / FAULT / OFFLINE |
| `severity` | `Severity` | Severity level |
| `label` | `str` | Short display label for sim overlay (e.g. `bearing_wear / score=0.97`) |
| `timestamp` | `datetime` | Update time |

---

## AlertActionIn

Operator workflow request body.

| Field | Type | Validation | Description |
|---|---|---|---|
| `action_type` | `AlertActionType` | — | acknowledge / assign / escalate / resolve |
| `note` | `str` | max 500 chars | Operator note |
| `assignee` | `str` | max 120 chars | Assignee name; persisted only for the `assign` action |

---

## AlertOperatorState

Derived workflow snapshot returned by `GET /alerts/{event_id}/actions` and merged into `GET /alerts/` rows.

| Field | Type | Description |
|---|---|---|
| `operator_status` | `str` | One of `new`, `acknowledged`, `assigned`, `escalated`, `resolved` |
| `assigned_to` | `str` | Most recent non-empty assignee observed in the action history |
| `last_action` | `AlertActionType \| null` | Latest operator action for the alert |
| `last_action_at` | `datetime \| null` | Timestamp of the latest operator action |

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
| `anomaly_type` | `AnomalyType` | Predicted fault class |
| `severity` | `Severity` | INFO / WARNING / CRITICAL |
| `summary` | `str` | Explanation summary text |
| `raw_payload` | `dict[str, Any]` | Full `EventIn` as JSON — all 19 channels recoverable |

`GET /alerts/` enriches these rows with the derived `AlertOperatorState` fields so the dashboard can render current ownership and workflow status without an extra join client-side.

---

## AssetTimelineResponse

Response returned by `GET /assets/{asset_id}/timeline`.

| Field | Type | Description |
|---|---|---|
| `asset_id` | `str` | Asset identifier requested in the route |
| `points` | `AssetTimelinePoint[]` | Ordered oldest → newest for chart rendering |
