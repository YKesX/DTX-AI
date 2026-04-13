import Card from '../ui/Card';

const SUMMARY_ITEMS = [
  { key: 'total_replayed', label: 'Total Replay' },
  { key: 'total_correct', label: 'Correct Predictions' },
  { key: 'running_accuracy', label: 'Running Accuracy', isPercent: true },
];

export default function ReplaySummaryCards({ metrics }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      {SUMMARY_ITEMS.map((item) => {
        const rawValue = metrics?.[item.key] ?? 0;
        const value = item.isPercent ? `${(rawValue * 100).toFixed(1)}%` : rawValue;

        return (
          <Card key={item.key} className="p-5">
            <p className="text-xs uppercase tracking-[0.22em] text-gray-500">{item.label}</p>
            <p className="mt-2 text-3xl font-semibold text-white">{value}</p>
          </Card>
        );
      })}
    </div>
  );
}
