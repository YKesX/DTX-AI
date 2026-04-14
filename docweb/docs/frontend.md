---
id: frontend
title: Frontend Architecture
sidebar_position: 7
---

# Frontend Architecture

**React 18 + Vite + TailwindCSS** — operator-facing real-time control panel.

---

## Component Hierarchy

```
App.jsx (BrowserRouter + Layout)
├── / → Dashboard.jsx
│   ├── StatusCards.jsx         6-card summary bar
│   ├── EventTable.jsx          Filterable event stream (Operator/Developer views)
│   ├── ExplanationPanel.jsx    SHAP feature bars + operator actions
│   │   └── OperatorActionBar.jsx
│   ├── TrendChart.jsx          Anomaly score over time (last 20 events)
│   └── AssetDrilldownChart.jsx Per-asset sensor history
│
└── /validation → Validation.jsx
    ├── ReplaySummaryCards.jsx  Total / Correct / Accuracy
    ├── ClassDistributionCharts.jsx  GT vs Predicted bar charts
    ├── ConfusionMatrix.jsx     Dynamic confusion matrix table
    └── ReplayEventTable.jsx    Recent replay events with GT/predicted comparison
```

**Shared layout:**
```
layout/Sidebar.jsx    Fixed left nav with NavLink routes
layout/TopBar.jsx     Fixed top — WS status indicator + live clock
```

**UI primitives:**
```
ui/Badge.jsx    Severity badge (info / warning / critical)
ui/Card.jsx     Glass-morphism card container
```

---

## State Management

No global state library. State lives locally in page components via React hooks:

| Hook | Usage |
|---|---|
| `useState` | Event list, selected event, filter values, action state |
| `useEffect` | REST fetches on mount, polling intervals (2s/4s), WS setup |
| `useWebSocket` | WS lifecycle, message dispatch, auto-reconnect |

---

## Real-Time Data Flow

```
API WebSocket ──► useWebSocket.js
                      │
                      ▼
               normalizeAlert.js   (any backend shape → flat view-model)
                      │
                      ▼
               events[] state      (capped at 50 in-memory)
                      │
                      ▼
               EventTable + ExplanationPanel + TrendChart
```

**`normalizeAlert.js`** handles multiple backend response shapes (live WebSocket push vs historical REST load) and normalizes them to a consistent flat view-model consumed by all components.

**`useWebSocket.js`** auto-reconnects with a 3-second delay on disconnect. WS connection status is shown in the `TopBar`.

---

## Pages

### Dashboard (`/`)
Main operations page. Connects to the WebSocket on mount and loads the last 50 historical alerts from `GET /alerts/`. Every 2 seconds, polls `GET /metrics/live` to update the status cards.

Selecting an event row:
1. `GET /assets/{asset_id}/timeline` → populates `AssetDrilldownChart`
2. `GET /alerts/{event_id}/actions` → populates `ExplanationPanel` action history
3. `ExplanationPanel` shows SHAP feature bar chart, sensor readings, operator state

### Validation (`/validation`)
AI validation page. Polls `GET /metrics/live` every 4 seconds and `GET /alerts/?limit=100` to populate the replay event table. Shows running accuracy, confusion matrix, and per-class distributions.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend REST base URL |
| `VITE_WS_URL` | `ws://localhost:8000/ws/events` | Backend WebSocket URL |
