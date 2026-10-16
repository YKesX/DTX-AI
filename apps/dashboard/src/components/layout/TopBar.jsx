import { useState, useEffect } from 'react';

export default function TopBar({ title }) {
  const [clock, setClock] = useState('');

  useEffect(() => {
    const tick = () =>
      setClock(
        new Date().toLocaleTimeString('en-GB', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="app-topbar fixed left-56 right-0 top-0 z-20 flex h-16 items-center justify-between border-b border-line px-6">
      <div>
        <h1 className="topbar-title text-xl font-semibold text-ink">{title}</h1>
        <p className="topbar-subtitle text-[10px] uppercase tracking-[0.28em] text-dim">
          Live Operations Layer
        </p>
      </div>

      <div className="flex items-center gap-4">
        <div className="topbar-clock rounded-full border border-line bg-paper px-3 py-1.5">
          <span className="font-mono text-sm text-muted">{clock}</span>
        </div>
      </div>
    </header>
  );
}
