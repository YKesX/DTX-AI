import { NavLink } from 'react-router-dom';
import { Warehouse, LayoutDashboard, ListChecks, Settings } from 'lucide-react';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/events', label: 'Olaylar', icon: ListChecks },
  { to: '/settings', label: 'Ayarlar', icon: Settings },
];

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-screen w-56 bg-gray-950 border-r border-gray-800 flex flex-col z-30">
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-gray-800">
        <Warehouse className="w-7 h-7 text-blue-400 shrink-0" />
        <span className="text-white font-bold text-lg tracking-tight">DTX-AI</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-gray-800 text-xs text-gray-600">
        v0.1.0 — Smart Warehouse
      </div>
    </aside>
  );
}
