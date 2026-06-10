# DTX-AI — Smart Warehouse Anomaly Detection + Explainable AI

DTX-AI is a university capstone project for intelligent warehouse monitoring and decision support.

## Whole project scope

DTX-AI is a full-stack AI system, not only a dashboard or notebook:

- anomaly detection on warehouse/equipment telemetry
- explainable AI (XAI) for operator-facing justification
- FastAPI backend for ingestion, inference, persistence, broadcast
- live dashboard for operators
- dataset replay validation against a leakage-safe holdout
- hardware/sensor integration (ESP32 — see [HW/](HW) and [docs/hardware_demo.md](docs/hardware_demo.md))
- later digital twin integration with NVIDIA Isaac Sim

## Current project stage (truthful scope)

Current critical path is the software demo path **without Isaac Sim**:

- real API ingestion (`POST /events/`)
- runtime model inference (active model selection across 7 model families)
- explanation generation
- websocket broadcast + dashboard rendering
- operator workflow actions (acknowledge / assign / escalate / resolve)
- asset drilldown history for selected warehouse assets
- dataset replay validation mode **and** IRL hardware demo mode (ESP32)

The dataset replay mode is used to prove that trained models are driving outputs by showing ground truth vs prediction and live running metrics. It replays the **leakage-safe demo holdout**: the last 20% of every contiguous fault run, separated from training data by a 60-row purge gap (the old row-level stratified split leaked near-duplicate ~60 Hz frames into the demo).

## Current architecture flow

```
[dataset replay OR ESP32 hardware bridge]
              │
              ▼
         POST /events/
       (FastAPI apps/api)
              │
              ▼
     services/ai runtime pipeline
     - detector (real model path)
     - explainer (SHAP/feature-importance path)
              │
              ├── SQLite persistence (events)
              ├── WebSocket broadcast (/ws/events)
              └── live in-memory replay metrics (/metrics/live)
                        │
                        ▼
                   React dashboard
```

## Runtime model support

Artifacts: [services/ai/ai/models](services/ai/ai/models) — 7 model families, all retrained on the leakage-safe canonical split (see `shared/leaderboard.json` for current metrics):

- `random_forest`
- `lightgbm`
- `xgboost`
- `tabnet`
- `cnn` (30-step windowed)
- `bilstm` (30-step windowed)
- `lstm_ae`

Selection precedence:

1. event metadata `active_model` (replay mode)
2. `DTX_ACTIVE_MODEL`
3. registry `active_model` in [services/ai/ai/models/shared/model_registry.json](services/ai/ai/models/shared/model_registry.json)

### Strict replay mode

Strict replay can be enabled per replay run (`--strict`) or via `DTX_REPLAY_STRICT=1`.

In strict replay mode:

- selected model must load successfully
- no silent fallback to stub detector
- tree explanation failure is explicit and degrades to model `feature_importances_`
- LSTM-AE is rejected in strict mode when `default_threshold` is missing

## Demo modes

### Dataset replay validation demo

```bash
bash scripts/run_demo.sh --model random_forest --split holdout --count 100 --delay 0.5 --strict-replay
```

Direct replay command:

```bash
python scripts/replay_dataset_demo.py --model random_forest --split episode_holdout --limit 100 --delay 0.5 --strict
```

Replay splits:

- `holdout` (default): the leakage-safe per-episode temporal demo holdout, shuffled for display
- `episode_holdout`: grouped holdout for episode/run validation
- `temporal`: chronological tail for drift checks
- `all`: whole dataset, including training rows

Replay events include provenance in `event.metadata`:

- `source=dataset_replay`
- `dataset`, `row_id`, `split`, `replay_index`
- `ground_truth_label`, `ground_truth_name`
- `active_model`, `runtime_model`
- `predicted_label`, `prediction_correct`

### Dashboard demo selector

The AI Validation page (`/validation`) includes a **Demo Control** panel that starts/stops either demo from the browser — pick Dataset demo or IRL demo (ESP32), choose the model/split/count, and watch the demo log. It drives the backend `/demo` routes (`GET /demo/models`, `GET /demo/status`, `POST /demo/start`, `POST /demo/stop`).

### IRL hardware demo (ESP32)

[HW/](HW) is a PlatformIO project for an ESP32-WROOM-32 with a DS18B20 temperature probe and a BMP280 pressure sensor. `scripts/hw_demo_bridge.py` polls the node and streams live readings through the same `POST /events/` pipeline (`metadata.source=hardware_demo`). Full guide: [docs/hardware_demo.md](docs/hardware_demo.md).

## Setup and run

```bash
bash scripts/setup.sh
bash scripts/run_dev.sh
```

Runtime dependency note:

- `lightgbm` and `xgboost` are included in [services/ai/requirements.txt](services/ai/requirements.txt).
- On macOS, these model runtimes require OpenMP (`libomp.dylib`) to load successfully in strict replay mode.

URLs:

- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:5173
- Live replay metrics: http://localhost:8000/metrics/live

Dashboard convenience:

- The event table includes a **Clear Logs** button that clears dashboard rows, deletes persisted API event logs, and resets live replay metrics for fresh percentage tracking.
- The operations dashboard includes an asset drilldown chart and operator-action panel for the selected alert.
- The `/validation` page surfaces replay metrics, class distributions, confusion matrix, and recent replay rows for model-review demos.

## Current limitations

- Isaac Sim intentionally excluded from this current validation path
- the training notebook is generated from `scripts/train_models.py` via `scripts/gen_training_notebook.py` — regenerate it, do not hand-edit
- LSTM-AE strict replay requires a configured numeric threshold (`default_threshold`)
- all model metrics now come from the same canonical split (`shared/leaderboard.json`), but the dataset is still highly separable — near-perfect scores reflect the data, not model strength (see [docs/isaac_sim_integration.md](docs/isaac_sim_integration.md))

## Documentation

- API contract: [docs/api_contract.md](docs/api_contract.md)
- Architecture: [docs/architecture.md](docs/architecture.md)
- Current usage guide: [docs/current_usage.md](docs/current_usage.md)
