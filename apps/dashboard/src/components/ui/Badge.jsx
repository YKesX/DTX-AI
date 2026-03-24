const severityClasses = {
  low: 'bg-green-900/60 text-green-300 border border-green-700',
  medium: 'bg-yellow-900/60 text-yellow-300 border border-yellow-700',
  high: 'bg-orange-900/60 text-orange-300 border border-orange-700',
  critical: 'bg-red-900/60 text-red-300 border border-red-700',
};

const severityLabels = {
  low: 'Düşük',
  medium: 'Orta',
  high: 'Yüksek',
  critical: 'Kritik',
};

export default function Badge({ severity }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide ${
        severityClasses[severity] ?? severityClasses.low
      }`}
    >
      {severityLabels[severity] ?? severity}
    </span>
  );
}
