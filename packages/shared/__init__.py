"""
packages/shared — canonical event schemas for DTX-AI.

All inter-service contracts live here so that every app
imports from a single source of truth.
"""
from .schemas import (
    EventIn,
    AnomalyResult,
    ExplanationResult,
    TwinUpdate,
    DashboardAlert,
    EventLog,
)

__all__ = [
    "EventIn",
    "AnomalyResult",
    "ExplanationResult",
    "TwinUpdate",
    "DashboardAlert",
    "EventLog",
]
