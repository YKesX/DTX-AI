import { MousePointerClick, ShieldAlert, Wrench, ClipboardList } from 'lucide-react';
import Badge from '../ui/Badge';
import Card from '../ui/Card';
import OperatorActionBar from './OperatorActionBar';

const SENSOR_CONFIG = [
  { key: 'vibration', label: 'Vibration', unit: 'mm/s²', threshold: 10 },
  { key: 'temperature', label: 'Temperature', unit: '°C', threshold: 75 },
  { key: 'humidity', label: 'Humidity', unit: '%', threshold: 85 },
  { key: 'pressure', label: 'Pressure', unit: 'hPa', threshold: 1050 },
];

function formatMetric(value, unit) {
  if (typeof value !== 'number') return '—';
  return `${value.toFixed(2)} ${unit}`;
}

function ReadingCard({ label, value, unit, threshold }) {
  const numeric = typeof value === 'number' ? value : null;
  const isAboveThreshold = numeric != null && numeric > threshold;

  return (
    <div className="control-panel-muted rounded-2xl p-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs uppercase tracking-wider text-dim">{label}</span>
        <span className={`text-[11px] ${isAboveThreshold ? 'text-red-800' : 'text-dim'}`}>
          Threshold: {threshold} {unit}
        </span>
      </div>
      <div className="mt-2 flex items-end justify-between gap-3">
        <span className={`text-lg font-semibold ${isAboveThreshold ? 'text-red-800' : 'text-ink'}`}>
          {formatMetric(value, unit)}
        </span>
        <span className={`text-xs ${isAboveThreshold ? 'text-red-800' : 'text-emerald-800'}`}>
          {numeric == null ? 'No data' : isAboveThreshold ? 'Above threshold' : 'Normal range'}
        </span>
      </div>
    </div>
  );
}

function FeatureBar({ feature }) {
  const pct = Math.round(feature.impact * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="font-medium text-muted">{feature.name}</span>
        <span className="text-dim">{feature.value}</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-paper">
          <div
            className="h-full rounded-full bg-paper-selected transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="w-8 text-right text-xs text-muted">{feature.impact.toFixed(2)}</span>
      </div>
    </div>
  );
}

function ActionHistory({ actions = [] }) {
  if (!actions.length) {
    return <p className="text-sm text-dim">No operator actions yet.</p>;
  }

  return (
    <div className="space-y-2">
      {actions.map((action) => (
        <div
          key={`${action.id}-${action.created_at}`}
          className="control-panel-muted rounded-xl px-3 py-2"
        >
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-medium capitalize text-ink">
              {action.action_type}
            </span>
            <span className="text-xs text-dim">
              {new Date(action.created_at).toLocaleString('tr-TR')}
            </span>
          </div>
          <div className="mt-1 space-y-1 text-xs text-muted">
            {action.action_type === 'assign' && action.assignee ? (
              <p>Assigned to: {action.assignee}</p>
            ) : null}
            {action.note ? <p>Note: {action.note}</p> : null}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function ExplanationPanel({
  event,
  actionHistory = [],
  actionState = null,
  actionLoading = false,
  onSubmitAction,
}) {
  if (!event) {
    return (
      <Card className="flex h-full flex-col items-center justify-center gap-3 p-10 text-center">
        <MousePointerClick className="h-10 w-10 text-ink" />
        <p className="text-sm text-dim">Select an event</p>
        <p className="text-xs text-dim">
          Click an event row in the table to view details, explanation, and operator actions.
        </p>
      </Card>
    );
  }

  const topFeatures = Array.isArray(event.top_features) ? event.top_features : [];
  const currentState = actionState ?? {
    operator_status: event.operator_status ?? 'new',
    assigned_to: event.assigned_to ?? '',
    last_action: event.last_action ?? null,
    last_action_at: event.last_action_at ?? null,
  };

  return (
    <Card className="flex flex-col gap-5 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="mb-1 text-xs uppercase tracking-wider text-dim">Asset</p>
          <p className="text-base font-semibold text-ink">{event.entity_id || event.entity}</p>
          <p className="mt-1 text-sm text-muted">
            {event.zone_id ? `${event.zone_id} zone` : 'Zone information unavailable'}
          </p>
        </div>
        <Badge severity={event.severity} />
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <div className="control-panel-muted rounded-2xl p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-ink">
            <ShieldAlert className="h-4 w-4 text-[var(--accent-cyan)]" />
            Event Summary
          </div>
          <div className="space-y-2 text-sm text-muted">
            <p>Anomaly Type: <span className="font-medium text-ink">{event.anomaly_type}</span></p>
            <p>Prediction: <span className="font-medium text-ink">{event.predicted_label ?? '—'}</span></p>
            <p>Score: <span className="font-medium text-ink">{(event.anomaly_score ?? 0).toFixed(2)}</span></p>
            <p>Source: <span className="font-medium text-ink">{event.source ?? 'synthetic'}</span></p>
            <p>Model: <span className="font-medium text-ink">{event.active_model ?? 'n/a'}</span></p>
            <p>Ground Truth: <span className="font-medium text-ink">{event.ground_truth_name ?? '—'}</span></p>
            <p>Replay Result: <span className="font-medium text-ink">
              {event.prediction_correct == null ? '—' : event.prediction_correct ? 'Correct' : 'Incorrect'}
            </span></p>
          </div>
        </div>

        <div className="control-panel-muted rounded-2xl p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-ink">
            <ClipboardList className="h-4 w-4 text-[var(--accent-blue)]" />
            Operator Status
          </div>
          <div className="space-y-2 text-sm text-muted">
            <p>Status: <span className="font-medium capitalize text-ink">{currentState.operator_status ?? 'new'}</span></p>
            <p>Assigned to: <span className="font-medium text-ink">{currentState.assigned_to || '—'}</span></p>
            <p>Last Action: <span className="font-medium text-ink">{currentState.last_action ?? '—'}</span></p>
            <p>Last Updated: <span className="font-medium text-ink">
              {currentState.last_action_at ? new Date(currentState.last_action_at).toLocaleString('tr-TR') : '—'}
            </span></p>
          </div>
        </div>
      </div>

      <div>
        <p className="mb-3 text-xs uppercase tracking-wider text-dim">Sensor Readings</p>
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {SENSOR_CONFIG.map((sensor) => (
            <ReadingCard
              key={sensor.key}
              label={sensor.label}
              value={event[sensor.key]}
              unit={sensor.unit}
              threshold={sensor.threshold}
            />
          ))}
        </div>
      </div>

      {topFeatures.length > 0 ? (
        <div>
          <p className="mb-3 text-xs uppercase tracking-wider text-dim">Key Features</p>
          <div className="space-y-3">
            {topFeatures.map((feature) => (
              <FeatureBar key={feature.name} feature={feature} />
            ))}
          </div>
        </div>
      ) : null}

      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs uppercase tracking-wider text-dim">Explanation</p>
          <span className="rounded-full border border-[var(--border)] px-3 py-1 text-xs text-muted">
            {{ t5: 'T5 explainer', lstm_template: 'LSTM-AE fallback', shap: 'SHAP',
              feature_importance: 'Feature importance', rules: 'Rule-based' }[event.explanation_source] || 'Source not recorded'}
          </span>
        </div>
        {event.explanation_source === 'lstm_template' && (
          <p className="text-xs text-muted">T5 could not generate an explanation for this event. Showing the LSTM-AE summary.</p>
        )}
        <div className="control-panel-muted rounded-2xl p-4">
          <p className="whitespace-pre-line text-sm leading-relaxed text-muted">
            {event.summary || event.explanation || '—'}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm font-medium text-ink">
          <Wrench className="h-4 w-4 text-[var(--accent-cyan)]" />
          Operator Actions
        </div>
        <div className="control-panel-muted rounded-2xl p-4">
          <p className="mb-3 text-sm text-muted">
            Recommendation: <span className="text-ink">{event.recommendation || 'No recommendation available.'}</span>
          </p>
          <p className="mb-3 text-xs text-dim">
            Assignee is only used when you click <span className="text-muted">Assign</span>.
          </p>
          <OperatorActionBar
            event={event}
            disabled={!event.event_id}
            loading={actionLoading}
            onSubmitAction={onSubmitAction}
          />
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs uppercase tracking-wider text-dim">Action History</p>
        <ActionHistory actions={actionHistory} />
      </div>
    </Card>
  );
}
