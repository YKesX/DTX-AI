---
id: known-issues
title: Known Issues & Technical Debt
sidebar_position: 13
---

# Known Issues & Technical Debt

## Dataset

The training dataset is now produced by Isaac Sim and uses 19 sensor channels, but the F1 ≈ 1.0 result on a held-out 20% test split is still suspicious. Concretely:

| Issue | Detail |
|---|---|
| **Rows sorted by label** | `fault_label` lives in 6 contiguous 1 800-row blocks. Random `train_test_split` consequently sees adjacent rows in train and test. Use the chronological split (`scripts/replay_dataset_demo.py:chronological_split`) for honest evaluation. |
| **Per-class signatures barely overlap** | A 3-deep decision stump on `(power_dissipated_w, pseudo_pressure_pa, roller_fl_velocity)` already separates most pairs. The classifier isn't really doing hard work yet. |
| **No fault precursors** | The CSV jumps directly from `nominal` to a steady fault state with no transition region. The model never sees ambiguous near-boundary events. |
| **No mixed faults** | There is no `wheel_slip + overheat` regime. Compound faults will collapse to whichever class is closest. |
| **No environmental noise** | Vibration magnitude is essentially constant in the CSV. The model has not learned to ignore noise. |

The full breakdown and the four concrete things the Isaac Sim team can do to fix this lives in [docs/isaac_sim_integration.md §3–4](https://github.com/YKesX/DTX-AI/blob/main/docs/isaac_sim_integration.md).

---

## Incomplete Features

| Issue | Detail |
|---|---|
| **`/events` page** | Placeholder div — "Events page coming soon..." (`App.jsx`) |
| **`/settings` page** | Placeholder div — "Settings page coming soon..." (`App.jsx`) |
| **Isaac Sim integration** | `apps/sim/sim/scene.py` and `apps/sim/sim/hooks.py` are logging stubs — no real USD / Omniverse calls |
| **LSTM-AE SHAP** | `supports_tree_xai: false` — explanation degrades to a generic per-class summary string; no per-feature attribution. Adding `shap.DeepExplainer` is open |
| **SHAP not persisted** | `contributing_features` are lost after WebSocket broadcast — `GET /alerts/` returns alerts without them |
| **CORS config unused** | `api/config.py` defines `cors_origins` but `main.py` hardcodes `allow_origins=["*"]` |
| **PyTorch outside the requirements file** | `torch` is intentionally documented as a separate `pip install` step in `services/ai/requirements.txt` because PyPI's torch wheel doesn't always ship CUDA support — must come from the official index URL |

---

## Architecture Flags

- **Replace SQLite with PostgreSQL** when concurrent write volume grows
- **Add a message queue** (Redis Streams or NATS) between API and AI service for high-throughput production use
- **Tighten CORS** in `main.py` before any external deployment
- **Lazy import pattern** in `events.py` — `from ai.pipeline import run_pipeline` happens inside the route handler body for path-setup reasons; should move to startup-time once `PYTHONPATH` is reliably set in every entrypoint
- **Sklearn version pinning** — every checked-in `.pkl` is pickled against `scikit-learn==1.8.0`; bumping that version requires running `python scripts/train_models.py` to regenerate, otherwise `InconsistentVersionWarning` leaks at load time and behaviour may drift
- **No retraining CI step** — `scripts/train_models.py` is not run on every PR; metrics in `metadata.json` are only as fresh as the last manual run
