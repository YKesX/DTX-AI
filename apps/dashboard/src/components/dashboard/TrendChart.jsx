import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';
import Card from '../ui/Card';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-[rgba(92,117,142,0.28)] bg-[rgba(12,18,25,0.96)] px-3 py-2 text-xs shadow-xl backdrop-blur-xl">
      <p className="text-gray-400 mb-1">{label}</p>
      <p className="font-semibold text-[var(--accent-cyan)]">
        Score: {payload[0].value.toFixed(2)}
      </p>
    </div>
  );
};

export default function TrendChart({ data = [] }) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-gray-200 uppercase tracking-wide">
          Anomaly Score Trend (Last 10 min)
        </h2>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="inline-block h-0.5 w-3 bg-[var(--accent-red)] opacity-80" />
          <span>Risk Threshold (0.70)</span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 4, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(111,127,144,0.22)" />
          <XAxis
            dataKey="time"
            tick={{ fill: '#7f90a0', fontSize: 11 }}
            axisLine={{ stroke: 'rgba(111,127,144,0.28)' }}
            tickLine={false}
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fill: '#7f90a0', fontSize: 11 }}
            axisLine={{ stroke: 'rgba(111,127,144,0.28)' }}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine
            y={0.7}
            stroke="var(--accent-red)"
            strokeDasharray="4 3"
            strokeOpacity={0.78}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="url(#trendStroke)"
            strokeWidth={2.4}
            dot={{ fill: 'var(--accent-cyan)', r: 3, stroke: '#0d141b', strokeWidth: 1.5 }}
            activeDot={{ r: 5, fill: 'var(--accent-blue)', stroke: '#0d141b', strokeWidth: 2 }}
          />
          <defs>
            <linearGradient id="trendStroke" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#8cf1de" />
              <stop offset="55%" stopColor="#7fe1ff" />
              <stop offset="100%" stopColor="#8cb8ff" />
            </linearGradient>
          </defs>
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
