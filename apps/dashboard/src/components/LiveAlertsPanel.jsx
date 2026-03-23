/**
 * Severity badge colours.
 */
const SEVERITY_STYLES = {
  critical: 'bg-red-100 text-red-700 border-red-300',
  warning: 'bg-yellow-100 text-yellow-700 border-yellow-300',
  info: 'bg-blue-100 text-blue-700 border-blue-300',
}

/**
 * LiveAlertsPanel — shows incoming DashboardAlert objects in real time.
 *
 * @param {{ alerts: DashboardAlert[], onSelect: (alert) => void }} props
 */
export default function LiveAlertsPanel({ alerts, onSelect }) {
  if (alerts.length === 0) {
    return (
      <div className="bg-white rounded-2xl shadow p-5">
        <h2 className="font-semibold text-gray-700 mb-2">Live Alerts</h2>
        <p className="text-sm text-gray-400">No alerts yet — waiting for events…</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-2xl shadow p-5">
      <h2 className="font-semibold text-gray-700 mb-3">Live Alerts</h2>
      <ul className="space-y-2 max-h-72 overflow-y-auto">
        {alerts.map((alert) => (
          <li
            key={alert.alert_id}
            className={`border rounded-lg px-3 py-2 cursor-pointer hover:shadow-sm text-sm ${
              SEVERITY_STYLES[alert.anomaly?.severity] ?? SEVERITY_STYLES.info
            }`}
            onClick={() => onSelect(alert)}
          >
            <div className="flex justify-between">
              <span className="font-medium">{alert.event?.asset_id}</span>
              <span className="uppercase text-xs font-bold">
                {alert.anomaly?.severity}
              </span>
            </div>
            <p className="text-xs mt-0.5 truncate text-gray-500">
              {alert.explanation?.summary}
            </p>
          </li>
        ))}
      </ul>
    </div>
  )
}
