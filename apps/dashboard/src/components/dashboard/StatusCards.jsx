import { Bell, Wifi, Clock, Activity } from 'lucide-react';
import Card from '../ui/Card';

function StatCard({ icon: Icon, label, value, pulse }) {
  return (
    <Card className="p-5 flex items-center gap-4">
      <div
        className={`p-2.5 rounded-lg ${
          pulse ? 'bg-red-900/40 animate-pulse' : 'bg-gray-700/60'
        }`}
      >
        <Icon
          className={`w-5 h-5 ${pulse ? 'text-red-400' : 'text-blue-400'}`}
        />
      </div>
      <div>
        <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
        <p
          className={`text-xl font-bold mt-0.5 ${
            pulse ? 'text-red-400' : 'text-white'
          }`}
        >
          {value}
        </p>
      </div>
    </Card>
  );
}

export default function StatusCards({ activeAlerts, connectedSensors, lastDataTime, systemStatus }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard
        icon={Bell}
        label="Aktif Uyarı"
        value={activeAlerts}
        pulse={activeAlerts > 0}
      />
      <StatCard
        icon={Wifi}
        label="Bağlı Sensör"
        value={connectedSensors}
      />
      <StatCard
        icon={Clock}
        label="Son Veri"
        value={lastDataTime}
      />
      <StatCard
        icon={Activity}
        label="Sistem Durumu"
        value={systemStatus}
      />
    </div>
  );
}
