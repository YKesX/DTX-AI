"""
Canonical Pydantic schemas shared across all DTX-AI services.

Version: 1.0 (MVP)

Keep fields explicit and avoid Optional where a sensible default exists.
Add a new versioned module (e.g. schemas_v2.py) rather than breaking
these definitions when the contract evolves.
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
    """Coarse categories of detected anomaly."""

    VIBRATION = "vibration"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    PRESSURE = "pressure"
    COMBINED = "combined"
    UNKNOWN = "unknown"


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


# ---------------------------------------------------------------------------
# Core input schema
# ---------------------------------------------------------------------------


class EventIn(BaseModel):
    """
    Warehouse sensor event sent to POST /events.

    All numeric sensor readings are optional so that partial payloads
    (e.g. a temperature-only sensor) are still valid.
    """

    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    asset_id: str = Field(..., description="Identifier of the warehouse asset or machine")
    zone_id: str = Field(..., description="Warehouse zone where the asset is located")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event creation time (UTC)",
    )
    vibration: float | None = Field(None, ge=0, description="Vibration in mm/s²")
    temperature: float | None = Field(None, description="Temperature in °C")
    humidity: float | None = Field(None, ge=0, le=100, description="Relative humidity %")
    pressure: float | None = Field(None, ge=0, description="Pressure in hPa")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary extra fields")

    model_config = {"json_schema_extra": {
        "examples": [
            {
                "asset_id": "conveyor-belt-01",
                "zone_id": "zone-A",
                "vibration": 12.4,
                "temperature": 78.5,
                "humidity": 45.0,
                "pressure": 1013.2,
            }
        ]
    }}


# ---------------------------------------------------------------------------
# AI pipeline outputs
# ---------------------------------------------------------------------------


class AnomalyResult(BaseModel):
    """Anomaly detection output produced by services/ai."""

    event_id: UUID = Field(..., description="References the originating EventIn.event_id")
    anomaly_score: float = Field(..., ge=0.0, le=1.0, description="Normalised anomaly score (0 = normal, 1 = certain anomaly)")
    is_anomaly: bool = Field(..., description="True when score exceeds the configured threshold")
    anomaly_type: AnomalyType = Field(default=AnomalyType.UNKNOWN)
    severity: Severity = Field(default=Severity.INFO)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExplanationResult(BaseModel):
    """Human-readable XAI explanation for an anomaly."""

    event_id: UUID = Field(..., description="References the originating EventIn.event_id")
    summary: str = Field(..., description="One-sentence plain English explanation")
    contributing_features: dict[str, float] = Field(
        default_factory=dict,
        description="Feature → importance score (e.g. from SHAP)",
    )
    recommendation: str = Field(
        default="",
        description="Short suggested action for the operator",
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Digital-twin update
# ---------------------------------------------------------------------------


class TwinUpdate(BaseModel):
    """
    Payload sent to the Isaac Sim adapter when an anomaly is confirmed.
    The adapter is the only consumer; keep this schema thin.
    """

    event_id: UUID
    asset_id: str
    zone_id: str
    new_status: AssetStatus
    severity: Severity
    label: str = Field(default="", description="Short display label for the sim overlay")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Dashboard alert
# ---------------------------------------------------------------------------


class DashboardAlert(BaseModel):
    """
    Composed object broadcast over WebSocket /ws/events and stored for
    GET /alerts.  Combines the raw event, anomaly result, and explanation
    into a single message for the frontend.
    """

    alert_id: UUID = Field(default_factory=uuid4)
    event: EventIn
    anomaly: AnomalyResult
    explanation: ExplanationResult
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Persisted event log entry
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
