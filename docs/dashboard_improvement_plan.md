# Dashboard Improvement Plan

## Purpose

This document scopes the next dashboard iteration for DTX-AI without adding the warehouse map / Isaac Sim view yet.

Requested changes:

1. Add asset drilldown chart
2. Add an AI validation page
3. Add operator actions
4. Improve the explanation panel

The goal is to move the dashboard from a live alert viewer into a more defensible operator-facing and demo-ready system.

## Current State Summary

Current dashboard strengths:

- Live event ingestion over WebSocket
- Event table with severity, model, prediction, and replay fields
- Basic explanation panel
- Basic anomaly score trend chart
- Replay metrics already exposed by the backend

Current gaps relevant to the requested work:

- No asset-specific sensor history or drilldown workflow
- No dedicated AI validation screen
- No persistent operator workflow (acknowledge / assign / resolve / escalate)
- Explanation panel is mostly textual and does not expose enough operational context

## Scope Decision

This iteration explicitly skips:

- Isaac Sim map / 3D twin view
- A warehouse overview map
- Full historical analytics beyond the current SQLite-backed event log

This iteration will focus on stronger operator value and stronger AI validation visibility.

## Proposed Feature Set

### 1. Asset Drilldown Chart

Add an asset-focused chart area that shows recent sensor values and anomaly score for the selected asset.

User outcome:

- When an operator selects an event or asset, they can inspect how the asset behaved over recent samples.
- The UI will show trends for vibration, temperature, pressure, and anomaly score instead of only one event row.

Proposed behavior:

- Selection source: clicking an event row selects an asset and a focal event
- Chart shows recent timeline for that asset
- Controls allow switching metric series:
  - vibration
  - temperature
  - pressure
  - anomaly score
- Chart highlights the currently selected event timestamp

Backend impact:

- Add an asset timeline endpoint backed by existing SQLite event rows and `raw_payload`
- No database migration required for sensor history because sensor values are already stored inside `raw_payload`

Proposed API:

- `GET /assets/{asset_id}/timeline?limit=50`

Response shape:

- `asset_id`
- `points[]`
  - `event_id`
  - `timestamp`
  - `vibration`
  - `temperature`
  - `humidity`
  - `pressure`
  - `anomaly_score`
  - `severity`
  - `predicted_label`

Primary files to change:

- `apps/api/api/database.py`
- `apps/api/api/routes/alerts.py` or new `apps/api/api/routes/assets.py`
- `apps/api/main.py`
- `apps/dashboard/src/pages/Dashboard.jsx`
- `apps/dashboard/src/lib/normalizeAlert.js`
- New component: `apps/dashboard/src/components/dashboard/AssetDrilldownChart.jsx`

### 2. AI Validation Page

Add a dedicated page for replay-mode validation so the AI story is visible as a first-class part of the system.

User outcome:

- The team can demonstrate model quality and replay behavior separately from live operations.
- The dashboard will show stronger graduation-project evidence than a single accuracy card.

Proposed behavior:

- New sidebar item: `AI Validation`
- Page will consume `/metrics/live`
- Page sections:
  - replay summary cards
  - per-class ground truth counts
  - per-class predicted counts
  - confusion matrix
  - per-model counts
  - recent replay events table

Backend impact:

- Phase 1 can reuse existing `GET /metrics/live`
- Optional Phase 2: add richer backend metrics if needed

Primary files to change:

- `apps/dashboard/src/App.jsx`
- `apps/dashboard/src/components/layout/Sidebar.jsx`
- New page: `apps/dashboard/src/pages/Validation.jsx`
- New components:
  - `apps/dashboard/src/components/validation/ReplaySummaryCards.jsx`
  - `apps/dashboard/src/components/validation/ConfusionMatrix.jsx`
  - `apps/dashboard/src/components/validation/ClassDistributionCharts.jsx`
  - `apps/dashboard/src/components/validation/ReplayEventTable.jsx`

Potential backend follow-up if current metrics are not sufficient:

- `apps/api/api/live_metrics.py`
- `apps/api/api/routes/metrics.py`

### 3. Operator Actions

Add real operator workflow controls so the dashboard is not passive.

User outcome:

- Operators can acknowledge, assign, escalate, and resolve incidents.
- The state survives refresh and can be shown in the event table and detail panel.

Proposed action set:

- `acknowledge`
- `assign`
- `escalate`
- `resolve`

Proposed behavior:

- Action buttons live in the detail / explanation panel
- Each action creates a persisted action record
- Latest operator state is surfaced in the main event list
- Action history is visible per event

Backend impact:

- Requires persistence support
- Recommended design: add a new SQLite table for event actions instead of overloading the `events` table

Proposed database addition:

- New table: `event_actions`
  - `id`
  - `event_id`
  - `action_type`
  - `note`
  - `assignee`
  - `created_at`

Proposed API:

- `POST /alerts/{event_id}/actions`
- `GET /alerts/{event_id}/actions`

Derived state to expose in alert list responses:

- `operator_status`
- `assigned_to`
- `last_action`
- `last_action_at`

Primary files to change:

- `apps/api/api/database.py`
- `apps/api/api/routes/alerts.py`
- `packages/shared/schemas.py`
- `docs/api_contract.md`
- `apps/dashboard/src/lib/normalizeAlert.js`
- `apps/dashboard/src/components/dashboard/EventTable.jsx`
- `apps/dashboard/src/components/dashboard/ExplanationPanel.jsx`
- New component: `apps/dashboard/src/components/dashboard/OperatorActionBar.jsx`

### 4. Explanation Panel Upgrade

Upgrade the detail panel from a plain text card into an operational incident view.

User outcome:

- The selected event becomes easier to interpret and act on.
- The panel better justifies the model decision.

Proposed sections:

- asset summary
- severity and predicted class
- sensor readings
- comparison against normal / threshold values
- top contributing features
- recommendation
- event metadata
- operator actions
- event action history

Proposed data additions to the frontend view-model:

- `vibration`
- `temperature`
- `humidity`
- `pressure`
- `recommendation`
- `operator_status`
- `assigned_to`
- `action_history`

Implementation note:

- WebSocket `DashboardAlert` already contains raw event sensor fields
- `GET /alerts/` rows contain `raw_payload`, so normalization can extract the same sensor fields for persisted events

Primary files to change:

- `apps/dashboard/src/lib/normalizeAlert.js`
- `apps/dashboard/src/components/dashboard/ExplanationPanel.jsx`
- Possibly split into smaller detail components:
  - `EventSummaryCard.jsx`
  - `SensorReadingsCard.jsx`
  - `FeatureImportanceCard.jsx`
  - `ActionHistoryCard.jsx`

## File-Level Change Plan

### Frontend

Core routing and layout:

- `apps/dashboard/src/App.jsx`
  - add `AI Validation` route
- `apps/dashboard/src/components/layout/Sidebar.jsx`
  - add navigation entry for validation page

Dashboard page:

- `apps/dashboard/src/pages/Dashboard.jsx`
  - manage selected asset state
  - fetch asset timeline when selection changes
  - pass operator-action handlers into the detail panel

Normalization and data shaping:

- `apps/dashboard/src/lib/normalizeAlert.js`
  - extract sensor readings from WebSocket payloads and `raw_payload`
  - include operator-state fields once backend supports them

Existing components to upgrade:

- `apps/dashboard/src/components/dashboard/EventTable.jsx`
  - add operator status column
  - better asset selection behavior
- `apps/dashboard/src/components/dashboard/ExplanationPanel.jsx`
  - restructure into operational detail panel
- `apps/dashboard/src/components/dashboard/TrendChart.jsx`
  - keep as dashboard overview chart, not the asset drilldown chart

New frontend components:

- `apps/dashboard/src/components/dashboard/AssetDrilldownChart.jsx`
- `apps/dashboard/src/components/dashboard/OperatorActionBar.jsx`
- `apps/dashboard/src/components/validation/ReplaySummaryCards.jsx`
- `apps/dashboard/src/components/validation/ConfusionMatrix.jsx`
- `apps/dashboard/src/components/validation/ClassDistributionCharts.jsx`
- `apps/dashboard/src/components/validation/ReplayEventTable.jsx`
- `apps/dashboard/src/pages/Validation.jsx`

### Backend

Routing:

- `apps/api/main.py`
  - register new route module if asset timeline route is added

Persistence:

- `apps/api/api/database.py`
  - add helper for asset timeline query
  - add `event_actions` table creation
  - add insert/fetch helpers for operator actions
  - add join or merge logic so alert list responses include derived operator state

Routes:

- `apps/api/api/routes/alerts.py`
  - add action endpoints
  - optionally enrich `GET /alerts/` rows with operator state
- New optional route module:
  - `apps/api/api/routes/assets.py`
    - asset timeline endpoint

Contracts and docs:

- `packages/shared/schemas.py`
  - add action request / response schemas if backend models are formalized
- `docs/api_contract.md`
  - document new endpoints and response fields

## Implementation Order

Recommended order:

1. Extend backend for asset timeline and operator actions
2. Extend frontend normalization so sensor and operator fields are available everywhere
3. Upgrade explanation panel
4. Add asset drilldown chart
5. Add AI validation page
6. Update docs and usage notes

Reasoning:

- Operator actions and drilldown both depend on stronger backend/frontend data shaping
- Explanation panel becomes the integration point for the new action workflow
- AI validation page is mostly isolated and can be built after the shared data flow is stable

## Testing Plan

Backend:

- Add route tests for:
  - `GET /assets/{asset_id}/timeline`
  - `POST /alerts/{event_id}/actions`
  - `GET /alerts/{event_id}/actions`
- Add database tests for action persistence and timeline extraction

Frontend:

- Manual validation of:
  - event selection
  - timeline rendering
  - action submission and refresh persistence
  - replay page rendering in both empty and populated states

Suggested regression checks:

- synthetic mode still works
- replay mode still updates `/metrics/live`
- dashboard still consumes WebSocket alerts correctly

## Documentation Follow-Up

After implementation, update:

- `README.md`
- `docs/current_usage.md`
- `docs/api_contract.md`

The final documentation should include:

- new dashboard pages
- new action workflow
- asset drilldown behavior
- AI validation page behavior
