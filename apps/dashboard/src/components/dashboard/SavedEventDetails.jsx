import { useEffect, useRef, useState } from 'react';
import ExplanationPanel from './ExplanationPanel';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

// Mounted with an event key so late responses cannot update a different selection.
export default function SavedEventDetails({ event, onUpdate }) {
  const [actions, setActions] = useState([]);
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const actionController = useRef(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const request = new AbortController();
    if (!event.event_id) return () => request.abort();
    setLoading(true); setError('');
    fetch(`${API_BASE}/alerts/${encodeURIComponent(event.event_id)}/actions`, { signal: request.signal })
      .then((res) => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.json(); })
      .then((body) => { if (!request.signal.aborted) { setActions(body.actions ?? []); setState(body.state ?? null); } })
      .catch((err) => { if (!request.signal.aborted) setError(`Could not load action history: ${err.message}`); })
      .finally(() => { if (!request.signal.aborted) setLoading(false); });
    return () => { request.abort(); actionController.current?.abort(); };
  }, [event.event_id, retry]);
  async function submit(actionType, { assignee, note }) {
    const request = new AbortController();
    actionController.current = request;
    setSaving(true); setError('');
    try {
      const res = await fetch(`${API_BASE}/alerts/${encodeURIComponent(event.event_id)}/actions`, {
        method: 'POST', signal: request.signal, headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action_type: actionType, assignee, note }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.json();
      if (request.signal.aborted) return false;
      setState(body.state ?? null);
      if (body.action) setActions((prev) => [body.action, ...prev]);
      onUpdate(event.event_id, body.state ?? {});
      return true;
    } catch (err) {
      if (!request.signal.aborted) setError(`Action was not saved. ${err.message}. Please retry.`);
      return false;
    } finally { if (!request.signal.aborted) setSaving(false); }
  }
  return (
    <div className="space-y-3">
      {loading && <p role="status" className="text-sm text-muted">Loading operator history…</p>}
      {error && <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}<button type="button" onClick={() => setRetry((n) => n + 1)} className="ml-3 underline">Reload history</button></div>}
      <ExplanationPanel event={event} actionHistory={actions} actionState={state} actionLoading={loading || saving} onSubmitAction={submit} />
    </div>
  );
}
