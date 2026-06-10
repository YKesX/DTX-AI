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

- `DTX_ACTIVE_MODEL` (optional): `random_forest|lightgbm|xgboost|tabnet|cnn|bilstm|lstm_ae`
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

- `holdout` (default): the leakage-safe demo holdout — the last 20% of every contiguous fault run, separated from training data by a 60-row purge gap (shuffled for a readable dashboard demo)
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

### Demo control from the dashboard

Both demos can also be started from the dashboard: the AI Validation page has a **Demo Control** panel that picks the mode (Dataset demo vs IRL demo/ESP32), model, split, and count, starts/stops the run, and tails the demo log. It drives the backend `/demo` routes:

- `GET /demo/models` — enabled model keys
- `GET /demo/status` — running state, params, log tail
- `POST /demo/start` — spawn `scripts/replay_dataset_demo.py` or `scripts/hw_demo_bridge.py` (409 if already running)
- `POST /demo/stop` — terminate the running demo

### IRL hardware demo (ESP32)

`scripts/hw_demo_bridge.py` polls the ESP32 node (`HW/`, DS18B20 + BMP280), maps the two real channels onto the dataset vocabulary, synthesizes the rest from nominal training-pool stats, and POSTs into `/events/` with `metadata.source=hardware_demo`. See [docs/hardware_demo.md](hardware_demo.md) for wiring, flashing, and usage.

## 5) Model selection and strict behavior

- Standard mode: loader may fallback to another enabled model when selected one fails.
- Strict replay mode: selected model must load, otherwise request fails loudly.
- Strict replay does not silently fallback to stub.
- LSTM-AE strict replay requires numeric `default_threshold` in metadata.

## 6) Artifact locations

- Registry/shared:
  - [services/ai/ai/models/shared/model_registry.json](../services/ai/ai/models/shared/model_registry.json)
  - [services/ai/ai/models/shared/feature_order.json](../services/ai/ai/models/shared/feature_order.json)
  - [services/ai/ai/models/shared/scaler.pkl](../services/ai/ai/models/shared/scaler.pkl) (fallback — each scaled family ships its own `scaler.pkl`)
  - [services/ai/ai/models/shared/leaderboard.json](../services/ai/ai/models/shared/leaderboard.json) (val/holdout metrics + winner)
  - [services/ai/ai/models/shared/sanity_baselines.json](../services/ai/ai/models/shared/sanity_baselines.json)
  - `services/ai/ai/models/shared/model_best.pth` (global winner checkpoint, currently CNN)
- Model families:
  - [services/ai/ai/models/lightgbm](../services/ai/ai/models/lightgbm)
  - [services/ai/ai/models/random_forest](../services/ai/ai/models/random_forest)
  - [services/ai/ai/models/xgboost](../services/ai/ai/models/xgboost)
  - [services/ai/ai/models/tabnet](../services/ai/ai/models/tabnet)
  - [services/ai/ai/models/cnn](../services/ai/ai/models/cnn)
  - [services/ai/ai/models/bilstm](../services/ai/ai/models/bilstm)
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

Current local baseline: `56 passed`.

## 11) Later stages (not current path)

- Isaac Sim live integration
- harder, noisier simulation data (the current dataset is still highly separable — see [docs/isaac_sim_integration.md](isaac_sim_integration.md))

Hardware sensor ingestion is now implemented — see the IRL hardware demo above and [docs/hardware_demo.md](hardware_demo.md). All 7 model families are benchmarked on the same canonical split in `services/ai/ai/models/shared/leaderboard.json`.
