import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
} from 'recharts';
import Card from '../ui/Card';

const METRICS = [
  { key: 'vibration', label: 'Vibration', color: '#8cf1de' },
  { key: 'temperature', label: 'Temperature', color: '#ff8098' },
  { key: 'pressure', label: 'Pressure', color: '#7fe1ff' },
  { key: 'anomaly_score', label: 'Anomaly Score', color: '#8cb8ff' },
];

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-[rgba(92,117,142,0.28)] bg-[rgba(12,18,25,0.96)] px-3 py-2 text-xs shadow-xl backdrop-blur-xl">
      <p className="mb-2 text-gray-400">{label}</p>
      {payload.map((item) => (
        <p key={item.dataKey} className="font-medium" style={{ color: item.color }}>
          {item.name}: {typeof item.value === 'number' ? item.value.toFixed(2) : '—'}
        </p>
      ))}
    </div>
  );
}

export default function AssetDrilldownChart({
  assetId,
  data = [],
  selectedEventId = null,
  activeMetric = 'vibration',
  onMetricChange,
  loading = false,
}) {
  const chartMetric = METRICS.find((metric) => metric.key === activeMetric) ?? METRICS[0];
  const chartData = data.map((point) => ({
    ...point,
    time: new Date(point.timestamp).toLocaleTimeString('tr-TR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }),
  }));

  const selectedPoint = chartData.find((point) => point.event_id === selectedEventId) ?? null;

  return (
    <Card className="p-5">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-200">
            Asset Drilldown Chart
          </h2>
          <p className="mt-1 text-sm text-gray-400">
            {assetId ? `Latest readings for ${assetId}` : 'Select an event from the table to view the chart'}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {METRICS.map((metric) => (
            <button
              key={metric.key}
              type="button"
              onClick={() => onMetricChange?.(metric.key)}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                metric.key === chartMetric.key
                  ? 'border-emerald-300/40 bg-emerald-300/12 text-emerald-100'
                  : 'border-[rgba(92,117,142,0.26)] bg-[rgba(16,24,33,0.84)] text-gray-300 hover:bg-[rgba(32,44,57,0.82)]'
              }`}
            >
              {metric.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex h-[260px] items-center justify-center text-sm text-gray-400">
          Loading chart data...
        </div>
      ) : chartData.length === 0 ? (
        <div className="flex h-[260px] items-center justify-center text-sm text-gray-500">
          No historical data found for this asset.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData} margin={{ top: 8, right: 12, left: -14, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(111,127,144,0.22)" />
          <XAxis
            dataKey="time"
            tick={{ fill: '#7f90a0', fontSize: 11 }}
            axisLine={{ stroke: 'rgba(111,127,144,0.28)' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#7f90a0', fontSize: 11 }}
            axisLine={{ stroke: 'rgba(111,127,144,0.28)' }}
            tickLine={false}
          />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey={chartMetric.key}
              name={chartMetric.label}
              stroke={chartMetric.color}
              strokeWidth={2.5}
              dot={{ fill: chartMetric.color, r: 3 }}
              activeDot={{ fill: chartMetric.color, r: 5 }}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="anomaly_score"
              name="Anomaly Score"
              stroke="#8cb8ff"
              strokeOpacity={chartMetric.key === 'anomaly_score' ? 0.22 : 0.48}
              strokeWidth={1.5}
              dot={false}
              connectNulls
            />
            {selectedPoint ? (
              <ReferenceDot
                x={selectedPoint.time}
                y={selectedPoint[chartMetric.key]}
                r={6}
                fill="#f8fafc"
                stroke={chartMetric.color}
                strokeWidth={2}
              />
            ) : null}
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
