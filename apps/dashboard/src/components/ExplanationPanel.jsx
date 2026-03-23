/**
 * ExplanationPanel — shows the XAI explanation for the selected alert.
 *
 * @param {{ alert: DashboardAlert | null }} props
 */
export default function ExplanationPanel({ alert }) {
  if (!alert) {
    return (
      <div className="bg-white rounded-2xl shadow p-5">
        <h2 className="font-semibold text-gray-700 mb-2">Explanation</h2>
        <p className="text-sm text-gray-400">Click an alert to see its explanation.</p>
      </div>
    )
  }

  const { event, anomaly, explanation } = alert
  const features = explanation?.contributing_features ?? {}

  return (
    <div className="bg-white rounded-2xl shadow p-5 space-y-4">
      <h2 className="font-semibold text-gray-700">Explanation</h2>

      <div>
        <p className="text-sm font-medium text-gray-600">Asset</p>
        <p className="text-sm">
          {event?.asset_id} — Zone {event?.zone_id}
        </p>
      </div>

      <div>
        <p className="text-sm font-medium text-gray-600">Summary</p>
        <p className="text-sm text-gray-800">{explanation?.summary}</p>
      </div>

      {explanation?.recommendation && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
          <span className="font-semibold">Recommendation: </span>
          {explanation.recommendation}
        </div>
      )}

      {Object.keys(features).length > 0 && (
        <div>
          <p className="text-sm font-medium text-gray-600 mb-2">
            Contributing Features
          </p>
          <ul className="space-y-1">
            {Object.entries(features)
              .sort(([, a], [, b]) => b - a)
              .map(([feature, score]) => (
                <li key={feature} className="text-sm flex items-center gap-2">
                  <span className="w-24 capitalize text-gray-600">{feature}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full"
                      style={{ width: `${Math.min(score * 100, 100)}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-500">
                    {(score * 100).toFixed(1)}%
                  </span>
                </li>
              ))}
          </ul>
        </div>
      )}

      <div className="text-xs text-gray-400">
        Anomaly score: {anomaly?.anomaly_score?.toFixed(4)} | Severity:{' '}
        <span className="capitalize">{anomaly?.severity}</span>
      </div>
    </div>
  )
}
