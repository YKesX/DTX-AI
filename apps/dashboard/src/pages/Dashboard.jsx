import { useState, useEffect, useMemo } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import StatusCards from '../components/dashboard/StatusCards';
import EventTable from '../components/dashboard/EventTable';
import ExplanationPanel from '../components/dashboard/ExplanationPanel';
import TrendChart from '../components/dashboard/TrendChart';
import { normalizeAlerts } from '../lib/normalizeAlert';

// Use environment variables defined in .env (copy from .env.example).
// Falls back to localhost defaults for convenience during development.
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
      systemStatus: 'Çevrimiçi',
    };
  }

  // Backend severities: info | warning | critical
  const activeAlerts = events.filter(
    (e) => ['warning', 'critical', 'high'].includes(e.severity)
  ).length;

  const connectedSensors = new Set(
    events.map((e) => e.entity_id || e.entity).filter(Boolean)
  ).size;

  const latest = events.reduce((a, b) =>
    new Date(a.timestamp) > new Date(b.timestamp) ? a : b
  );
  const lastDataTime = new Date(latest.timestamp).toLocaleTimeString('tr-TR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  const hasCritical = events.some((e) => e.severity === 'critical');
  const hasWarning  = events.some((e) => e.severity === 'warning' || e.severity === 'high');
  const systemStatus = hasCritical ? 'Kritik' : hasWarning ? 'Uyarı' : 'Çevrimiçi';

  return { activeAlerts, connectedSensors, lastDataTime, systemStatus };
}

function deriveTrend(events) {
  return [...events]
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    .slice(-20)
    .map((e) => ({
      time: new Date(e.timestamp).toLocaleTimeString('tr-TR', {
        hour: '2-digit',
        minute: '2-digit',
      }),
      score: e.anomaly_score ?? 0,
    }));
}

export default function Dashboard() {
  const { events, setEvents, status } = useWebSocket(WS_URL);
  const [selectedEvent, setSelectedEvent] = useState(null);

  // On mount, seed the list with events already stored in the API.
  // GET /alerts/ returns { alerts: [...EventLog rows], count: N }
  useEffect(() => {
    fetch(`${API_BASE}/alerts/`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        // Accept both { alerts: [...] } and a bare array for flexibility
        const rows = Array.isArray(data) ? data : (data.alerts ?? []);
        if (rows.length === 0) return;
        const normalized = normalizeAlerts(rows);
        setEvents((prev) => {
          const existingIds = new Set(prev.map((e) => e.id));
          const fresh = normalized.filter((e) => !existingIds.has(e.id));
          return [...prev, ...fresh];
        });
      })
      .catch(() => {
        // API not reachable — fall back to whatever WS / mock provides
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const summary = useMemo(() => deriveStatus(events), [events]);
  const trendData = useMemo(() => deriveTrend(events), [events]);

  return (
    <div className="space-y-5">
      {/* Status cards — full width */}
      <StatusCards {...summary} />

      {/* Middle row: table (60%) + explanation (40%) */}
      <div className="flex gap-5">
        <div className="w-[60%]">
          <EventTable
            events={events}
            onSelectEvent={setSelectedEvent}
            selectedId={selectedEvent?.id}
          />
        </div>
        <div className="w-[40%]">
          <ExplanationPanel event={selectedEvent} />
        </div>
      </div>

      {/* Trend chart — full width */}
      <TrendChart data={trendData} />
    </div>
  );
}
