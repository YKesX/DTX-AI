import { NavLink } from 'react-router-dom';
import { Warehouse, LayoutDashboard, ListChecks, Settings, FlaskConical } from 'lucide-react';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/validation', label: 'AI Validation', icon: FlaskConical },
  { to: '/events', label: 'Events', icon: ListChecks },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 z-30 flex h-screen w-56 flex-col border-r border-white/10 bg-[rgba(10,15,21,0.9)] backdrop-blur-2xl">
      <div className="border-b border-white/10 px-5 py-5">
        <div className="mb-1 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/15 bg-white/8 shadow-[inset_0_1px_0_rgba(255,255,255,0.16)] backdrop-blur-xl">
            <Warehouse className="h-6 w-6 shrink-0 text-[var(--accent-cyan)]" />
          </div>
          <div>
            <span className="block text-lg font-bold tracking-tight text-white">DTX-AI</span>
            <span className="text-[10px] uppercase tracking-[0.24em] text-gray-500">
              Control Room
            </span>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-2xl px-3 py-3 text-sm font-medium transition-all ${
                isActive
                  ? 'border border-[rgba(140,241,222,0.16)] bg-[rgba(255,255,255,0.06)] text-[rgba(229,255,248,0.96)] shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
                  : 'text-gray-400 hover:border hover:border-white/10 hover:bg-white/6 hover:text-white'
              }`
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 px-5 py-4 text-xs text-gray-600">
        <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500">DTX-AI Console</div>
        <div className="mt-1 text-xs text-gray-600">v2.0 — Smart Warehouse</div>
      </div>
    </aside>
  );
}
