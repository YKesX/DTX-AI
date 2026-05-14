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
│   │       │   ├── validation/       # ReplaySummaryCards, ConfusionMatrix, …
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
│       ├── requirements.txt          # sklearn 1.8, lightgbm 4.6, xgboost 3.2, …
│       ├── preprocessing.py          # CSV loader + CLASS_NAMES + FEATURES
│       ├── xai_explainer.py          # SHAP TreeExplainer + report builder
│       ├── dtx_ai_master_dataset.csv # Isaac-Sim-style telemetry dataset (10 800 rows)
│       ├── dtxai_model_training.ipynb # Full training notebook (cells 2–10)
│       └── ai/
│           ├── pipeline.py           # async run_pipeline(event) entry point
│           ├── detector.py           # Multi-model detector + rule-based fallback
│           ├── explainer.py          # XAI explanation dispatch
│           ├── model_loader.py       # Registry-driven model loading + LRU cache
│           ├── lstm_classifier.py    # LSTMAutoencoderClassifier (shared with notebook)
│           └── models/
│               ├── shared/
│               │   ├── model_registry.json
│               │   ├── feature_order.json   # 19 channels, positional
│               │   ├── scaler.pkl           # StandardScaler fit on train split
│               │   └── model_best.pkl       # Overall-best non-LSTM, retrained on train+val
│               ├── lightgbm/{best_lgbm.pkl, metadata.json}
│               ├── random_forest/{best_rf.pkl, metadata.json}
│               ├── xgboost/{best_xgb.pkl, metadata.json}
│               └── lstm_ae/{best_lstmae.pth, metadata.json}
│
├── packages/
│   └── shared/
│       ├── pyproject.toml            # dtx-ai-shared
│       └── schemas.py                # All canonical Pydantic v2 schemas
│
├── scripts/
│   ├── setup.sh                      # One-time dev environment setup
│   ├── run_dev.sh                    # Start API + dashboard
│   ├── run_demo.sh                   # Boot stack + replay the held-out dataset tail
│   ├── replay_dataset_demo.py        # Dataset replay CLI
│   └── train_models.py               # One-shot retrain of every artifact
│
├── tests/
│   ├── integration/test_api.py
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
| `apps/dashboard/src/hooks/useWebSocket.js` | WS connection with auto-reconnect |
| `apps/dashboard/src/lib/normalizeAlert.js` | Normalises any backend shape to a flat view-model |
| `services/ai/preprocessing.py` | `CLASS_NAMES`, `FEATURES`, dataset loader |
| `services/ai/ai/pipeline.py` | `run_pipeline(event)` — async entry point |
| `services/ai/ai/detector.py` | Tree + LSTM-AE+CLS dispatch, rule-based fallback, `_CLASS_MAP` |
| `services/ai/ai/lstm_classifier.py` | `LSTMAutoencoderClassifier` (shared with notebook) |
| `services/ai/ai/model_loader.py` | Registry-driven model loading, in-process cache |
| `services/ai/xai_explainer.py` | SHAP TreeExplainer + explanation text generation |
| `packages/shared/schemas.py` | All canonical Pydantic v2 schemas |
| `scripts/train_models.py` | One-shot retrain of every artifact |
