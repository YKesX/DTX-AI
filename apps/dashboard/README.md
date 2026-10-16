# apps/dashboard — React + Vite Web Dashboard

Release: **v3.0 Final** (package version `3.0.0`).

## Responsibilities
- Display live alerts and explanations via WebSocket
- Show recent event history
- Present XAI feature attribution as a visual bar chart

## Running locally

```bash
cd apps/dashboard
npm install
npm run dev
```

Open http://localhost:5173

## Environment variables

```bash
cp .env.example .env.local
```

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | REST API base URL |
| `VITE_WS_URL` | `ws://localhost:8000/ws/events` | WebSocket endpoint |

## Console pages

- **Dashboard**: live events, explanations, operator actions, and asset trends.
- **Events**: latest 50–200 persisted events, full dates, search/severity/source/
  operator filters, event inspection, and action history. The API currently
  returns the most recent 200 events at most; this is not the complete archive.
- **AI Validation**: dataset replay and ESP32 demo controls.
- **Settings**: browser-local event refresh preferences and defaults for the
  demo model, ESP32 address, and hardware polling interval. Save preferences
  before navigating away. Demo defaults apply the next time AI Validation is
  opened and do not change an already running demo. Check API tests backend
  reachability; it does not test the ESP32 connection.
