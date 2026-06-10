---
id: known-issues
title: Known Issues & Technical Debt
sidebar_position: 13
---

# Known Issues & Technical Debt

## Dataset

### FIXED: row-level split leakage

The old demo holdout was a **row-level stratified 20% split**. At ~60 Hz, neighbouring rows are near-duplicates, so the demo effectively replayed training data. This is fixed: the canonical split is now **per-episode temporal** — the demo holdout is the last 20% of every contiguous fault run, with a 60-row purge gap (`PURGE_GAP_ROWS`, ~1.02 s minimum separation) dropped between pool and holdout, and train/val inside the pool uses the same mechanics (75/25). All 7 model families were retrained on this split, and `--split holdout` in the replay tooling now serves the leakage-safe holdout by default.

### Still open: the dataset is too separable

:::caution
Near-perfect scores are now a **dataset property, not leakage**: a LightGBM trained on just the top-3 ANOVA features reaches macro F1 **0.994** on the honest demo holdout (see `shared/sanity_baselines.json`). The Isaac Sim team still needs to produce noisier, harder data.
:::

| Issue | Detail |
|---|---|
| **Per-class signatures barely overlap** | The top-3 ANOVA features alone separate the classes almost perfectly. The classifier isn't really doing hard work yet. |
| **No fault precursors** | The CSV jumps directly from `nominal` to a steady fault state with no transition region. The model never sees ambiguous near-boundary events. |
| **No mixed faults** | There is no `wheel_slip + overheat` regime. Compound faults will collapse to whichever class is closest. |
| **Limited environmental noise** | Aside from ~100 NaN sensor dropouts per channel, the channels are far cleaner than real telemetry. The model has not learned to ignore a realistic noise floor. |

The full breakdown and the concrete things the Isaac Sim team can do to fix this lives in [docs/isaac_sim_integration.md §3–4](https://github.com/YKesX/DTX-AI/blob/main/docs/isaac_sim_integration.md).

---

## Incomplete Features

| Issue | Detail |
|---|---|
| **`/events` page** | Placeholder div — "Events page coming soon..." (`App.jsx`) |
| **`/settings` page** | Placeholder div — "Settings page coming soon..." (`App.jsx`) |
| **Isaac Sim integration** | `apps/sim/sim/scene.py` and `apps/sim/sim/hooks.py` are logging stubs — no real USD / Omniverse calls |
| **Deep-model SHAP** | TabNet, CNN, Bi-LSTM and LSTM-AE all have `supports_tree_xai: false` — explanation degrades to a generic per-class summary string; no per-feature attribution. Adding `shap.DeepExplainer` is open |
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
