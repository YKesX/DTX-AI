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
    <aside className="app-sidebar fixed left-0 top-0 z-30 flex h-screen w-56 flex-col border-r border-line">
      <div className="sidebar-brand flex border-b border-line px-5 py-5">
        <div className="mb-1 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-line bg-paper shadow-none backdrop-blur-xl">
            <Warehouse className="h-6 w-6 shrink-0 text-[var(--accent-cyan)]" />
          </div>
          <div className="sidebar-copy">
            <span className="block font-serif text-2xl font-semibold tracking-tight text-ink">DTX-AI</span>
            <span className="text-[10px] uppercase tracking-[0.24em] text-dim">
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
            aria-label={label}
            title={label}
            end={to === '/'}
            className={({ isActive }) =>
              `sidebar-link flex items-center gap-3 rounded-2xl px-3 py-3 text-sm font-medium transition-all ${
                isActive
                  ? 'active'
                  : 'text-muted'
              }`
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            <span className="sidebar-copy">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer border-t border-line px-5 py-4 text-xs text-dim">
        <div className="text-[10px] uppercase tracking-[0.2em] text-dim">DTX-AI Console</div>
        <div className="mt-1 text-xs text-dim">v3.0 Final — Smart Warehouse</div>
      </div>
    </aside>
  );
}
