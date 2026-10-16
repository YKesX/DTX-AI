import { useEffect, useMemo, useState } from 'react';
import DemoControlPanel from '../components/validation/DemoControlPanel';
import ReplaySummaryCards from '../components/validation/ReplaySummaryCards';
import ClassDistributionCharts from '../components/validation/ClassDistributionCharts';
import ConfusionMatrix from '../components/validation/ConfusionMatrix';
import ReplayEventTable from '../components/validation/ReplayEventTable';
import Card from '../components/ui/Card';
import { normalizeAlerts } from '../lib/normalizeAlert';

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export default function Validation() {
  const [metrics, setMetrics] = useState(null);
  const [events, setEvents] = useState([]);

  useEffect(() => {
    let cancelled = false;

    const load = () => {
      Promise.all([
        fetch(`${API_BASE}/metrics/live`).then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        }),
        fetch(`${API_BASE}/alerts/?limit=100`).then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        }),
      ])
        .then(([metricsBody, alertsBody]) => {
          if (cancelled) return;
          setMetrics(metricsBody);
          const normalized = normalizeAlerts(alertsBody.alerts ?? []);
          setEvents(
            normalized.filter((event) =>
              ['dataset_replay', 'hardware_demo'].includes(event.source)
            )
          );
        })
        .catch(() => {
          if (cancelled) return;
          setMetrics(null);
          setEvents([]);
        });
    };

    load();
    const timer = setInterval(load, 4000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const modelCounts = useMemo(
    () => Object.entries(metrics?.per_model ?? {}),
    [metrics]
  );

  return (
    <div className="space-y-6">
      <div className="page-heading">
        <p className="eyebrow">DTX-AI / Model performance</p>
        <h1>AI Validation</h1>
        <p className="mt-1 text-sm text-muted">
          Replay-mode performance, class distributions, and model behavior
        </p>
      </div>

      <DemoControlPanel />

      <ReplaySummaryCards metrics={metrics} />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[2fr,1fr]">
        <ClassDistributionCharts metrics={metrics} />
        <Card className="p-5">
          <h2 className="section-title">
            Model Usage
          </h2>
          <p className="mt-1 text-sm text-muted">
            Number of events processed by each model during replay
          </p>
          <div className="mt-4 space-y-3">
            {modelCounts.length === 0 ? (
              <p className="text-sm text-dim">No model data yet.</p>
            ) : (
              modelCounts.map(([modelKey, count]) => (
                <div
                  key={modelKey}
                  className="control-panel-muted flex items-center justify-between rounded-2xl px-4 py-3"
                >
                  <span className="text-sm text-muted">{modelKey}</span>
                  <span className="text-lg font-semibold text-ink">{count}</span>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      <ConfusionMatrix metrics={metrics} />
      <ReplayEventTable events={events.slice(0, 20)} />
    </div>
  );
}
