const severityClasses = {
  // Backend severity values
  info:     'border border-emerald-300/35 bg-emerald-300/10 text-emerald-100',
  warning:  'border border-amber-500/45 bg-amber-500/12 text-amber-200',
  critical: 'border border-red-500/45 bg-red-500/14 text-red-200',
  // Legacy / mock severity values
  low:      'border border-sky-300/35 bg-sky-300/10 text-sky-100',
  medium:   'border border-amber-500/45 bg-amber-500/12 text-amber-200',
  high:     'border border-blue-400/45 bg-blue-400/12 text-blue-100',
};

const severityLabels = {
  info:     'Info',
  warning:  'Warning',
  critical: 'Critical',
  low:      'Low',
  medium:   'Medium',
  high:     'High',
};

export default function Badge({ severity }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold tracking-wide ${
        severityClasses[severity] ?? severityClasses.low
      }`}
    >
      {severityLabels[severity] ?? severity}
    </span>
  );
}
