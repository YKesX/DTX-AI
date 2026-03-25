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
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color} transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-300 w-8 text-right">{score.toFixed(2)}</span>
    </div>
  );
}

export default function EventTable({ events = [], onSelectEvent, selectedId }) {
  return (
    <Card className="overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-700">
        <h2 className="text-sm font-semibold text-gray-200 uppercase tracking-wide">
          Olay Akışı
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-500 uppercase tracking-wider border-b border-gray-700">
              <th className="text-left px-5 py-3">Zaman</th>
              <th className="text-left px-5 py-3">Varlık</th>
              <th className="text-left px-5 py-3">Anomali Tipi</th>
              <th className="text-left px-5 py-3">Skor</th>
              <th className="text-left px-5 py-3">Önem</th>
              <th className="text-left px-5 py-3">Detay</th>
            </tr>
          </thead>
          <tbody>
            {events.map((evt) => {
              const rowId = evt.id ?? evt.alert_id ?? evt.event_id;
              const isSelected = rowId === selectedId;
              const time = new Date(evt.timestamp).toLocaleTimeString('tr-TR', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
              });
              return (
                <tr
                  key={rowId}
                  onClick={() => onSelectEvent(evt)}
                  className={`border-b border-gray-700/50 cursor-pointer transition-colors ${
                    isSelected
                      ? 'bg-blue-900/20 border-blue-700/40'
                      : 'hover:bg-gray-700/30'
                  }`}
                >
                  <td className="px-5 py-3 text-gray-400 font-mono text-xs">{time}</td>
                  <td className="px-5 py-3 text-white font-medium">{evt.entity_id || evt.entity}</td>
                  <td className="px-5 py-3 text-gray-300">{evt.anomaly_type}</td>
                  <td className="px-5 py-3">
                    <ScoreBar score={evt.anomaly_score} />
                  </td>
                  <td className="px-5 py-3">
                    <Badge severity={evt.severity} />
                  </td>
                  <td className="px-5 py-3">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectEvent(evt);
                      }}
                      className="text-xs text-blue-400 hover:text-blue-300 hover:underline"
                    >
                      İncele →
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
