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
│   │   ├── requirements.txt
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
│   │       │   ├── dashboard/        # StatusCards, EventTable, ExplanationPanel...
│   │       │   ├── validation/       # ReplaySummaryCards, ConfusionMatrix...
│   │       │   ├── layout/           # Sidebar, TopBar
│   │       │   └── ui/               # Badge, Card
│   │       ├── hooks/
│   │       │   └── useWebSocket.js   # WS hook with auto-reconnect
│   │       └── lib/
│   │           └── normalizeAlert.js # Multi-shape alert normalizer
│   │
│   └── sim/                          # NVIDIA Isaac Sim adapter (stub)
│       └── sim/
│           ├── adapter.py            # notify(TwinUpdate) entry point
│           ├── scene.py              # USD scene helpers (stubbed)
│           └── hooks.py              # Sim lifecycle hooks (stubbed)
│
├── services/
│   └── ai/                           # AI/ML pipeline (imported into API)
│       ├── requirements.txt
│       ├── preprocessing.py          # Kaggle dataset loader + feature engineering
│       ├── xai_explainer.py          # SHAP TreeExplainer
│       └── ai/
│           ├── pipeline.py           # run_pipeline(event) — async entry point
│           ├── detector.py           # Multi-model detector + rule-based fallback
│           ├── explainer.py          # XAI explanation dispatch
│           ├── model_loader.py       # Registry-driven model loading
│           └── models/
│               ├── shared/
│               │   ├── model_registry.json
│               │   ├── feature_order.json
│               │   └── scaler.pkl
│               ├── lightgbm/best_lgbm.pkl
│               ├── random_forest/best_rf.pkl
│               ├── xgboost/best_xgb.pkl
│               └── lstm_ae/best_lstmae.pth
│
├── packages/
│   └── shared/
│       ├── pyproject.toml            # dtx-ai-shared v0.1.0
│       └── schemas.py                # All canonical Pydantic v2 schemas
│
├── scripts/
│   ├── setup.sh                      # One-time dev environment setup
│   ├── run_dev.sh                    # Start API + dashboard
│   ├── run_demo.sh                   # Full demo orchestrator
│   ├── replay_dataset_demo.py        # Dataset replay CLI tool
│   └── seed_demo_events.py           # Synthetic scenario seeder
│
├── tests/
│   ├── integration/test_api.py
│   └── smoke/
│       ├── test_ai_pipeline.py
│       ├── test_live_metrics.py
│       ├── test_model_runtime.py
│       └── test_schemas.py
│
└── docs/                             # Internal architecture docs
```

## Key File Reference

| File | Responsibility |
|---|---|
| `apps/api/main.py` | App factory, lifespan hooks, router registration |
| `apps/api/api/database.py` | All SQLite operations (init, insert, fetch, clear) |
| `apps/api/api/live_metrics.py` | Thread-safe in-memory replay metrics singleton |
| `apps/api/api/routes/events.py` | `POST /events/` — main ingestion + AI call + broadcast |
| `apps/dashboard/src/hooks/useWebSocket.js` | WS connection with auto-reconnect (3s delay) |
| `apps/dashboard/src/lib/normalizeAlert.js` | Normalizes any backend shape to flat view-model |
| `services/ai/ai/pipeline.py` | `run_pipeline(event)` — async entry point |
| `services/ai/ai/model_loader.py` | Registry-driven model loading, in-process cache |
| `services/ai/xai_explainer.py` | SHAP TreeExplainer + explanation text generation |
| `packages/shared/schemas.py` | All canonical Pydantic v2 schemas (inter-service contract) |
