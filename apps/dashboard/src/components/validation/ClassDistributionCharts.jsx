import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import Card from '../ui/Card';

export default function ClassDistributionCharts({ metrics }) {
  const gt = metrics?.per_class_ground_truth ?? {};
  const pred = metrics?.per_class_predicted ?? {};
  const classes = Array.from(new Set([...Object.keys(gt), ...Object.keys(pred)]));
  const data = classes.map((label) => ({
    label,
    groundTruth: gt[label] ?? 0,
    predicted: pred[label] ?? 0,
  }));

  return (
    <Card className="p-5">
      <div className="mb-4">
        <h2 className="section-title">
          Class Distributions
        </h2>
        <p className="mt-1 text-sm text-muted">
          Class-by-class comparison of ground truth and model predictions
        </p>
      </div>

      {data.length === 0 ? (
        <div className="flex h-64 items-center justify-center text-sm text-dim">
          No replay data available.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line-soft)" />
            <XAxis
              dataKey="label"
              tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
              axisLine={{ stroke: 'var(--line-strong)' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
              axisLine={{ stroke: 'var(--line-strong)' }}
              tickLine={false}
            />
            <Tooltip />
            <Legend />
            <Bar dataKey="groundTruth" fill="var(--chart-primary)" name="Ground Truth" radius={[10, 10, 0, 0]} />
            <Bar dataKey="predicted" fill="var(--chart-secondary)" name="Predicted" radius={[10, 10, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
