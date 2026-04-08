import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useWebSocket } from './hooks/useWebSocket';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import Dashboard from './pages/Dashboard';
import Validation from './pages/Validation';

function Layout() {
  const { status } = useWebSocket(null);

  return (
    <div className="dark min-h-screen bg-gray-900 text-white">
      <Sidebar />
      <div className="ml-56">
        <TopBar title="Smart Warehouse Control Panel" wsStatus={status} />
        <main className="pt-14 p-6 min-h-screen">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/validation" element={<Validation />} />
            <Route
              path="/events"
              element={
                <div className="text-gray-400 py-20 text-center">
                  Events page coming soon...
                </div>
              }
            />
            <Route
              path="/settings"
              element={
                <div className="text-gray-400 py-20 text-center">
                  Settings page coming soon...
                </div>
              }
            />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout />
    </BrowserRouter>
  );
}
