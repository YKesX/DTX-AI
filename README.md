# DTX-AI — Smart Warehouse Anomaly Detection + Explainable AI

DTX-AI is a university capstone project for intelligent warehouse monitoring and decision support.

## Whole project scope

DTX-AI is a full-stack AI system, not only a dashboard or notebook:

- anomaly detection on warehouse/equipment telemetry
- explainable AI (XAI) for operator-facing justification
- FastAPI backend for ingestion, inference, persistence, broadcast
- live dashboard for operators
- synthetic scenario generation
- later digital twin integration with NVIDIA Isaac Sim
- later hardware/sensor integration (ESP32 or equivalent)

## Current project stage (truthful scope)

Current critical path is the software demo path **without Isaac Sim**:

- real API ingestion (`POST /events/`)
- runtime model inference (active model selection)
- explanation generation
- websocket broadcast + dashboard rendering
- synthetic demo mode **and** dataset replay validation mode

The dataset replay mode is used to prove that trained models are driving outputs by showing ground truth vs prediction and live running metrics.

## Current architecture flow

```
[synthetic generator OR dataset replay]
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

Artifacts: [services/ai/ai/models](services/ai/ai/models)

- `lightgbm`
- `random_forest`
- `xgboost`
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

### A) Synthetic scenario demo

```bash
bash scripts/run_demo.sh --mode synthetic --scenario mixed --count 10 --delay 0.8
```

### B) Dataset replay validation demo (held-out chronological rows)

```bash
bash scripts/run_demo.sh --mode replay --model random_forest --split test --count 100 --delay 0.5 --strict-replay
```

Direct replay command:

```bash
python scripts/replay_dataset_demo.py --model random_forest --split test --limit 100 --delay 0.5 --source ziya --strict
```

Replay events include provenance in `event.metadata`:

- `source=dataset_replay`
- `dataset`, `row_id`, `split`, `replay_index`
- `ground_truth_label`, `ground_truth_name`
- `active_model`, `runtime_model`
- `predicted_label`, `prediction_correct`

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

## Current limitations

- Isaac Sim intentionally excluded from this current validation path
- notebook training files are separate from runtime integration and were not modified
- LSTM-AE strict replay requires a configured numeric threshold (`default_threshold`)
- saved model metrics come from different historical split setups and should not be oversold as directly comparable

## Documentation

- API contract: [docs/api_contract.md](docs/api_contract.md)
- Architecture: [docs/architecture.md](docs/architecture.md)
- Current usage guide: [docs/current_usage.md](docs/current_usage.md)
