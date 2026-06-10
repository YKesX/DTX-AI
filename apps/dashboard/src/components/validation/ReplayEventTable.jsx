import Card from '../ui/Card';
import Badge from '../ui/Badge';

export default function ReplayEventTable({ events = [] }) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-white/10 px-5 py-4">
        <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-gray-200">
          Recent Replay Events
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10 text-xs uppercase tracking-[0.18em] text-gray-500">
              <th className="px-5 py-3 text-left">Time</th>
              <th className="px-5 py-3 text-left">Asset</th>
              <th className="px-5 py-3 text-left">Model</th>
              <th className="px-5 py-3 text-left">GT</th>
              <th className="px-5 py-3 text-left">Pred</th>
              <th className="px-5 py-3 text-left">Correct</th>
              <th className="px-5 py-3 text-left">Score</th>
              <th className="px-5 py-3 text-left">Severity</th>
            </tr>
          </thead>
          <tbody>
            {events.length === 0 ? (
              <tr>
                <td colSpan="8" className="px-5 py-10 text-center text-sm text-gray-500">
                  No replay records found.
                </td>
              </tr>
            ) : (
              events.map((event) => (
                <tr key={event.id} className="border-b border-white/5">
                  <td className="px-5 py-3 text-gray-400">
                    {new Date(event.timestamp).toLocaleTimeString('en-GB', {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    })}
                  </td>
                  <td className="px-5 py-3 font-medium text-white">{event.entity_id}</td>
                  <td className="px-5 py-3 text-gray-300">{event.active_model ?? 'n/a'}</td>
                  <td className="px-5 py-3 text-gray-300">{event.ground_truth_name ?? '—'}</td>
                  <td className="px-5 py-3 text-gray-300">{event.predicted_label ?? '—'}</td>
                  <td className="px-5 py-3 text-gray-300">
                    {event.prediction_correct == null ? '—' : event.prediction_correct ? '✓' : '✗'}
                  </td>
                  <td className="px-5 py-3 text-gray-300">{(event.anomaly_score ?? 0).toFixed(2)}</td>
                  <td className="px-5 py-3"><Badge severity={event.severity} /></td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
