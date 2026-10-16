import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import Dashboard from './pages/Dashboard';
import Validation from './pages/Validation';
import Events from './pages/Events';
import Settings from './pages/Settings';
import { PreferencesProvider } from './context/Preferences';

function Layout() {
  return (
    <div className="control-shell min-h-screen text-ink">
      <Sidebar />
      <div className="app-content">
        <TopBar title="Smart Warehouse Control Panel" />
        <main className="app-main min-h-screen">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/validation" element={<Validation />} />
            <Route path="/events" element={<Events />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <PreferencesProvider>
    <BrowserRouter>
      <Layout />
    </BrowserRouter>
    </PreferencesProvider>
  );
}
