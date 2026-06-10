# Current Usage Guide (Current Software Stage)

This guide covers the current end-to-end software path for DTX-AI.
Isaac Sim is intentionally excluded from this stage.

## 1) Setup

```bash
cd DTX-AI
bash scripts/setup.sh
```

This creates `.venv`, installs API/AI dependencies, installs dashboard dependencies, and copies `.env` files.

## 2) Environment variables

Common:

- `DTX_ACTIVE_MODEL` (optional): `lightgbm|random_forest|xgboost|lstm_ae`
- `DTX_REPLAY_STRICT` (optional): `1` to force strict real-model replay behavior

Backend:

- [apps/api/.env.example](apps/api/.env.example)

Dashboard:

- [apps/dashboard/.env.example](apps/dashboard/.env.example)

## 3) Start services

```bash
bash scripts/run_dev.sh
```

- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:5173
- Live metrics: http://localhost:8000/metrics/live

Dashboard pages:

- `/` — operations dashboard with live event flow, explanation panel, operator actions, and asset drilldown chart
- `/validation` — replay validation page with summary cards, class distributions, confusion matrix, and recent replay rows

## 4) Dataset replay validation mode

Replay dataset rows through the same `POST /events/` path:

```bash
bash scripts/run_demo.sh --model random_forest --split holdout --count 100 --delay 0.5 --strict-replay
```

Direct replay script:

```bash
python scripts/replay_dataset_demo.py --model random_forest --split episode_holdout --limit 100 --delay 0.5 --strict
```

Replay splits:

- `holdout`: shuffled stratified demo holdout for a readable dashboard demo
- `episode_holdout`: grouped episode/run holdout for honest validation
- `temporal`: chronological tail for drift checks
- `all`: whole dataset, including rows used in training

Replay metadata sent with each event:

- `source=dataset_replay`
- `dataset`, `row_id`, `split`, `replay_index`
- `ground_truth_label`, `ground_truth_name`
- `active_model`, `replay_strict`

API enriches output metadata with:

- `runtime_model`, `runtime_model_family`
- `predicted_label`, `prediction_correct`, `predicted_score`

## 5) Model selection and strict behavior

- Standard mode: loader may fallback to another enabled model when selected one fails.
- Strict replay mode: selected model must load, otherwise request fails loudly.
- Strict replay does not silently fallback to stub.
- LSTM-AE strict replay requires numeric `default_threshold` in metadata.

## 6) Artifact locations

- Registry/shared:
  - [services/ai/ai/models/shared/model_registry.json](../services/ai/ai/models/shared/model_registry.json)
  - [services/ai/ai/models/shared/feature_order.json](../services/ai/ai/models/shared/feature_order.json)
  - [services/ai/ai/models/shared/scaler.pkl](../services/ai/ai/models/shared/scaler.pkl)
- Model families:
  - [services/ai/ai/models/lightgbm](../services/ai/ai/models/lightgbm)
  - [services/ai/ai/models/random_forest](../services/ai/ai/models/random_forest)
  - [services/ai/ai/models/xgboost](../services/ai/ai/models/xgboost)
  - [services/ai/ai/models/lstm_ae](../services/ai/ai/models/lstm_ae)

## 7) Interpreting dashboard replay results

In replay mode, table/panel now show:

- data source
- active/runtime model
- ground truth label
- predicted label
- correctness (`prediction_correct`)
- anomaly score and explanation/top features
- operator workflow state (`new`, `acknowledged`, `assigned`, `escalated`, `resolved`)
- running replay accuracy cards from `/metrics/live`

## 8) Operator workflow

The operations dashboard now supports per-alert operator actions:

- acknowledge
- assign
- escalate
- resolve

Backend endpoints:

- `POST /alerts/{event_id}/actions`
- `GET /alerts/{event_id}/actions`

The selected-event panel uses these endpoints to show current operator status, assignee, and action history.

## 9) Asset drilldown

Selecting an event now triggers an asset-specific history fetch:

- `GET /assets/{asset_id}/timeline?limit=50`

This powers the drilldown chart for:

- vibration
- temperature
- pressure
- anomaly score

## 10) Test matrix

Current automated suite is organized into three layers:

- `tests/unit/`
  - event-route helpers (`_normalize_gt_label`, `_build_twin_update`, label mapping)
  - database helpers (`_parse_payload`, operator-state derivation, timeline extraction, clear/reset flow)
  - config parsing and `ConnectionManager`
  - Isaac Sim adapter / scene / lifecycle stub behavior
- `tests/smoke/`
  - schemas
  - replay helper script behavior
  - model loader and strict replay selection
  - rule-based detector / explainer / async pipeline path
- `tests/integration/`
  - FastAPI `/health`, `/events/`, `/alerts/`, `/metrics/live`, `/assets/{id}/timeline`
  - operator actions and derived state

Recommended commands:

```bash
PYTHONPATH="packages:services:services/ai:apps/api:apps/sim" .venv/bin/pytest -q
PYTHONPATH="packages:services:services/ai:apps/api:apps/sim" .venv/bin/pytest -q tests/unit
.venv/bin/pytest -q tests/smoke
.venv/bin/pytest -q tests/integration
```

Current local baseline after the new unit-test additions: `54 passed`.

## 11) Later stages (not current path)

- Isaac Sim live integration
- hardware sensor ingestion
- unified offline benchmark protocol across model families
