import { useEffect, useState } from 'react';
import Card from '../ui/Card';

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

const SPLITS = ['holdout', 'episode_holdout', 'temporal', 'all'];

/**
 * Demo mode selector — choose between replaying the leakage-safe dataset
 * holdout and streaming live readings from the ESP32 hardware node, then
 * start/stop the run. The backend (/demo/*) owns the subprocess.
 */
export default function DemoControlPanel() {
  const [mode, setMode] = useState('dataset');
  const [models, setModels] = useState([]);
  const [model, setModel] = useState('lightgbm');
  const [split, setSplit] = useState('holdout');
  const [count, setCount] = useState(100);
  const [delay, setDelay] = useState(0.5);
  const [esp32Url, setEsp32Url] = useState('http://dtx-esp32.local');
  const [interval, setIntervalSec] = useState(1.0);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/demo/models`)
      .then((res) => (res.ok ? res.json() : { models: [] }))
      .then((body) => {
        const keys = body.models ?? [];
        setModels(keys);
        if (keys.length && !keys.includes(model)) setModel(keys[0]);
      })
      .catch(() => setModels([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      fetch(`${API_BASE}/demo/status`)
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then((body) => {
          if (!cancelled) setStatus(body);
        })
        .catch(() => {
          if (!cancelled) setStatus(null);
        });
    };
    poll();
    const timer = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const running = Boolean(status?.running);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const body =
        mode === 'dataset'
          ? { mode, model, split, count: Number(count), delay: Number(delay) }
          : { mode, model, esp32_url: esp32Url, interval: Number(interval), count: Number(count) };
      const res = await fetch(`${API_BASE}/demo/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail ?? `HTTP ${res.status}`);
      }
    } catch (err) {
      setError(String(err.message ?? err));
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    setError(null);
    try {
      await fetch(`${API_BASE}/demo/stop`, { method: 'POST' });
    } catch (err) {
      setError(String(err.message ?? err));
    } finally {
      setBusy(false);
    }
  };

  const inputClass =
    'w-full rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-200 focus:border-blue-500 focus:outline-none';
  const labelClass = 'block text-xs font-medium uppercase tracking-wide text-gray-400';

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-200">
            Demo Control
          </h2>
          <p className="mt-1 text-sm text-gray-400">
            Replay the unseen dataset holdout or stream live ESP32 sensor data
          </p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-semibold ${
            running ? 'bg-green-500/20 text-green-300' : 'bg-gray-700/40 text-gray-400'
          }`}
        >
          {running ? `running — ${status?.mode}` : 'idle'}
        </span>
      </div>

      <div className="mt-4 flex gap-2">
        {[
          { key: 'dataset', label: 'Dataset demo' },
          { key: 'hardware', label: 'IRL demo (ESP32)' },
        ].map((opt) => (
          <button
            key={opt.key}
            type="button"
            onClick={() => setMode(opt.key)}
            disabled={running}
            className={`rounded-2xl px-4 py-2 text-sm font-medium transition ${
              mode === opt.key
                ? 'bg-blue-600 text-white'
                : 'control-panel-muted text-gray-300 hover:text-white'
            } ${running ? 'opacity-60' : ''}`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <div>
          <label className={labelClass}>Model</label>
          <select
            className={inputClass}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={running}
          >
            {(models.length ? models : [model]).map((key) => (
              <option key={key} value={key}>
                {key}
              </option>
            ))}
          </select>
        </div>

        {mode === 'dataset' ? (
          <>
            <div>
              <label className={labelClass}>Split</label>
              <select
                className={inputClass}
                value={split}
                onChange={(e) => setSplit(e.target.value)}
                disabled={running}
              >
                {SPLITS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass}>Events</label>
              <input
                type="number"
                min="1"
                className={inputClass}
                value={count}
                onChange={(e) => setCount(e.target.value)}
                disabled={running}
              />
            </div>
            <div>
              <label className={labelClass}>Delay (s)</label>
              <input
                type="number"
                step="0.1"
                min="0"
                className={inputClass}
                value={delay}
                onChange={(e) => setDelay(e.target.value)}
                disabled={running}
              />
            </div>
          </>
        ) : (
          <>
            <div className="col-span-2">
              <label className={labelClass}>ESP32 URL</label>
              <input
                type="text"
                className={inputClass}
                value={esp32Url}
                onChange={(e) => setEsp32Url(e.target.value)}
                disabled={running}
                placeholder="http://dtx-esp32.local"
              />
            </div>
            <div>
              <label className={labelClass}>Interval (s)</label>
              <input
                type="number"
                step="0.1"
                min="0.1"
                className={inputClass}
                value={interval}
                onChange={(e) => setIntervalSec(e.target.value)}
                disabled={running}
              />
            </div>
          </>
        )}
      </div>

      <div className="mt-4 flex items-center gap-3">
        {running ? (
          <button
            type="button"
            onClick={stop}
            disabled={busy}
            className="rounded-2xl bg-red-600 px-5 py-2 text-sm font-semibold text-white transition hover:bg-red-500 disabled:opacity-60"
          >
            Stop demo
          </button>
        ) : (
          <button
            type="button"
            onClick={start}
            disabled={busy}
            className="rounded-2xl bg-blue-600 px-5 py-2 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-60"
          >
            Start {mode === 'dataset' ? 'dataset replay' : 'IRL demo'}
          </button>
        )}
        {error && <span className="text-sm text-red-400">{error}</span>}
      </div>

      {status?.log_tail?.length > 0 && (
        <pre className="mt-4 max-h-40 overflow-y-auto rounded-xl bg-black/40 p-3 text-xs leading-relaxed text-gray-400">
          {status.log_tail.join('\n')}
        </pre>
      )}
    </Card>
  );
}
