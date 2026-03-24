"""
Stub AI service for DTX-AI.

process_event() mimics the real ML pipeline:
  - assigns a random anomaly score
  - derives severity and anomaly type from input features
  - builds a top-3 feature impact list
  - returns a canned Turkish explanation per anomaly type
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from schemas.events import AnomalyResult, EventIn, FeatureImpact

# ── Constants ─────────────────────────────────────────────────────────────────

_ANOMALY_TYPES = [
    "Forklift Yakını Riski",
    "Yasak Bölge Girişi",
    "Beklenmeyen Duruş",
    "Vibrasyon Artışı",
]

_EXPLANATIONS: dict[str, str] = {
    "Forklift Yakını Riski": (
        "Forklift, bir insana veya engele güvenlik mesafesinin altında yaklaşmıştır. "
        "Tespit edilen mesafe kritik eşiğin altındadır ve çarpışma riski oluşturmaktadır. "
        "Operatörün frene basması veya hızını düşürmesi gerekmektedir."
    ),
    "Yasak Bölge Girişi": (
        "Bir varlık, depodaki kısıtlı veya yetkisiz erişim bölgesine girmiştir. "
        "Bu bölge aktif makine operasyonlarıyla çakışmakta olup ciddi tehlike oluşturmaktadır. "
        "Bölgeye erişimin engellenmesi ve ilgili personelin uyarılması önerilir."
    ),
    "Beklenmeyen Duruş": (
        "Varlık, aktif görev rotasında beklenmedik bir süre hareketsiz kalmıştır. "
        "Bu durum mekanik arıza, engel tespiti veya operatör müdahalesine işaret edebilir. "
        "Saha kontrolü yapılarak nedeni belirlenmesi önerilir."
    ),
    "Vibrasyon Artışı": (
        "Sensör, normalin üzerinde titreşim değerleri kaydetmektedir. "
        "Yüksek titreşim, mekanik aşınma, gevşek bağlantılar veya aşırı yük belirtisi olabilir. "
        "Bakım ekibinin cihazı incelemesi gerekmektedir."
    ),
}

# Feature display names mapped to EventFeatures field names
_FEATURE_META: list[tuple[str, str]] = [
    ("Yakınlık", "proximity"),
    ("Hız", "speed"),
    ("Yön", "direction"),
    ("Bölge İhlali", "zone"),
    ("RMS Vibrasyon", "vibration_rms"),
    ("Duruş Süresi", "stop_duration"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _pick_anomaly_type(features) -> str:
    """Choose the most plausible anomaly type based on feature hints."""
    if features.zone and str(features.zone).lower() not in ("", "none", "normal"):
        return "Yasak Bölge Girişi"
    if features.vibration_rms is not None and features.vibration_rms > 2.0:
        return "Vibrasyon Artışı"
    if features.stop_duration is not None and features.stop_duration > 15:
        return "Beklenmeyen Duruş"
    if features.proximity is not None and features.proximity < 2.0:
        return "Forklift Yakını Riski"
    # Fall back to weighted random so every type can appear in mock data
    return random.choice(_ANOMALY_TYPES)


def _severity_from_score(score: float) -> str:
    if score < 0.4:
        return "low"
    if score < 0.6:
        return "medium"
    if score < 0.8:
        return "high"
    return "critical"


def _fmt_value(field: str, raw) -> str:
    """Format a raw feature value into a human-readable string."""
    if raw is None:
        return "N/A"
    units = {
        "proximity": "m",
        "speed": "km/h",
        "vibration_rms": "g",
        "stop_duration": "sn",
    }
    unit = units.get(field, "")
    if isinstance(raw, float):
        return f"{raw:.1f} {unit}".strip()
    return str(raw)


def _build_top_features(features, anomaly_type: str) -> list[FeatureImpact]:
    """
    Assign mock impact scores to each feature and return the top 3.
    Features relevant to the detected anomaly type get a higher base impact.
    """
    relevance: dict[str, float] = {
        "Forklift Yakını Riski":  {"proximity": 0.9, "speed": 0.7, "direction": 0.5},
        "Yasak Bölge Girişi":    {"zone": 0.9, "proximity": 0.6, "direction": 0.5},
        "Beklenmeyen Duruş":     {"stop_duration": 0.9, "speed": 0.7, "direction": 0.4},
        "Vibrasyon Artışı":      {"vibration_rms": 0.95, "speed": 0.3, "stop_duration": 0.2},
    }.get(anomaly_type, {})

    scored: list[FeatureImpact] = []
    for display_name, field in _FEATURE_META:
        raw = getattr(features, field)
        base = relevance.get(field, 0.0)
        # Add noise so results look realistic
        impact = min(1.0, max(0.0, base + random.uniform(-0.1, 0.1)))
        scored.append(
            FeatureImpact(
                name=display_name,
                value=_fmt_value(field, raw),
                impact=round(impact, 2),
            )
        )

    scored.sort(key=lambda f: f.impact, reverse=True)
    return scored[:3]


# ── Public API ────────────────────────────────────────────────────────────────


def process_event(event: EventIn) -> AnomalyResult:
    """
    Stub AI pipeline: deterministically derive an AnomalyResult from an EventIn.
    Scores are random (0.30 – 0.95) to simulate a live model.
    """
    score = round(random.uniform(0.30, 0.95), 2)
    anomaly_type = _pick_anomaly_type(event.features)
    severity = _severity_from_score(score)
    top_features = _build_top_features(event.features, anomaly_type)
    explanation = _EXPLANATIONS[anomaly_type]

    return AnomalyResult(
        event_id=str(uuid.uuid4()),
        entity_id=event.entity_id,
        anomaly_score=score,
        anomaly_type=anomaly_type,
        severity=severity,
        top_features=top_features,
        explanation=explanation,
        timestamp=event.timestamp,
    )
