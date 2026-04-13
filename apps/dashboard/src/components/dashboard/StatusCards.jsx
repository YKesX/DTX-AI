import { Bell, Wifi, Clock, Activity } from 'lucide-react';
import Card from '../ui/Card';

function StatCard({ icon: Icon, label, value, pulse }) {
  return (
    <Card className="relative overflow-hidden p-5">
      <div className={`absolute inset-x-6 top-0 h-px ${pulse ? 'bg-[linear-gradient(90deg,transparent,var(--accent-red),transparent)]' : 'bg-[linear-gradient(90deg,transparent,var(--accent-cyan),var(--accent-blue),transparent)]'}`} />
      <div className="flex items-center gap-4">
      <div
        className={`rounded-xl border p-3 ${
          pulse
            ? 'border-white/12 bg-white/8'
            : 'border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.08),rgba(140,241,222,0.04))]'
        }`}
      >
        <Icon
          className={`h-5 w-5 ${pulse ? 'text-red-300' : 'text-[var(--accent-cyan)]'}`}
        />
      </div>
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-[0.22em] text-gray-500">{label}</p>
        <p
          className={`mt-1 text-xl font-bold ${
            pulse ? 'text-red-300' : 'text-white'
          }`}
        >
          {value}
        </p>
      </div>
      </div>
    </Card>
  );
}

export default function StatusCards({ activeAlerts, connectedSensors, lastDataTime, systemStatus, replayMetrics }) {
  const replayTotal = replayMetrics?.total_replayed ?? 0;
  const replayCorrect = replayMetrics?.total_correct ?? 0;
  const replayAccuracy = replayMetrics?.running_accuracy ?? 0;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
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
