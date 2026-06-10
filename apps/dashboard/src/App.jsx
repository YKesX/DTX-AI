import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useWebSocket } from './hooks/useWebSocket';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import Dashboard from './pages/Dashboard';
import Validation from './pages/Validation';

function Layout() {
  const { status } = useWebSocket(null);

  return (
    <div className="control-shell dark min-h-screen text-white">
      <Sidebar />
      <div className="ml-56">
        <TopBar title="Smart Warehouse Control Panel" wsStatus={status} />
        <main className="min-h-screen px-6 pb-8 pt-16">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/validation" element={<Validation />} />
            <Route
              path="/events"
              element={
                <div className="py-20 text-center text-gray-400">
                  Events page coming soon...
                </div>
              }
            />
            <Route
              path="/settings"
              element={
                <div className="py-20 text-center text-gray-400">
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
