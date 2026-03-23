import { useState } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import SystemStatusCard from './components/SystemStatusCard'
import LiveAlertsPanel from './components/LiveAlertsPanel'
import RecentEventList from './components/RecentEventList'
import ExplanationPanel from './components/ExplanationPanel'

export default function App() {
  const { alerts, connected } = useWebSocket()
  const [selectedAlert, setSelectedAlert] = useState(null)

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-gray-900 text-white px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-bold tracking-tight">
          DTX-AI — Smart Warehouse Digital Twin
        </h1>
        <SystemStatusCard connected={connected} />
      </header>

      {/* Main grid */}
      <main className="max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: live alerts + recent events */}
        <div className="lg:col-span-2 space-y-6">
          <LiveAlertsPanel
            alerts={alerts}
            onSelect={setSelectedAlert}
          />
          <RecentEventList alerts={alerts} />
        </div>

        {/* Right column: explanation */}
        <div>
          <ExplanationPanel alert={selectedAlert} />
        </div>
      </main>
    </div>
  )
}
