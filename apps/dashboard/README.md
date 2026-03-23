# apps/dashboard — React + Vite Web Dashboard

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
