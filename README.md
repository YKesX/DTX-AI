# DTX-AI — Smart Warehouse Anomaly Detection + Explainable AI

DTX-AI is a university capstone project focused on smart warehouse monitoring with anomaly detection, explainable AI (XAI), a live backend API, and a live web dashboard.

## Whole project scope

- smart warehouse anomaly detection
- explainable AI
- live backend API
- live web dashboard
- reproducible demo scenario generation
- **later** digital twin integration with NVIDIA Isaac Sim
- **later** hardware integration with ESP32 (or similar real sensor streams)

## Current project stage

The current stage is the **software demo core**, not the final full system.

Current end-to-end path intentionally excludes Isaac Sim and focuses on:

1. environment setup
2. backend startup
3. dashboard startup
4. scenario generation / event seeding
5. API ingestion
6. runtime inference with active model selection
7. explanation generation
8. API persistence + websocket broadcast
9. dashboard rendering (score, severity, explanation, top features)

## Current architecture flow

```
[scenario generator / seeded events]
             │
             ▼
        POST /events/
        (FastAPI backend)
             │
             ▼
    services/ai runtime pipeline
    - detector (model registry + fallback)
    - explainer (tree XAI + fallback)
             │
             ├── SQLite persistence
             └── WS broadcast (/ws/events)
                          │
                          ▼
                    React dashboard
```

## Current runtime model support

Runtime artifacts are under `services/ai/ai/models/` and selected by:

- `services/ai/ai/models/shared/model_registry.json` (`active_model`)
- optional runtime override: `DTX_ACTIVE_MODEL=<model_key>`

Supported families:

- LightGBM (`lightgbm`)
- RandomForest (`random_forest`)
- XGBoost (`xgboost`)
- LSTM-AE (`lstm_ae`)

Behavior notes:

- tree models use shared scaler + canonical feature order and produce explanation payloads compatible with API/dashboard normalization
- tree XAI uses `services/ai/xai_explainer.py` when possible, with graceful fallback if unavailable
- LSTM-AE loading is explicit; threshold is used only when defined in metadata
- if selected model is incomplete/unloadable, runtime falls back cleanly so demo flow remains usable

## Quick start (current demo path)

### 1) Setup

```bash
cd DTX-AI
bash scripts/setup.sh
```

### 2) Run one-command demo

```bash
bash scripts/run_demo.sh --scenario mixed --count 10 --delay 0.8
```

Example options:

```bash
bash scripts/run_demo.sh --setup --model lightgbm --scenario combined --count 12 --delay 0.6
bash scripts/run_demo.sh --model random_forest --scenario gradual_drift
bash scripts/run_demo.sh --no-seed
```

### 3) URLs

- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:5173

## Supported demo scenarios

- `normal`
- `bearing_fault`
- `overheating`
- `combined`
- `mixed`
- `gradual_drift`
- `intermittent_spike`

You can run scenario generation directly:

```bash
python scripts/seed_demo_events.py --scenario mixed --count 10 --delay 0.8
```

## Model artifacts and registry files

Shared:

- `services/ai/ai/models/shared/model_registry.json`
- `services/ai/ai/models/shared/feature_order.json`
- `services/ai/ai/models/shared/scaler.pkl`

Per model family:

- `services/ai/ai/models/lightgbm/`
- `services/ai/ai/models/random_forest/`
- `services/ai/ai/models/xgboost/`
- `services/ai/ai/models/lstm_ae/`

Metadata files define model family assumptions, class mapping, and runtime notes.

## Current limitations (important)

- Isaac Sim is excluded from this current software demo path
- training notebooks are separate and not part of runtime integration
- LSTM-AE may require explicit threshold configuration (`default_threshold`) before full anomaly-threshold behavior is active
- model metrics come from different data splits across artifacts; avoid overselling direct comparability

## Additional docs

- API contract: `docs/api_contract.md`
- Architecture: `docs/architecture.md`
- Current usage details: `docs/current_usage.md`
