import { useMemo, useState } from 'react';
import Badge from '../ui/Badge';
import Card from '../ui/Card';

function ScoreBar({ score }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.8
      ? 'bg-red-500'
      : score >= 0.6
      ? 'bg-orange-500'
      : score >= 0.4
      ? 'bg-yellow-500'
      : 'bg-green-500';

  return (
    <div className="flex min-w-[80px] items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[rgba(64,82,101,0.65)]">
        <div
          className={`h-full rounded-full ${color} transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 text-right text-xs text-gray-300">{score.toFixed(2)}</span>
    </div>
  );
}

function formatOperatorState(value) {
  const normalized = String(value ?? 'new').replaceAll('_', ' ');
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function getRecommendationPreview(event) {
  const recommendation = event.recommendation ?? '';
  if (!recommendation) return '—';
  return recommendation.length > 48 ? `${recommendation.slice(0, 48)}...` : recommendation;
}

const VIEW_CONFIG = {
  operator: [
    { key: 'time', label: 'Time', render: (evt, time) => <span className="font-mono text-xs text-gray-400">{time}</span> },
    { key: 'asset', label: 'Asset', render: (evt) => <span className="font-medium text-white">{evt.entity_id || evt.entity}</span> },
    { key: 'issue', label: 'Issue', render: (evt) => <span className="text-gray-300">{evt.anomaly_type}</span> },
    { key: 'severity', label: 'Severity', render: (evt) => <Badge severity={evt.severity} /> },
    { key: 'score', label: 'Score', render: (evt) => <ScoreBar score={evt.anomaly_score} /> },
    { key: 'recommendation', label: 'Recommendation', render: (evt) => <span className="text-gray-300">{getRecommendationPreview(evt)}</span> },
    { key: 'operator', label: 'Operator Status', render: (evt) => <span className="text-gray-300">{formatOperatorState(evt.operator_status)}</span> },
    { key: 'detail', label: 'Detail', render: (evt, time, onSelectEvent) => (
      <button
        onClick={(e) => {
          e.stopPropagation();
          onSelectEvent(evt);
        }}
        className="text-xs text-blue-400 hover:text-blue-300 hover:underline"
      >
        Inspect →
      </button>
    ) },
  ],
  developer: [
    { key: 'time', label: 'Time', render: (evt, time) => <span className="font-mono text-xs text-gray-400">{time}</span> },
    { key: 'asset', label: 'Asset', render: (evt) => <span className="font-medium text-white">{evt.entity_id || evt.entity}</span> },
    { key: 'anomaly_type', label: 'Anomaly Type', render: (evt) => <span className="text-gray-300">{evt.anomaly_type}</span> },
    { key: 'source', label: 'Source', render: (evt) => <span className="text-gray-300">{evt.source ?? 'synthetic'}</span> },
    { key: 'model', label: 'Model', render: (evt) => <span className="text-gray-300">{evt.active_model ?? 'n/a'}</span> },
    { key: 'operator', label: 'Operator', render: (evt) => <span className="text-gray-300">{formatOperatorState(evt.operator_status)}</span> },
    { key: 'gt', label: 'GT', render: (evt) => <span className="text-gray-300">{evt.ground_truth_name ?? '—'}</span> },
    { key: 'pred', label: 'Pred', render: (evt) => <span className="text-gray-300">{evt.predicted_label ?? '—'}</span> },
    { key: 'correct', label: 'Correct', render: (evt) => <span className="text-gray-300">{evt.prediction_correct == null ? '—' : evt.prediction_correct ? '✓' : '✗'}</span> },
    { key: 'score', label: 'Score', render: (evt) => <ScoreBar score={evt.anomaly_score} /> },
    { key: 'severity', label: 'Severity', render: (evt) => <Badge severity={evt.severity} /> },
    { key: 'detail', label: 'Detail', render: (evt, time, onSelectEvent) => (
      <button
        onClick={(e) => {
          e.stopPropagation();
          onSelectEvent(evt);
        }}
        className="text-xs text-blue-400 hover:text-blue-300 hover:underline"
      >
        Inspect →
      </button>
    ) },
  ],
};

export default function EventTable({ events = [], onSelectEvent, selectedId, onClearLogs }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [severityFilter, setSeverityFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [operatorFilter, setOperatorFilter] = useState('all');
  const [viewMode, setViewMode] = useState('operator');

  const severityOptions = Array.from(
    new Set(events.map((event) => event.severity).filter(Boolean))
  );
  const sourceOptions = Array.from(
    new Set(events.map((event) => event.source ?? 'synthetic').filter(Boolean))
  );
  const operatorOptions = Array.from(
    new Set(events.map((event) => event.operator_status ?? 'new').filter(Boolean))
  );

  const normalizedSearch = searchTerm.trim().toLowerCase();
  const filteredEvents = events.filter((event) => {
    const matchesSearch =
      normalizedSearch.length === 0 ||
      [
        event.entity_id,
        event.entity,
        event.anomaly_type,
        event.predicted_label,
        event.ground_truth_name,
        event.active_model,
        event.recommendation,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalizedSearch));

    const matchesSeverity =
      severityFilter === 'all' || event.severity === severityFilter;
    const matchesSource =
      sourceFilter === 'all' || (event.source ?? 'synthetic') === sourceFilter;
    const matchesOperator =
      operatorFilter === 'all' || (event.operator_status ?? 'new') === operatorFilter;

    return matchesSearch && matchesSeverity && matchesSource && matchesOperator;
  });

  const columns = useMemo(() => VIEW_CONFIG[viewMode] ?? VIEW_CONFIG.operator, [viewMode]);

  const resetFilters = () => {
    setSearchTerm('');
    setSeverityFilter('all');
    setSourceFilter('all');
    setOperatorFilter('all');
  };

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-[rgba(113,136,158,0.18)] px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-100">
            Event Stream
          </h2>
          <p className="mt-1 text-xs text-gray-500">
            Showing {filteredEvents.length}/{events.length} records
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="rounded-xl border border-[rgba(92,117,142,0.28)] bg-[rgba(12,19,26,0.84)] p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
            <button
              type="button"
              onClick={() => setViewMode('operator')}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                viewMode === 'operator'
                  ? 'bg-[linear-gradient(90deg,rgba(140,241,222,0.18),rgba(140,184,255,0.12))] text-[rgba(225,255,248,0.96)]'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Operator View
            </button>
            <button
              type="button"
              onClick={() => setViewMode('developer')}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                viewMode === 'developer'
                  ? 'bg-[linear-gradient(90deg,rgba(140,241,222,0.18),rgba(140,184,255,0.12))] text-[rgba(225,255,248,0.96)]'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Developer View
            </button>
          </div>
          <button
            type="button"
            onClick={resetFilters}
            className="rounded-md border border-[rgba(92,117,142,0.28)] bg-[rgba(17,24,32,0.84)] px-3 py-1.5 text-xs text-gray-300 hover:bg-[rgba(37,50,64,0.85)]"
          >
            Reset Filters
          </button>
          <button
            type="button"
            onClick={onClearLogs}
            className="rounded-md border border-[rgba(255,93,93,0.22)] bg-[rgba(44,18,20,0.72)] px-3 py-1.5 text-xs text-red-100 hover:bg-[rgba(64,23,27,0.82)]"
          >
            Clear Logs
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 border-b border-[rgba(113,136,158,0.18)] px-5 py-4 md:grid-cols-2 xl:grid-cols-4">
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search asset, model, prediction, or recommendation"
          className="control-input w-full rounded-xl px-3 py-2 text-sm"
        />

        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="control-input w-full rounded-xl px-3 py-2 text-sm"
        >
          <option value="all">All severities</option>
          {severityOptions.map((severity) => (
            <option key={severity} value={severity}>
              {severity}
            </option>
          ))}
        </select>

        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="control-input w-full rounded-xl px-3 py-2 text-sm"
        >
          <option value="all">All sources</option>
          {sourceOptions.map((source) => (
            <option key={source} value={source}>
              {source}
            </option>
          ))}
        </select>

        <select
          value={operatorFilter}
          onChange={(e) => setOperatorFilter(e.target.value)}
          className="control-input w-full rounded-xl px-3 py-2 text-sm"
        >
          <option value="all">All operator states</option>
          {operatorOptions.map((status) => (
            <option key={status} value={status}>
              {formatOperatorState(status)}
            </option>
          ))}
        </select>
      </div>

      <div className="max-h-[620px] overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[rgba(113,136,158,0.18)] text-xs uppercase tracking-[0.18em] text-gray-500">
              {columns.map((column) => (
                <th key={column.key} className="sticky top-0 bg-[rgba(21,30,40,0.98)] px-5 py-3 text-left backdrop-blur-xl">
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredEvents.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-5 py-10 text-center text-sm text-gray-500"
                >
                  No events match the current filters.
                </td>
              </tr>
            ) : (
              filteredEvents.map((evt) => {
                const rowId = evt.id ?? evt.alert_id ?? evt.event_id;
                const isSelected = rowId === selectedId;
                const time = new Date(evt.timestamp).toLocaleTimeString('en-GB', {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                });

                return (
                  <tr
                    key={rowId}
                    onClick={() => onSelectEvent(evt)}
                    className={`cursor-pointer border-b border-[rgba(113,136,158,0.12)] transition-colors ${
                      isSelected
                        ? 'border-emerald-300/30 bg-[linear-gradient(90deg,rgba(140,241,222,0.12),rgba(140,184,255,0.12))]'
                        : 'hover:bg-[rgba(28,39,51,0.72)]'
                    }`}
                  >
                    {columns.map((column) => (
                      <td key={column.key} className="px-5 py-3 align-top">
                        {column.render(evt, time, onSelectEvent)}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
