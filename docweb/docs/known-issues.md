---
id: known-issues
title: Known Issues & Technical Debt
sidebar_position: 13
---

# Known Issues & Technical Debt

## TODOs in Codebase

| Location | TODO |
|---|---|
| `services/ai/ai/explainer.py:35` | Replace with SHAP TreeExplainer / DeepExplainer when model is ready — stale for tree models, still relevant for LSTM-AE |
| `apps/sim/sim/scene.py:9` | Replace stub implementations with real USD/Omniverse calls |
| `apps/sim/sim/scene.py:30` | Open the USD stage, find the prim by asset_id/zone_id |
| `apps/sim/sim/hooks.py:7` | Wire into an actual Isaac Sim Extension when Isaac Sim is installed |
| `apps/sim/sim/hooks.py:20–21` | Load warehouse USD scene + subscribe to physics callbacks |

---

## Incomplete Features

| Issue | Detail |
|---|---|
| `/events` page | Placeholder div — "Events page coming soon..." (`App.jsx:22`) |
| `/settings` page | Placeholder div — "Settings page coming soon..." (`App.jsx:28`) |
| Isaac Sim integration | Entire `apps/sim/` is a logging stub — no real USD/Omniverse calls |
| LSTM-AE SHAP | `supports_tree_xai: false` — explanation degrades to generic string, no feature attribution |
| SHAP not persisted | `contributing_features` are lost after WebSocket broadcast — `GET /alerts/` returns `top_features: []` |
| CORS config unused | `api/config.py` defines `cors_origins` but `main.py` hardcodes `allow_origins=["*"]` |
| PyTorch not in requirements | `torch` is an implicit dependency for `lstm_ae` — not listed in any `requirements.txt` |

---

## Architecture Flags

- **Replace SQLite with PostgreSQL** when data volume grows (`architecture.md:79`)
- **Add message queue** (Redis Streams or NATS) between API and AI service for high-throughput (`architecture.md:81`)
- **Tighten CORS** (`main.py:44`) before any external deployment
- **`lazy import` pattern** in `events.py:94–108` — `from ai.pipeline import run_pipeline` inside the route handler body; should move to startup-time import when `PYTHONPATH` is reliably set
- **Model metrics disclaimer** — saved model metrics come from different historical split setups and should not be treated as directly comparable
