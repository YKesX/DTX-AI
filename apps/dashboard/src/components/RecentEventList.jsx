/**
 * RecentEventList — compact table of the last N events.
 *
 * @param {{ alerts: DashboardAlert[] }} props
 */
export default function RecentEventList({ alerts }) {
  return (
    <div className="bg-white rounded-2xl shadow p-5">
      <h2 className="font-semibold text-gray-700 mb-3">Recent Events</h2>
      {alerts.length === 0 ? (
        <p className="text-sm text-gray-400">No events recorded yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs text-left">
            <thead>
              <tr className="text-gray-500 border-b">
                <th className="pr-4 pb-1">Asset</th>
                <th className="pr-4 pb-1">Zone</th>
                <th className="pr-4 pb-1">Score</th>
                <th className="pr-4 pb-1">Type</th>
                <th className="pb-1">Time</th>
              </tr>
            </thead>
            <tbody>
              {alerts.slice(0, 20).map((alert) => (
                <tr key={alert.alert_id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="pr-4 py-1 font-medium">{alert.event?.asset_id}</td>
                  <td className="pr-4 py-1">{alert.event?.zone_id}</td>
                  <td className="pr-4 py-1">
                    {alert.anomaly?.anomaly_score?.toFixed(3)}
                  </td>
                  <td className="pr-4 py-1 capitalize">{alert.anomaly?.anomaly_type}</td>
                  <td className="py-1 text-gray-400">
                    {new Date(alert.created_at).toLocaleTimeString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
