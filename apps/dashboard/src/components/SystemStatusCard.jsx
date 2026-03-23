/**
 * SystemStatusCard — shows whether the API backend is reachable
 * via the WebSocket connection (connected: true/false).
 */
export default function SystemStatusCard({ connected }) {
  return (
    <div className="bg-white rounded-2xl shadow p-5 flex items-center gap-4">
      <div
        className={`w-4 h-4 rounded-full ${
          connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
        }`}
      />
      <div>
        <p className="text-sm font-semibold text-gray-700">Backend connection</p>
        <p className={`text-xs ${connected ? 'text-green-600' : 'text-red-600'}`}>
          {connected ? 'Live — receiving events' : 'Disconnected — retrying…'}
        </p>
      </div>
    </div>
  )
}
