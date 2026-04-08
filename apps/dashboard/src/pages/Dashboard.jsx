import { useCallback, useEffect, useMemo, useState } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import StatusCards from '../components/dashboard/StatusCards';
import EventTable from '../components/dashboard/EventTable';
import ExplanationPanel from '../components/dashboard/ExplanationPanel';
import TrendChart from '../components/dashboard/TrendChart';
import AssetDrilldownChart from '../components/dashboard/AssetDrilldownChart';
import { normalizeAlerts } from '../lib/normalizeAlert';

const WS_URL =
  import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws/events';
const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

function deriveStatus(events) {
  if (!events.length) {
    return {
      activeAlerts: 0,
      connectedSensors: 0,
      lastDataTime: '—',
      systemStatus: 'Online',
    };
  }

  const activeAlerts = events.filter(
    (event) => ['warning', 'critical', 'high'].includes(event.severity)
  ).length;

  const connectedSensors = new Set(
    events.map((event) => event.entity_id || event.entity).filter(Boolean)
  ).size;

  const latest = events.reduce((a, b) =>
    new Date(a.timestamp) > new Date(b.timestamp) ? a : b
  );
  const lastDataTime = new Date(latest.timestamp).toLocaleTimeString('tr-TR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  const hasCritical = events.some((event) => event.severity === 'critical');
  const hasWarning = events.some(
    (event) => event.severity === 'warning' || event.severity === 'high'
  );
  const systemStatus = hasCritical ? 'Critical' : hasWarning ? 'Warning' : 'Online';

  return { activeAlerts, connectedSensors, lastDataTime, systemStatus };
}

function deriveTrend(events) {
  return [...events]
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    .slice(-20)
    .map((event) => ({
      time: new Date(event.timestamp).toLocaleTimeString('tr-TR', {
        hour: '2-digit',
        minute: '2-digit',
      }),
      score: event.anomaly_score ?? 0,
    }));
}

export default function Dashboard() {
  const { events, setEvents } = useWebSocket(WS_URL);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [liveMetrics, setLiveMetrics] = useState(null);
  const [assetTimeline, setAssetTimeline] = useState([]);
  const [timelineMetric, setTimelineMetric] = useState('vibration');
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [actionHistory, setActionHistory] = useState([]);
  const [actionState, setActionState] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  const mergeOperatorState = useCallback((eventId, state) => {
    if (!eventId || !state) return;

    setEvents((prev) =>
      prev.map((event) =>
        event.event_id === eventId
          ? {
              ...event,
              operator_status: state.operator_status ?? event.operator_status,
              assigned_to: state.assigned_to ?? event.assigned_to,
              last_action: state.last_action ?? event.last_action,
              last_action_at: state.last_action_at ?? event.last_action_at,
            }
          : event
      )
    );

    setSelectedEvent((prev) =>
      prev && prev.event_id === eventId
        ? {
            ...prev,
            operator_status: state.operator_status ?? prev.operator_status,
            assigned_to: state.assigned_to ?? prev.assigned_to,
            last_action: state.last_action ?? prev.last_action,
            last_action_at: state.last_action_at ?? prev.last_action_at,
          }
        : prev
    );
  }, [setEvents]);

  const handleClearLogs = async () => {
    try {
      const res = await fetch(`${API_BASE}/alerts/clear`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch {
      // keep UI usable even if API clear fails
    } finally {
      setEvents([]);
      setSelectedEvent(null);
      setAssetTimeline([]);
      setActionHistory([]);
      setActionState(null);
      setLiveMetrics((prev) => ({
        ...(prev ?? {}),
        total_replayed: 0,
        total_correct: 0,
        running_accuracy: 0,
      }));
    }
  };

  useEffect(() => {
    fetch(`${API_BASE}/alerts/`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        const rows = Array.isArray(data) ? data : (data.alerts ?? []);
        if (rows.length === 0) return;
        const normalized = normalizeAlerts(rows);
        setEvents((prev) => {
          const existingKeys = new Set(
            prev.map((event) => (event.event_id != null ? event.event_id : event.id))
          );
          const fresh = normalized.filter(
            (event) => !existingKeys.has(event.event_id != null ? event.event_id : event.id)
          );
          return [...prev, ...fresh];
        });
      })
      .catch(() => {
        // API not reachable — fall back to whatever WS provides
      });
  }, [setEvents]);

  useEffect(() => {
    let cancelled = false;
    const loadMetrics = () => {
      fetch(`${API_BASE}/metrics/live`)
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then((data) => {
          if (!cancelled) setLiveMetrics(data);
        })
        .catch(() => {
          if (!cancelled) setLiveMetrics(null);
        });
    };

    loadMetrics();
    const timer = setInterval(loadMetrics, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!selectedEvent?.event_id) {
      setAssetTimeline([]);
      setActionHistory([]);
      setActionState(null);
      return;
    }

    let cancelled = false;
    const assetId = selectedEvent.entity_id || selectedEvent.entity;
    setTimelineLoading(true);

    Promise.all([
      fetch(`${API_BASE}/assets/${assetId}/timeline?limit=30`).then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      }),
      fetch(`${API_BASE}/alerts/${selectedEvent.event_id}/actions`).then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      }),
    ])
      .then(([timelineData, actionData]) => {
        if (cancelled) return;
        setAssetTimeline(Array.isArray(timelineData.points) ? timelineData.points : []);
        setActionHistory(Array.isArray(actionData.actions) ? actionData.actions : []);
        setActionState(actionData.state ?? null);
        mergeOperatorState(selectedEvent.event_id, actionData.state ?? null);
      })
      .catch(() => {
        if (cancelled) return;
        setAssetTimeline([]);
        setActionHistory([]);
        setActionState(null);
      })
      .finally(() => {
        if (!cancelled) setTimelineLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [mergeOperatorState, selectedEvent?.entity_id, selectedEvent?.entity, selectedEvent?.event_id]);

  const handleSubmitAction = async (actionType, { assignee, note }) => {
    if (!selectedEvent?.event_id) return;

    setActionLoading(true);
    try {
      const res = await fetch(`${API_BASE}/alerts/${selectedEvent.event_id}/actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action_type: actionType,
          assignee,
          note,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setActionState(data.state ?? null);
      setActionHistory((prev) => (data.action ? [data.action, ...prev] : prev));
      mergeOperatorState(selectedEvent.event_id, data.state ?? null);
    } catch {
      // ignore for now; panel remains usable
    } finally {
      setActionLoading(false);
    }
  };

  const summary = useMemo(() => deriveStatus(events), [events]);
  const trendData = useMemo(() => deriveTrend(events), [events]);

  return (
    <div className="space-y-5">
      <StatusCards
        {...summary}
        replayMetrics={liveMetrics}
      />

      <div className="flex gap-5">
        <div className="w-[60%]">
          <EventTable
            events={events}
            onSelectEvent={setSelectedEvent}
            selectedId={selectedEvent?.id}
            onClearLogs={handleClearLogs}
          />
        </div>
        <div className="w-[40%]">
          <ExplanationPanel
            event={selectedEvent}
            actionHistory={actionHistory}
            actionState={actionState}
            actionLoading={actionLoading}
            onSubmitAction={handleSubmitAction}
          />
        </div>
      </div>

      <AssetDrilldownChart
        assetId={selectedEvent?.entity_id || selectedEvent?.entity || null}
        data={assetTimeline}
        selectedEventId={selectedEvent?.event_id ?? null}
        activeMetric={timelineMetric}
        onMetricChange={setTimelineMetric}
        loading={timelineLoading}
      />

      <TrendChart data={trendData} />
    </div>
  );
}
