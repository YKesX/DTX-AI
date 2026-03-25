/**
 * normalizeAlert — converts any backend alert shape into a flat view-model
 * that all dashboard components consume.
 *
 * Handled input shapes
 * ────────────────────
 * A. DashboardAlert (nested) — emitted by WS /ws/events and POST /events/:
 *    { alert_id, event: {event_id, asset_id, zone_id, timestamp, ...},
 *      anomaly: {anomaly_score, anomaly_type, severity, is_anomaly, ...},
 *      explanation: {summary, contributing_features, recommendation, ...},
 *      created_at }
 *
 * B. EventLog row (flat) — returned by GET /alerts/:
 *    { event_id, asset_id, zone_id, timestamp,
 *      anomaly_score, is_anomaly, anomaly_type, severity, summary }
 *
 * C. Legacy mock shape (flat) — from src/lib/mockData.js:
 *    { id, entity, anomaly_type, anomaly_score, severity,
 *      top_features: [{name, value, impact}], explanation: string }
 *
 * Output view-model (all shapes produce the same fields):
 * {
 *   id            — primary key used for React keys and selection
 *   alert_id      — original alert_id (null for EventLog rows / mock)
 *   event_id      — original event_id string
 *   timestamp     — ISO string
 *   entity_id     — asset / entity identifier
 *   entity        — alias for entity_id (for backwards-compat)
 *   zone_id
 *   anomaly_type  — string label
 *   anomaly_score — number [0..1]
 *   severity      — one of: info | warning | critical | low | medium | high
 *   is_anomaly    — boolean
 *   top_features  — [{name, value, impact}] sorted desc by impact
 *   explanation   — plain-text explanation string
 *   summary       — summary field alone
 *   recommendation
 *   _raw          — original unserialized object (for debugging)
 * }
 */

/**
 * Convert a contributing_features dict into a sorted top_features array.
 *   { "vibration": 0.8, "temperature": 0.2 }
 *   → [{ name: "vibration", value: "0.8000", impact: 0.8 }, ...]
 */
function featuresFromDict(dict = {}) {
  return Object.entries(dict)
    .map(([name, impact]) => ({
      name,
      value: typeof impact === 'number' ? impact.toFixed(4) : String(impact),
      impact: typeof impact === 'number' ? impact : 0,
    }))
    .sort((a, b) => b.impact - a.impact)
    .slice(0, 5);
}

/**
 * Normalise a single raw alert payload from any known backend shape.
 * Returns null if the input is falsy.
 */
export function normalizeAlert(raw) {
  if (!raw) return null;

  // ── Shape A: DashboardAlert (nested) ──────────────────────────────────────
  if (raw.alert_id !== undefined || (raw.event && raw.anomaly && raw.explanation)) {
    const event = raw.event ?? {};
    const anomaly = raw.anomaly ?? {};
    const explanation = raw.explanation ?? {};

    const entityId = event.asset_id ?? '';
    return {
      id: raw.alert_id ?? event.event_id ?? raw.created_at,
      alert_id: raw.alert_id ?? null,
      event_id: String(event.event_id ?? ''),
      timestamp: event.timestamp ?? raw.created_at ?? new Date().toISOString(),
      entity_id: entityId,
      entity: entityId,
      zone_id: event.zone_id ?? '',
      anomaly_type: anomaly.anomaly_type ?? 'unknown',
      anomaly_score:
        typeof anomaly.anomaly_score === 'number' ? anomaly.anomaly_score : 0,
      severity: anomaly.severity ?? 'info',
      is_anomaly: Boolean(anomaly.is_anomaly),
      top_features: featuresFromDict(explanation.contributing_features),
      explanation: [explanation.summary, explanation.recommendation]
        .filter(Boolean)
        .join(' '),
      summary: explanation.summary ?? '',
      recommendation: explanation.recommendation ?? '',
      _raw: raw,
    };
  }

  // ── Shape B: EventLog row (flat) or legacy mock (flat) ────────────────────
  const entityId =
    raw.asset_id ?? raw.entity_id ?? raw.entity ?? '';

  return {
    id: raw.event_id ?? raw.alert_id ?? raw.id ?? String(Date.now()),
    alert_id: raw.alert_id ?? null,
    event_id: String(raw.event_id ?? raw.id ?? ''),
    timestamp: raw.timestamp ?? new Date().toISOString(),
    entity_id: entityId,
    entity: entityId,
    zone_id: raw.zone_id ?? '',
    anomaly_type: raw.anomaly_type ?? 'unknown',
    anomaly_score:
      typeof raw.anomaly_score === 'number' ? raw.anomaly_score : 0,
    severity: raw.severity ?? 'info',
    is_anomaly: Boolean(raw.is_anomaly),
    // Preserve existing top_features array if present (e.g. mock data),
    // otherwise leave empty (EventLog rows don't store feature detail).
    top_features: Array.isArray(raw.top_features) ? raw.top_features : [],
    explanation: raw.summary ?? raw.explanation ?? '',
    summary: raw.summary ?? raw.explanation ?? '',
    recommendation: raw.recommendation ?? '',
    _raw: raw,
  };
}

/**
 * Normalise an array of raw alerts, filtering out nulls.
 */
export function normalizeAlerts(rawArray) {
  if (!Array.isArray(rawArray)) return [];
  return rawArray.map(normalizeAlert).filter(Boolean);
}
