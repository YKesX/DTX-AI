import { useState, useEffect } from 'react';

export default function TopBar({ title, wsStatus }) {
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

  const isConnected = wsStatus === 'connected';

  return (
    <header className="fixed left-56 right-0 top-0 z-20 flex h-16 items-center justify-between border-b border-white/10 bg-[rgba(9,14,20,0.82)] px-6 backdrop-blur-2xl">
      <div>
        <h1 className="text-base font-semibold text-white">{title}</h1>
        <p className="text-[10px] uppercase tracking-[0.28em] text-slate-500">
          Live Operations Layer
        </p>
      </div>

      <div className="flex items-center gap-4">
        <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-sm shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] backdrop-blur-xl">
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                isConnected
                  ? 'bg-[var(--accent-green)]'
                  : 'bg-[var(--accent-red)]'
              }`}
            />
            <span className={isConnected ? 'text-emerald-300' : 'text-red-300'}>
              WebSocket
            </span>
          </div>
        </div>

        <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] backdrop-blur-xl">
          <span className="font-mono text-sm text-gray-300">{clock}</span>
        </div>
      </div>
    </header>
  );
}
