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

## 4) Synthetic demo mode

One-command path:

```bash
bash scripts/run_demo.sh --mode synthetic --scenario mixed --count 10 --delay 0.8
```

Scenarios: `normal`, `bearing_fault`, `overheating`, `combined`, `mixed`, `gradual_drift`, `intermittent_spike`

Direct generator:

```bash
python scripts/seed_demo_events.py --scenario mixed --count 10 --delay 0.8
```

## 5) Dataset replay validation mode

Replay held-out chronological rows through the same `POST /events/` path:

```bash
bash scripts/run_demo.sh --mode replay --model random_forest --split test --count 100 --delay 0.5 --strict-replay
```

Direct replay script:

```bash
python scripts/replay_dataset_demo.py --model random_forest --split test --limit 100 --delay 0.5 --source ziya --strict
```

Replay metadata sent with each event:

- `source=dataset_replay`
- `dataset`, `row_id`, `split`, `replay_index`
- `ground_truth_label`, `ground_truth_name`
- `active_model`, `replay_strict`

API enriches output metadata with:

- `runtime_model`, `runtime_model_family`
- `predicted_label`, `prediction_correct`, `predicted_score`

## 6) Model selection and strict behavior

- Standard mode: loader may fallback to another enabled model when selected one fails.
- Strict replay mode: selected model must load, otherwise request fails loudly.
- Strict replay does not silently fallback to stub.
- LSTM-AE strict replay requires numeric `default_threshold` in metadata.

## 7) Artifact locations

- Registry/shared:
  - [services/ai/ai/models/shared/model_registry.json](services/ai/ai/models/shared/model_registry.json)
  - [services/ai/ai/models/shared/feature_order.json](services/ai/ai/models/shared/feature_order.json)
  - [services/ai/ai/models/shared/scaler.pkl](services/ai/ai/models/shared/scaler.pkl)
- Model families:
  - [services/ai/ai/models/lightgbm](services/ai/ai/models/lightgbm)
  - [services/ai/ai/models/random_forest](services/ai/ai/models/random_forest)
  - [services/ai/ai/models/xgboost](services/ai/ai/models/xgboost)
  - [services/ai/ai/models/lstm_ae](services/ai/ai/models/lstm_ae)

## 8) Interpreting dashboard replay results

In replay mode, table/panel now show:

- data source
- active/runtime model
- ground truth label
- predicted label
- correctness (`prediction_correct`)
- anomaly score and explanation/top features
- running replay accuracy cards from `/metrics/live`

## 9) Later stages (not current path)

- Isaac Sim live integration
- hardware sensor ingestion
- unified offline benchmark protocol across model families
