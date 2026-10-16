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
  { key: 'vibration', label: 'Vibration', color: 'var(--chart-primary)' },
  { key: 'temperature', label: 'Temperature', color: 'var(--accent-red)' },
  { key: 'pressure', label: 'Pressure', color: 'var(--chart-tertiary)' },
  { key: 'anomaly_score', label: 'Anomaly Score', color: 'var(--chart-secondary)' },
];

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-line bg-paper px-3 py-2 text-xs shadow-xl backdrop-blur-xl">
      <p className="mb-2 text-muted">{label}</p>
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
          <h2 className="section-title">
            Asset Drilldown Chart
          </h2>
          <p className="mt-1 text-sm text-muted">
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
                  ? 'border-emerald-300/40 bg-emerald-300/12 text-emerald-800'
                  : 'border-line bg-paper text-muted hover:bg-paper-selected'
              }`}
            >
              {metric.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex h-[260px] items-center justify-center text-sm text-muted">
          Loading chart data...
        </div>
      ) : chartData.length === 0 ? (
        <div className="flex h-[260px] items-center justify-center text-sm text-dim">
          No historical data found for this asset.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData} margin={{ top: 8, right: 12, left: -14, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--line-soft)" />
          <XAxis
            dataKey="time"
            tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
            axisLine={{ stroke: 'var(--line-strong)' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
            axisLine={{ stroke: 'var(--line-strong)' }}
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
              stroke="var(--chart-secondary)"
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
