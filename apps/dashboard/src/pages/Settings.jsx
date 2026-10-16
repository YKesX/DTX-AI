import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Card from '../components/ui/Card';
import { usePreferences } from '../context/Preferences';
import { DEFAULT_PREFERENCES } from '../lib/preferences';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const inputClass = 'control-input mt-2 w-full rounded-xl px-3 py-2 text-sm';

export default function Settings() {
  const { preferences, savePreferences } = usePreferences();
  const [draft, setDraft] = useState(preferences);
  const [models, setModels] = useState([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [health, setHealth] = useState('');
  const [checking, setChecking] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/demo/models`, { signal: controller.signal })
      .then((res) => { if (!res.ok) throw new Error(); return res.json(); })
      .then((body) => setModels(Array.isArray(body.models) ? body.models : []))
      .catch(() => {});
    return () => controller.abort();
  }, []);
  function update(key, value) { setDraft((prev) => ({ ...prev, [key]: value })); setMessage(''); setError(''); }
  function save(event) {
    event.preventDefault();
    setError(''); setMessage('');
    try { savePreferences(draft); setMessage('Preferences saved for this browser.'); }
    catch (err) { setError(err.message); }
  }
  async function checkApi() {
    setChecking(true); setHealth('');
    try {
      const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(5000) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.json();
      if (body.status !== 'ok') throw new Error('Backend reported an unhealthy status');
      setHealth('API is reachable and healthy.');
    } catch { setHealth('API is unavailable. Start the backend and try again.'); }
    finally { setChecking(false); }
  }
  return (
    <div className="space-y-6">
      <div className="page-heading">
        <p className="eyebrow">DTX-AI / Preferences</p><h1>Settings</h1>
        <p>Choose how you review events and connect to your hardware demo. Preferences are saved in this browser.</p>
      </div>
      <form onSubmit={save} className="space-y-5">
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <Card className="space-y-5 p-6">
            <div><h2 className="section-title">Event history</h2><p className="mt-2 text-sm text-muted">Controls for the <Link to="/events" className="underline">Events page</Link>.</p></div>
            <label className="block text-sm">Records to load
              <select className={inputClass} value={draft.eventLimit} onChange={(e) => update('eventLimit', Number(e.target.value))}>
                {[50, 100, 200].map((n) => <option key={n} value={n}>Latest {n} events</option>)}
              </select>
            </label>
            <label className="flex items-center gap-3 text-sm"><input type="checkbox" className="h-4 w-4 accent-black" checked={draft.autoRefresh} onChange={(e) => update('autoRefresh', e.target.checked)} />Refresh events automatically</label>
            <label className="block text-sm">Refresh interval
              <select className={inputClass} disabled={!draft.autoRefresh} value={draft.refreshSeconds} onChange={(e) => update('refreshSeconds', Number(e.target.value))}>
                {[3, 5, 10, 30].map((n) => <option key={n} value={n}>Every {n} seconds</option>)}
              </select>
            </label>
          </Card>
          <Card className="space-y-5 p-6">
            <div><h2 className="section-title">Demo defaults</h2><p className="mt-2 text-sm text-muted">Used when you next open <Link to="/validation" className="underline">AI Validation</Link>. Saving does not start or change a running demo.</p></div>
            <label className="block text-sm">ESP32 address<input type="url" required className={inputClass} value={draft.esp32Url} onChange={(e) => update('esp32Url', e.target.value)} placeholder="http://dtx-esp32.local" /></label>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="block text-sm">Hardware polling (seconds)<input type="number" required min="1" max="60" step="0.5" className={inputClass} value={draft.hardwareInterval} onChange={(e) => update('hardwareInterval', e.target.value)} /></label>
              <label className="block text-sm">Default model
                <select className={inputClass} value={draft.defaultModel} onChange={(e) => update('defaultModel', e.target.value)}>
                  {Array.from(new Set([draft.defaultModel, ...models])).map((model) => <option key={model} value={model}>{model === 'lstm_ae' ? 'LSTM-AE + T5-small' : model}</option>)}
                </select>
              </label>
            </div>
            <p className="text-xs text-dim">The backend reaches the ESP32 over your local network. Use its IP address if dtx-esp32.local does not resolve.</p>
          </Card>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" className="bg-ink px-5 py-2.5 text-sm text-white hover:bg-black">Save preferences</button>
          <button type="button" className="border border-line bg-white px-5 py-2.5 text-sm hover:bg-paper" onClick={() => { setDraft({ ...DEFAULT_PREFERENCES }); setError(''); setMessage('Default values restored in the form. Save to apply them.'); }}>Restore defaults</button>
          {message && <p role="status" className="text-sm text-emerald-800">{message}</p>}
          {error && <p role="alert" className="text-sm text-red-800">{error}</p>}
        </div>
      </form>
      <Card className="p-6">
        <h2 className="section-title">System connection</h2>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
          <div className="min-w-0"><p className="eyebrow">Backend API</p><p className="mt-1 break-all font-mono text-sm">{API_BASE}</p></div>
          <button type="button" disabled={checking} onClick={checkApi} className="border border-line bg-paper px-5 py-2.5 text-sm disabled:opacity-50">{checking ? 'Checking…' : 'Check API'}</button>
        </div>
        {health && <p role="status" className="mt-3 text-sm text-muted">{health}</p>}
      </Card>
    </div>
  );
}
