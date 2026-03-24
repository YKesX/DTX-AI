import { useState, useEffect, useRef, useCallback } from 'react';
import { mockEvents } from '../lib/mockData';

export function useWebSocket(url = null) {
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState('disconnected');
  const wsRef = useRef(null);
  const retryTimer = useRef(null);
  // Stable ref so the reconnect closure always sees the latest url
  const urlRef = useRef(url);
  useEffect(() => { urlRef.current = url; }, [url]);

  const connect = useCallback(() => {
    if (!urlRef.current) return;

    const ws = new WebSocket(urlRef.current);
    wsRef.current = ws;

    ws.onopen = () => setStatus('connected');

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        setEvents((prev) => [data, ...prev.slice(0, 49)]);
      } catch {
        // ignore malformed frames
      }
    };

    const scheduleRetry = () => {
      setStatus('disconnected');
      retryTimer.current = setTimeout(connect, 3000);
    };

    ws.onclose = scheduleRetry;
    ws.onerror = () => {
      ws.close(); // triggers onclose → scheduleRetry
    };
  }, []); // no deps — uses urlRef internally

  useEffect(() => {
    if (!url) {
      // Mock mode
      setEvents(mockEvents);
      setStatus('connected');
      return;
    }

    connect();

    return () => {
      clearTimeout(retryTimer.current);
      // Prevent the onclose handler from scheduling another retry on unmount
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.close();
      }
    };
  }, [url, connect]);

  return { events, setEvents, status };
}
