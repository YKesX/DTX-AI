import { MousePointerClick } from 'lucide-react';
import Badge from '../ui/Badge';
import Card from '../ui/Card';

function FeatureBar({ feature }) {
  const pct = Math.round(feature.impact * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-gray-300 font-medium">{feature.name}</span>
        <span className="text-gray-500">{feature.value}</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-blue-500 transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="text-xs text-gray-400 w-8 text-right">{feature.impact.toFixed(2)}</span>
      </div>
    </div>
  );
}

export default function ExplanationPanel({ event }) {
  if (!event) {
    return (
      <Card className="h-full flex flex-col items-center justify-center gap-3 p-10 text-center">
        <MousePointerClick className="w-10 h-10 text-gray-600" />
        <p className="text-gray-500 text-sm">Bir olay seçin</p>
        <p className="text-gray-600 text-xs">
          Detayları görmek için tablodan bir olay satırına tıklayın.
        </p>
      </Card>
    );
  }

  return (
    <Card className="flex flex-col gap-5 p-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Varlık</p>
          <p className="text-white font-semibold text-base">{event.entity}</p>
        </div>
        <Badge severity={event.severity} />
      </div>

      {/* Anomaly type + score */}
      <div className="bg-gray-700/30 rounded-lg p-3 flex items-center justify-between">
        <span className="text-sm text-gray-300">{event.anomaly_type}</span>
        <span
          className={`font-bold text-lg ${
            event.anomaly_score >= 0.8
              ? 'text-red-400'
              : event.anomaly_score >= 0.6
              ? 'text-orange-400'
              : event.anomaly_score >= 0.4
              ? 'text-yellow-400'
              : 'text-green-400'
          }`}
        >
          {event.anomaly_score.toFixed(2)}
        </span>
      </div>

      {/* Top features */}
      <div>
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">
          Önemli Özellikler
        </p>
        <div className="space-y-3">
          {event.top_features.map((f) => (
            <FeatureBar key={f.name} feature={f} />
          ))}
        </div>
      </div>

      {/* Explanation */}
      <div>
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Açıklama</p>
        <div className="bg-gray-700/20 border border-gray-700 rounded-lg p-3">
          <p className="text-sm text-gray-300 leading-relaxed">{event.explanation}</p>
        </div>
      </div>
    </Card>
  );
}
