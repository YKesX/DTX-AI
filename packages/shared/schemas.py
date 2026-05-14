"""
Canonical Pydantic schemas shared across all DTX-AI services.

Version: v2.0 — Isaac-Sim telemetry schema.

The previous 4-channel (vibration / temperature / humidity / pressure) schema
has been replaced with the 19-channel sensor set the models are now trained
on. See services/ai/preprocessing.py:FEATURES for the canonical ordering.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AnomalyType(str, Enum):
    """Fault classes emitted by the trained classifier.

    Values match the canonical strings in the training dataset's
    ``fault_label`` column and the ``class_mapping`` block in every
    services/ai/ai/models/*/metadata.json file.
    """

    UNKNOWN = "unknown"
    NOMINAL = "nominal"
    BEARING_WEAR = "bearing_wear"
    OVERHEAT = "overheat"
    OVERLOAD = "overload"
    PRESSURE_FAULT = "pressure_fault"
    WHEEL_SLIP = "wheel_slip"


class Severity(str, Enum):
    """Severity level used by alerts and twin updates."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AssetStatus(str, Enum):
    """Digital-twin asset operational status."""

    NORMAL = "normal"
    DEGRADED = "degraded"
    FAULT = "fault"
    OFFLINE = "offline"


class AlertActionType(str, Enum):
    """Operator-side incident actions."""

    ACKNOWLEDGE = "acknowledge"
    ASSIGN = "assign"
    ESCALATE = "escalate"
    RESOLVE = "resolve"


# ---------------------------------------------------------------------------
# Core input schema
# ---------------------------------------------------------------------------


class EventIn(BaseModel):
    """Asset telemetry frame sent to ``POST /events/``.

    Every sensor field is optional so partial frames remain valid; the runtime
    treats missing channels as zero.  Field names match the dataset CSV columns
    and the entries in services/ai/preprocessing.py:FEATURES exactly.
    """

    event_id: UUID = Field(default_factory=uuid4)
    asset_id: str = Field(..., description="Asset / forklift identifier")
    zone_id: str = Field(..., description="Warehouse zone identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event creation time (UTC)",
    )

    # IMU — linear acceleration (m/s²)
    imu_lin_acc_x: float | None = None
    imu_lin_acc_y: float | None = None
    imu_lin_acc_z: float | None = None
    # IMU — angular velocity (rad/s)
    imu_ang_vel_x: float | None = None
    imu_ang_vel_y: float | None = None
    imu_ang_vel_z: float | None = None
    # Combined vibration magnitude (m/s²)
    vibration_magnitude: float | None = None
    # Lift mechanism
    lift_joint_position: float | None = None
    lift_force_z: float | None = None
    lift_joint_velocity: float | None = None
    # Hydraulic / pneumatic proxy pressure (Pa)
    pseudo_pressure_pa: float | None = None
    # Drive joint
    drive_joint_velocity: float | None = None
    drive_joint_effort: float | None = None
    # Four wheel-roller angular velocities (rad/s)
    roller_fl_velocity: float | None = None
    roller_fr_velocity: float | None = None
    roller_bl_velocity: float | None = None
    roller_br_velocity: float | None = None
    # Bulk electrical
    power_dissipated_w: float | None = None
    # Thermal
    temperature_c: float | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"json_schema_extra": {
        "examples": [
            {
                "asset_id": "forklift-01",
                "zone_id": "zone-A",
                "imu_lin_acc_x": -9.77, "imu_lin_acc_y": 0.0, "imu_lin_acc_z": 0.86,
                "imu_ang_vel_x": 0.0, "imu_ang_vel_y": 0.0, "imu_ang_vel_z": 0.0,
                "vibration_magnitude": 9.81,
                "lift_joint_position": -0.15, "lift_force_z": 0.31,
                "lift_joint_velocity": 0.0,
                "pseudo_pressure_pa": 3.8,
                "drive_joint_velocity": -0.01, "drive_joint_effort": 3082.0,
                "roller_fl_velocity": 0.06, "roller_fr_velocity": -0.02,
                "roller_bl_velocity": 0.07, "roller_br_velocity": 0.01,
                "power_dissipated_w": 0.0,
                "temperature_c": 25.15,
            }
        ]
    }}


# ---------------------------------------------------------------------------
# AI pipeline outputs
# ---------------------------------------------------------------------------


class AnomalyResult(BaseModel):
    """Anomaly detection output produced by services/ai."""

    event_id: UUID = Field(..., description="References the originating EventIn.event_id")
    anomaly_score: float = Field(..., ge=0.0, le=1.0)
    is_anomaly: bool
    anomaly_type: AnomalyType = Field(default=AnomalyType.UNKNOWN)
    severity: Severity = Field(default=Severity.INFO)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExplanationResult(BaseModel):
    """Human-readable XAI explanation for an anomaly."""

    event_id: UUID
    summary: str
    contributing_features: dict[str, float] = Field(default_factory=dict)
    recommendation: str = Field(default="")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Digital-twin update
# ---------------------------------------------------------------------------


class TwinUpdate(BaseModel):
    """Payload sent to the Isaac Sim adapter when an anomaly is confirmed."""

    event_id: UUID
    asset_id: str
    zone_id: str
    new_status: AssetStatus
    severity: Severity
    label: str = Field(default="")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Dashboard alert
# ---------------------------------------------------------------------------


class DashboardAlert(BaseModel):
    """Composed object broadcast over WebSocket /ws/events and stored for /alerts."""

    alert_id: UUID = Field(default_factory=uuid4)
    event: EventIn
    anomaly: AnomalyResult
    explanation: ExplanationResult
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Persisted event log + operator workflow
# ---------------------------------------------------------------------------


class EventLog(BaseModel):
    """Row stored in the SQLite events table."""

    event_id: UUID
    asset_id: str
    zone_id: str
    timestamp: datetime
    anomaly_score: float
    is_anomaly: bool
    anomaly_type: AnomalyType
    severity: Severity
    summary: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class AlertActionIn(BaseModel):
    """Request payload for a new operator action."""

    action_type: AlertActionType
    note: str = Field(default="", max_length=500)
    assignee: str = Field(default="", max_length=120)


class AlertActionRecord(BaseModel):
    """Persisted operator action record."""

    id: int
    event_id: UUID
    action_type: AlertActionType
    note: str = Field(default="")
    assignee: str = Field(default="")
    created_at: datetime


class AlertOperatorState(BaseModel):
    """Derived operator workflow state for an alert."""

    operator_status: str = Field(default="new")
    assigned_to: str = Field(default="")
    last_action: AlertActionType | None = None
    last_action_at: datetime | None = None


class AssetTimelinePoint(BaseModel):
    """One point in an asset drilldown timeline."""

    event_id: UUID
    timestamp: datetime
    vibration_magnitude: float | None = None
    temperature_c: float | None = None
    pseudo_pressure_pa: float | None = None
    power_dissipated_w: float | None = None
    anomaly_score: float = 0.0
    severity: Severity = Severity.INFO
    predicted_label: str | None = None


class AssetTimelineResponse(BaseModel):
    """Response shape for asset drilldown history."""

    asset_id: str
    points: list[AssetTimelinePoint] = Field(default_factory=list)
