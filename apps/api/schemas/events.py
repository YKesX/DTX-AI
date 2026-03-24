"""Pydantic schemas for the DTX-AI stub API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class EventFeatures(BaseModel):
    """Sensor feature vector attached to each incoming event."""

    proximity: Optional[float] = Field(None, description="Nearest obstacle distance (m)")
    speed: Optional[float] = Field(None, description="Asset speed (km/h)")
    direction: Optional[str] = Field(None, description="Movement direction label")
    zone: Optional[str] = Field(None, description="Current zone ID or name")
    vibration_rms: Optional[float] = Field(None, description="RMS vibration (g)")
    stop_duration: Optional[float] = Field(None, description="Stopped duration (s)")


class EventIn(BaseModel):
    """Incoming warehouse sensor event payload."""

    entity_id: str = Field(..., examples=["Forklift-01"])
    entity_type: str = Field(..., examples=["forklift"])
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    features: EventFeatures = Field(default_factory=EventFeatures)


class FeatureImpact(BaseModel):
    """Single feature contribution to the anomaly decision."""

    name: str
    value: str
    impact: float = Field(..., ge=0.0, le=1.0)


Severity = Literal["low", "medium", "high", "critical"]


class AnomalyResult(BaseModel):
    """AI pipeline result returned for every processed event."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    entity_id: str
    anomaly_score: float = Field(..., ge=0.0, le=1.0)
    anomaly_type: str
    severity: Severity
    top_features: list[FeatureImpact]
    explanation: str
    timestamp: datetime
