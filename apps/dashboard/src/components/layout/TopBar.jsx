import { useState, useEffect } from 'react';

export default function TopBar({ title, wsStatus }) {
  const [clock, setClock] = useState('');

  useEffect(() => {
    const tick = () =>
      setClock(
        new Date().toLocaleTimeString('tr-TR', {
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
    <header className="fixed top-0 left-56 right-0 h-14 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-6 z-20">
      <h1 className="text-white font-semibold text-base">{title}</h1>

      <div className="flex items-center gap-4">
        {/* WebSocket indicator */}
        <div className="flex items-center gap-2 text-sm">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              isConnected ? 'bg-green-400 shadow-[0_0_6px_#4ade80]' : 'bg-red-500'
            }`}
          />
          <span className={isConnected ? 'text-green-400' : 'text-red-400'}>
            WebSocket
          </span>
        </div>

        {/* Clock */}
        <span className="text-gray-400 text-sm font-mono">{clock}</span>
      </div>
    </header>
  );
}
