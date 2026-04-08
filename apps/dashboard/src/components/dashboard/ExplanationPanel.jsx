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
        <span className="text-xs uppercase tracking-wider text-gray-500">{label}</span>
        <span className={`text-[11px] ${isAboveThreshold ? 'text-red-300' : 'text-gray-500'}`}>
          Threshold: {threshold} {unit}
        </span>
      </div>
      <div className="mt-2 flex items-end justify-between gap-3">
        <span className={`text-lg font-semibold ${isAboveThreshold ? 'text-red-200' : 'text-white'}`}>
          {formatMetric(value, unit)}
        </span>
        <span className={`text-xs ${isAboveThreshold ? 'text-red-400' : 'text-emerald-400'}`}>
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
        <span className="font-medium text-gray-300">{feature.name}</span>
        <span className="text-gray-500">{feature.value}</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-[rgba(62,79,96,0.58)]">
          <div
            className="h-full rounded-full bg-[linear-gradient(90deg,var(--accent-cyan),var(--accent-blue))] transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="w-8 text-right text-xs text-gray-400">{feature.impact.toFixed(2)}</span>
      </div>
    </div>
  );
}

function ActionHistory({ actions = [] }) {
  if (!actions.length) {
    return <p className="text-sm text-gray-500">No operator actions yet.</p>;
  }

  return (
    <div className="space-y-2">
      {actions.map((action) => (
        <div
          key={`${action.id}-${action.created_at}`}
          className="control-panel-muted rounded-xl px-3 py-2"
        >
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-medium capitalize text-gray-100">
              {action.action_type}
            </span>
            <span className="text-xs text-gray-500">
              {new Date(action.created_at).toLocaleString('tr-TR')}
            </span>
          </div>
          <div className="mt-1 space-y-1 text-xs text-gray-400">
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
        <MousePointerClick className="h-10 w-10 text-[rgba(140,241,222,0.72)]" />
        <p className="text-sm text-gray-500">Select an event</p>
        <p className="text-xs text-gray-600">
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
          <p className="mb-1 text-xs uppercase tracking-wider text-gray-500">Asset</p>
          <p className="text-base font-semibold text-white">{event.entity_id || event.entity}</p>
          <p className="mt-1 text-sm text-gray-400">
            {event.zone_id ? `${event.zone_id} zone` : 'Zone information unavailable'}
          </p>
        </div>
        <Badge severity={event.severity} />
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <div className="control-panel-muted rounded-2xl p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-200">
            <ShieldAlert className="h-4 w-4 text-[var(--accent-cyan)]" />
            Event Summary
          </div>
          <div className="space-y-2 text-sm text-gray-300">
            <p>Anomaly Type: <span className="font-medium text-white">{event.anomaly_type}</span></p>
            <p>Prediction: <span className="font-medium text-white">{event.predicted_label ?? '—'}</span></p>
            <p>Score: <span className="font-medium text-white">{(event.anomaly_score ?? 0).toFixed(2)}</span></p>
            <p>Source: <span className="font-medium text-white">{event.source ?? 'synthetic'}</span></p>
            <p>Model: <span className="font-medium text-white">{event.active_model ?? 'n/a'}</span></p>
            <p>Ground Truth: <span className="font-medium text-white">{event.ground_truth_name ?? '—'}</span></p>
            <p>Replay Result: <span className="font-medium text-white">
              {event.prediction_correct == null ? '—' : event.prediction_correct ? 'Correct' : 'Incorrect'}
            </span></p>
          </div>
        </div>

        <div className="control-panel-muted rounded-2xl p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-200">
            <ClipboardList className="h-4 w-4 text-[var(--accent-blue)]" />
            Operator Status
          </div>
          <div className="space-y-2 text-sm text-gray-300">
            <p>Status: <span className="font-medium capitalize text-white">{currentState.operator_status ?? 'new'}</span></p>
            <p>Assigned to: <span className="font-medium text-white">{currentState.assigned_to || '—'}</span></p>
            <p>Last Action: <span className="font-medium text-white">{currentState.last_action ?? '—'}</span></p>
            <p>Last Updated: <span className="font-medium text-white">
              {currentState.last_action_at ? new Date(currentState.last_action_at).toLocaleString('tr-TR') : '—'}
            </span></p>
          </div>
        </div>
      </div>

      <div>
        <p className="mb-3 text-xs uppercase tracking-wider text-gray-500">Sensor Readings</p>
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
          <p className="mb-3 text-xs uppercase tracking-wider text-gray-500">Key Features</p>
          <div className="space-y-3">
            {topFeatures.map((feature) => (
              <FeatureBar key={feature.name} feature={feature} />
            ))}
          </div>
        </div>
      ) : null}

      <div className="space-y-2">
        <p className="text-xs uppercase tracking-wider text-gray-500">Explanation</p>
        <div className="control-panel-muted rounded-2xl p-4">
          <p className="text-sm leading-relaxed text-gray-300">
            {event.summary || event.explanation || '—'}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-200">
          <Wrench className="h-4 w-4 text-[var(--accent-cyan)]" />
          Operator Actions
        </div>
        <div className="control-panel-muted rounded-2xl p-4">
          <p className="mb-3 text-sm text-gray-400">
            Recommendation: <span className="text-[rgba(215,255,246,0.96)]">{event.recommendation || 'No recommendation available.'}</span>
          </p>
          <p className="mb-3 text-xs text-gray-500">
            Assignee is only used when you click <span className="text-gray-300">Assign</span>.
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
        <p className="text-xs uppercase tracking-wider text-gray-500">Action History</p>
        <ActionHistory actions={actionHistory} />
      </div>
    </Card>
  );
}
