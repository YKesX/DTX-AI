import { Bell, Wifi, Clock, Activity } from 'lucide-react';
import Card from '../ui/Card';

function StatCard({ icon: Icon, label, value, pulse }) {
  return (
    <Card className="relative overflow-hidden p-5">
      <div className="mb-5 flex items-start justify-between gap-3">
        <p className="text-[10px] uppercase tracking-[0.14em] text-dim">{label}</p>
        <Icon className={`h-4 w-4 shrink-0 ${pulse ? 'text-red-800' : 'text-dim'}`} />
      </div>
      <div className="min-w-0">
        <p
          className={`stat-value ${
            pulse ? 'text-red-800' : 'text-ink'
          }`}
        >
          {value}
        </p>
      </div>
    </Card>
  );
}

export default function StatusCards({ activeAlerts, connectedSensors, lastDataTime, systemStatus, replayMetrics }) {
  const replayTotal = replayMetrics?.total_replayed ?? 0;
  const replayCorrect = replayMetrics?.total_correct ?? 0;
  const replayAccuracy = replayMetrics?.running_accuracy ?? 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6 gap-4">
      <StatCard
        icon={Bell}
        label="Active Alerts"
        value={activeAlerts}
        pulse={activeAlerts > 0}
      />
      <StatCard
        icon={Wifi}
        label="Connected Sensors"
        value={connectedSensors}
      />
      <StatCard
        icon={Clock}
        label="Last Data"
        value={lastDataTime}
      />
      <StatCard
        icon={Activity}
        label="System Status"
        value={systemStatus}
      />
      <StatCard
        icon={Activity}
        label="Replay Correct"
        value={`${replayCorrect}/${replayTotal}`}
      />
      <StatCard
        icon={Activity}
        label="Replay Accuracy"
        value={`${(replayAccuracy * 100).toFixed(1)}%`}
      />
    </div>
  );
}
