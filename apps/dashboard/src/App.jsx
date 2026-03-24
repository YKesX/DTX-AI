import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useWebSocket } from './hooks/useWebSocket';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import Dashboard from './pages/Dashboard';

function Layout() {
  const { status } = useWebSocket(null);

  return (
    <div className="dark min-h-screen bg-gray-900 text-white">
      <Sidebar />
      <div className="ml-56">
        <TopBar title="Akıllı Depo Yönetim Paneli" wsStatus={status} />
        <main className="pt-14 p-6 min-h-screen">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route
              path="/events"
              element={
                <div className="text-gray-400 py-20 text-center">
                  Olaylar sayfası yakında…
                </div>
              }
            />
            <Route
              path="/settings"
              element={
                <div className="text-gray-400 py-20 text-center">
                  Ayarlar sayfası yakında…
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
