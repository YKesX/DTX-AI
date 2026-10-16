import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import Card from '../components/ui/Card';
import EventTable from '../components/dashboard/EventTable';
import SavedEventDetails from '../components/dashboard/SavedEventDetails';
import { normalizeAlerts } from '../lib/normalizeAlert';
import { usePreferences } from '../context/Preferences';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export default function Events() {
  const { preferences } = usePreferences();
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [updatedAt, setUpdatedAt] = useState(null);
  const request = useRef(null);
  const details = useRef(null);
  const updatedAtRef = useRef(null);
  const load = useCallback(async () => {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 10000);
    try {
      const res = await fetch(`${API_BASE}/alerts/?limit=${preferences.eventLimit}`, { signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.json();
      const rows = normalizeAlerts(Array.isArray(body) ? body : (body.alerts ?? []));
      if (controller.signal.aborted) return;
      const now = new Date();
      updatedAtRef.current = now;
      setEvents(rows); setUpdatedAt(now); setError('');
      setSelectedEvent((prev) => prev ? rows.find((row) => row.id === prev.id) ?? null : null);
    } catch (err) {
      if (timedOut || !controller.signal.aborted) setError(`Could not refresh events (${timedOut ? 'request timed out' : err.message}). ${updatedAtRef.current ? 'Showing the last loaded records.' : 'Check the backend connection and retry.'}`);
    } finally {
      clearTimeout(timeout);
      if (request.current === controller) {
        request.current = null;
        setLoading(false);
      }
    }
  }, [preferences.eventLimit]);
  useEffect(() => {
    load();
    const timer = preferences.autoRefresh ? setInterval(load, preferences.refreshSeconds * 1000) : null;
    return () => { clearInterval(timer); request.current?.abort(); request.current = null; };
  }, [load, preferences.autoRefresh, preferences.refreshSeconds]);
  const selectedId = selectedEvent?.id;
  useEffect(() => {
    if (selectedId) details.current?.scrollIntoView({ behavior: 'instant', block: 'start' });
  }, [selectedId]);
  function updateOperatorState(eventId, state) {
    // Discard a history fetch started before this action was saved.
    request.current?.abort(); request.current = null; setLoading(false);
    setEvents((prev) => prev.map((event) => event.event_id === eventId ? { ...event, ...state } : event));
    setSelectedEvent((prev) => prev?.event_id === eventId ? { ...prev, ...state } : prev);
  }
  const assets = new Set(events.map((event) => event.entity_id).filter(Boolean)).size;
  const unresolved = events.filter((event) => event.operator_status !== 'resolved' && ['critical', 'warning', 'high', 'medium'].includes(event.severity)).length;
  return (
    <div className="space-y-6">
      <div className="page-heading"><p className="eyebrow">DTX-AI / Activity archive</p><h1>Events</h1><p>Search recent saved events, inspect explanations, and track operator follow-up.</p></div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[['Loaded records', events.length], ['Assets represented', assets], ['Unresolved alerts', unresolved]].map(([label, value]) => <Card key={label} className="p-5"><p className="eyebrow">{label}</p><p className="stat-value mt-3">{value}</p></Card>)}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-muted"><p>Latest {preferences.eventLimit} saved records · {preferences.autoRefresh ? `Refreshes every ${preferences.refreshSeconds}s` : 'Manual refresh'}</p><p className="text-xs text-dim">{updatedAt ? `Last updated ${updatedAt.toLocaleTimeString()}` : 'No records loaded yet.'} <Link to="/settings" className="underline">Change preferences</Link></p></div>
        <button type="button" disabled={loading} onClick={load} className="border border-line bg-white px-5 py-2 text-sm disabled:opacity-50">{loading ? 'Refreshing…' : 'Refresh events'}</button>
      </div>
      {error && <p role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
      <EventTable title="Event history" showDates events={events} onSelectEvent={setSelectedEvent} selectedId={selectedEvent?.id} />
      {selectedEvent && <section ref={details} className="scroll-mt-24 space-y-4" aria-label="Selected event details">
        <div className="flex items-center justify-between gap-3"><h2 className="section-title">Event details</h2><button type="button" onClick={() => setSelectedEvent(null)} className="border border-line bg-white px-4 py-2 text-xs">Close details</button></div>
        <SavedEventDetails key={selectedEvent.id} event={selectedEvent} onUpdate={updateOperatorState} />
      </section>}
    </div>
  );
}
