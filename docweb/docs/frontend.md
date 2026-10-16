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
layout/TopBar.jsx     Fixed top — release console title + live clock
```

**UI primitives:**
```
ui/Badge.jsx    Severity badge (info / warning / critical)
ui/Card.jsx     Paper-style card container
```

---

## State Management

Page state uses React hooks. `PreferencesProvider` shares validated browser-local settings:

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

**`useWebSocket.js`** auto-reconnects with a 3-second delay on disconnect. The header displays the clock; it has no connection badge. No mock events are injected.

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

### Events (`/events`)
Loads the latest 50, 100, or 200 saved records, with configurable polling,
full dates, search and severity/source/operator filters. Selection opens
explanations and operator actions. Failed refreshes retain the last loaded
records with an error message; failed actions retain the unsaved note.

### Settings (`/settings`)
Saves event history limits, automatic refresh, model defaults, ESP32 address,
and hardware polling interval in local storage. Defaults apply when the demo
page is next opened; saving does not alter a running demo. The API health
button checks backend reachability.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend REST base URL |
| `VITE_WS_URL` | `ws://localhost:8000/ws/events` | Backend WebSocket URL |
