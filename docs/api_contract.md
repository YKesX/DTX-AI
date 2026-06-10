# API Contract — DTX-AI

Base URL: `http://localhost:8000`

The canonical Pydantic schemas live in
[`packages/shared/schemas.py`](../packages/shared/schemas.py); the dataset
columns and fault classes they reflect live in
[`services/ai/preprocessing.py`](../services/ai/preprocessing.py).

---

## Endpoints

### `GET /health`

Returns API liveness status.

**Response 200**
```json
{ "status": "ok", "timestamp": "2026-05-14T12:00:00Z" }
```

---

### `POST /events/`

Ingest a warehouse-asset telemetry frame and run the AI pipeline.

**Request body** (`EventIn`)

Every sensor channel is optional — partial frames are accepted; missing
channels are treated as zero by the runtime.

```json
{
  "asset_id": "forklift-01",
  "zone_id": "zone-A",
  "timestamp": "2026-05-14T12:00:00Z",

  "imu_lin_acc_x": -9.77, "imu_lin_acc_y": 0.00, "imu_lin_acc_z": 0.86,
  "imu_ang_vel_x":  0.00, "imu_ang_vel_y": 0.00, "imu_ang_vel_z": 0.00,

  "vibration_magnitude": 9.81,

  "lift_joint_position": -0.15,
  "lift_force_z": 0.31,
  "lift_joint_velocity": 0.00,

  "pseudo_pressure_pa": 3.82,

  "drive_joint_velocity": -0.01,
  "drive_joint_effort":   3082.0,

  "roller_fl_velocity": 0.06, "roller_fr_velocity": -0.02,
  "roller_bl_velocity": 0.07, "roller_br_velocity":  0.01,

  "power_dissipated_w": 0.0,
  "temperature_c": 25.15,

  "metadata": {
    "source": "isaac_sim",
    "active_model": "lightgbm"
  }
}
```

**Response 202** (`DashboardAlert`)

```json
{
  "alert_id": "uuid",
  "event": {
    "event_id": "uuid",
    "asset_id": "forklift-01",
    "zone_id": "zone-A",
    "timestamp": "2026-05-14T12:00:00Z",
    "temperature_c": 25.15,
    "...": "all 19 sensor channels echoed back",
    "metadata": {
      "predicted_label": "nominal",
      "predicted_anomaly_type": "nominal",
      "predicted_is_anomaly": false,
      "predicted_score": 0.997,
      "recommendation": "No action required — asset operating within nominal envelope.",
      "runtime_model": "lightgbm",
      "runtime_model_family": "lightgbm",
      "runtime_model_available": true
    }
  },
  "anomaly": {
    "event_id": "uuid",
    "anomaly_score": 0.997,
    "is_anomaly": false,
    "anomaly_type": "nominal",
    "severity": "info"
  },
  "explanation": {
    "event_id": "uuid",
    "summary": "Status: System is operating normally. No anomalies detected.",
    "contributing_features": { "temperature_c": 0.4, "power_dissipated_w": 0.3 },
    "recommendation": "No action required — asset operating within nominal envelope."
  }
}
```

The same `DashboardAlert` payload is also pushed over `WS /ws/events` to every
connected dashboard client.

### Sensor field reference

| Field                   | Unit         | Notes |
|-------------------------|--------------|-------|
| `imu_lin_acc_{x,y,z}`   | m/s²         | IMU linear acceleration |
| `imu_ang_vel_{x,y,z}`   | rad/s        | IMU angular velocity |
| `vibration_magnitude`   | m/s²         | Scalar L2 norm of vibration |
| `lift_joint_position`   | m or rad     | Lift joint generalized coordinate |
| `lift_force_z`          | N            | Vertical lift force |
| `lift_joint_velocity`   | m/s or rad/s | Lift joint generalized velocity |
| `pseudo_pressure_pa`    | Pa           | Hydraulic-line proxy pressure (negative under suction) |
| `drive_joint_velocity`  | rad/s        | Drive-joint angular velocity |
| `drive_joint_effort`    | N·m          | Drive-joint torque |
| `roller_{fl,fr,bl,br}_velocity` | rad/s | Four wheel-roller angular velocities |
| `power_dissipated_w`    | W            | Electrical power dissipation |
| `temperature_c`         | °C           | Motor / drive surface temperature |

### Fault classes returned in `anomaly.anomaly_type`

| Code | Label             | Default severity | Operator action |
|------|-------------------|------------------|-----------------|
| 0    | `nominal`         | info             | none |
| 1    | `bearing_wear`    | warning          | inspect bearings |
| 2    | `overheat`        | critical         | reduce load, verify cooling |
| 3    | `overload`        | warning          | check payload vs rating |
| 4    | `pressure_fault`  | warning          | inspect hydraulic/pneumatic line |
| 5    | `wheel_slip`      | warning          | check traction / surface |

---

### `GET /events`, `GET /alerts`, `WS /ws/events`, `GET /metrics/live`, `GET /assets/{id}/timeline`, `POST /alerts/{id}/actions`, `DELETE /alerts/clear`

Behaviour is unchanged from the previous contract; only the sensor field
names and fault-class vocabulary have changed. See the route handlers under
[`apps/api/api/routes/`](../apps/api/api/routes/) for the precise response
shapes.
