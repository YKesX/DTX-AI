---
id: repository-structure
title: Repository Structure
sidebar_position: 3
---

# Repository Structure

The project is a **monorepo** with clear service boundaries. Each top-level folder is an independently runnable service or shared package.

```
DTX-AI/
├── apps/
│   ├── api/                          # FastAPI backend service
│   │   ├── main.py                   # App factory, lifespan, router registration
│   │   ├── requirements.txt          # Pinned to versions verified in .venv
│   │   └── api/
│   │       ├── config.py             # Settings class loaded from .env
│   │       ├── database.py           # All SQLite operations
│   │       ├── live_metrics.py       # In-memory LiveReplayMetrics singleton
│   │       ├── ws_manager.py         # WebSocket ConnectionManager
│   │       └── routes/
│   │           ├── alerts.py         # GET/POST/DELETE alert + action routes
│   │           ├── assets.py         # GET asset drilldown timeline
│   │           ├── demo.py           # /demo/* — demo orchestration (dataset + hardware)
│   │           ├── events.py         # POST /events/ — main ingestion route
│   │           ├── health.py         # GET /health liveness check
│   │           ├── metrics.py        # GET /metrics/live replay metrics
│   │           └── websocket.py      # WS /ws/events endpoint
│   │
│   ├── dashboard/                    # React + Vite frontend
│   │   ├── package.json
│   │   ├── vite.config.js
│   │   └── src/
│   │       ├── App.jsx               # BrowserRouter + Layout + routes
│   │       ├── pages/
│   │       │   ├── Dashboard.jsx     # Main ops page at "/"
│   │       │   └── Validation.jsx    # AI validation page at "/validation"
│   │       ├── components/
│   │       │   ├── dashboard/        # StatusCards, EventTable, ExplanationPanel, …
│   │       │   ├── validation/       # DemoControlPanel, ReplaySummaryCards, ConfusionMatrix, …
│   │       │   ├── layout/           # Sidebar, TopBar
│   │       │   └── ui/               # Badge, Card
│   │       ├── hooks/
│   │       │   └── useWebSocket.js   # WS hook with auto-reconnect
│   │       └── lib/
│   │           └── normalizeAlert.js # Multi-shape alert normaliser
│   │
│   └── sim/                          # NVIDIA Isaac Sim adapter (stub today)
│       └── sim/
│           ├── adapter.py            # notify(TwinUpdate) entry point
│           ├── scene.py              # USD scene helpers (stubbed)
│           └── hooks.py              # Sim lifecycle hooks (stubbed)
│
├── services/
│   └── ai/                           # AI / ML pipeline (imported into API)
│       ├── requirements.txt          # sklearn 1.8, lightgbm 4.6, xgboost 3.2, pytorch-tabnet, …
│       ├── preprocessing.py          # CSV loader + CLASS_NAMES + FEATURES + canonical splits
│       ├── dtx_ai_master_dataset.csv # ~60 Hz telemetry dataset (22 270 rows, 13 fault runs)
│       ├── dtxai_model_training.ipynb # Generated from train_models.py (gen_training_notebook.py)
│       └── ai/
│           ├── pipeline.py           # async run_pipeline(event) entry point
│           ├── detector.py           # Multi-model detector + windowed buffers + rule-based fallback
│           ├── explainer.py          # XAI explanation dispatch
│           ├── xai_explainer.py      # SHAP TreeExplainer + report builder
│           ├── model_loader.py       # Registry-driven model loading + LRU cache
│           ├── lstm_classifier.py    # LSTMAutoencoderClassifier (shared with notebook)
│           └── models/
│               ├── shared/
│               │   ├── model_registry.json
│               │   ├── feature_order.json   # 19 channels, positional
│               │   ├── scaler.pkl           # Fallback StandardScaler (per-family preferred)
│               │   ├── leaderboard.json     # Val/holdout metrics per family + winner
│               │   ├── sanity_baselines.json # ANOVA ranking + trivial-baseline scores
│               │   └── model_best.pth       # Global winner checkpoint (currently CNN)
│               ├── lightgbm/{best_lgbm.pkl, metadata.json}            # unscaled, NaN-native
│               ├── xgboost/{best_xgb.pkl, metadata.json}              # unscaled, NaN-native
│               ├── random_forest/{best_rf.pkl, metadata.json, scaler.pkl}
│               ├── tabnet/{best_tabnet.zip, metadata.json, scaler.pkl}
│               ├── cnn/{best_cnn.pth, metadata.json, scaler.pkl}      # 30-step windowed
│               ├── bilstm/{best_bilstm.pth, metadata.json, scaler.pkl} # 30-step windowed
│               └── lstm_ae/{best_lstmae.pth, metadata.json, scaler.pkl}
│
├── packages/
│   └── shared/
│       ├── pyproject.toml            # dtx-ai-shared
│       └── schemas.py                # All canonical Pydantic v2 schemas
│
├── scripts/
│   ├── setup.sh                      # One-time dev environment setup
│   ├── run_dev.sh                    # Start API + dashboard
│   ├── run_demo.sh                   # Boot stack + replay the leakage-safe demo holdout
│   ├── replay_dataset_demo.py        # Dataset replay CLI
│   ├── hw_demo_bridge.py             # ESP32 → POST /events/ hardware demo bridge
│   ├── gen_training_notebook.py      # Regenerates the training notebook from train_models.py
│   └── train_models.py               # One-shot retrain of every artifact
│
├── HW/                               # PlatformIO project — ESP32 hardware demo node
│   ├── platformio.ini                # ESP32-WROOM-32 build config
│   ├── src/main.cpp                  # DS18B20 + BMP280 firmware, GET /health + /reading
│   ├── include/wifi_config.example.h # Wi-Fi credentials template
│   └── README.md                     # Wiring + flashing guide
│
├── tests/
│   ├── integration/
│   │   └── test_api.py
│   ├── unit/
│   │   ├── test_cnn_replay.py
│   │   ├── test_config_and_ws_manager.py
│   │   ├── test_database_helpers.py
│   │   ├── test_events_helpers.py
│   │   └── test_sim_adapter_and_hooks.py
│   └── smoke/
│       ├── test_ai_pipeline.py
│       ├── test_live_metrics.py
│       ├── test_model_runtime.py
│       ├── test_replay_dataset_demo.py
│       ├── test_run_demo_script.py
│       └── test_schemas.py
│
├── docs/                             # Internal architecture docs (engineering notes)
└── docweb/                           # This documentation site (Docusaurus source)
```

## Key File Reference

| File | Responsibility |
|---|---|
| `apps/api/main.py` | App factory, lifespan hooks, router registration |
| `apps/api/api/database.py` | All SQLite operations (init, insert, fetch, clear) |
| `apps/api/api/live_metrics.py` | Thread-safe in-memory replay metrics singleton |
| `apps/api/api/routes/events.py` | `POST /events/` — main ingestion + AI call + broadcast |
| `apps/api/api/routes/demo.py` | `/demo/*` — spawn/stop the dataset replay or hardware bridge subprocess |
| `apps/dashboard/src/hooks/useWebSocket.js` | WS connection with auto-reconnect |
| `apps/dashboard/src/lib/normalizeAlert.js` | Normalises any backend shape to a flat view-model |
| `services/ai/preprocessing.py` | `CLASS_NAMES`, `FEATURES`, dataset loader, canonical leakage-safe splits (`split_demo_pool_and_holdout`, `split_pool_train_val`) |
| `services/ai/ai/pipeline.py` | `run_pipeline(event)` — async entry point |
| `services/ai/ai/detector.py` | Tree + LSTM-AE+CLS dispatch, rule-based fallback, `_CLASS_MAP` |
| `services/ai/ai/lstm_classifier.py` | `LSTMAutoencoderClassifier` (shared with notebook) |
| `services/ai/ai/model_loader.py` | Registry-driven model loading, in-process cache |
| `services/ai/ai/xai_explainer.py` | SHAP TreeExplainer + explanation text generation |
| `packages/shared/schemas.py` | All canonical Pydantic v2 schemas |
| `scripts/train_models.py` | One-shot retrain of every artifact (7 families, canonical split) |
| `scripts/hw_demo_bridge.py` | Polls the ESP32 node and streams hardware events into `POST /events/` |
| `scripts/gen_training_notebook.py` | Regenerates `dtxai_model_training.ipynb` from `train_models.py` |

## Test Layers

| Test layer | Purpose |
|---|---|
| `tests/unit/` | Fast feedback for helper logic in API, config, database, websocket, and Isaac Sim stub modules |
| `tests/smoke/` | Stable behavior checks for schemas, replay helpers, runtime loading, and fallback AI pipeline flow |
| `tests/integration/` | End-to-end FastAPI route coverage through the in-process AI pipeline and SQLite-backed API behavior |
