---
id: setup
title: Setup & Running
sidebar_position: 11
---

# Setup & Running Locally

## Prerequisites

- Python **3.11+** (3.14 verified to work on Linux with the official PyTorch CUDA wheels)
- Node.js **18+** and npm
- Git
- macOS: `brew install libomp` (required for LightGBM and XGBoost)
- Optional: NVIDIA GPU with CUDA driver for LSTM-AE training (CPU works too — just slower)
- Optional: NVIDIA Isaac Sim 4.x (only for digital-twin visualisation — not required for the dashboard demo)

---

## 1. Clone & Setup

```bash
git clone https://github.com/YKesX/DTX-AI.git
cd DTX-AI
bash scripts/setup.sh
```

The setup script:
- Creates `.venv/` if missing and installs Python deps for the API (`apps/api/requirements.txt`)
- Installs Python deps for the AI service (`services/ai/requirements.txt`)
- Installs the shared schema package: `pip install -e packages/shared`
- Installs frontend npm packages: `cd apps/dashboard && npm install`

### PyTorch (separate index)

The pinned ML deps include everything except `torch`, which must be installed from the official PyTorch CUDA wheel index because PyPI does not always ship matching CUDA builds:

```bash
source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

Use the index URL matching your GPU's CUDA driver (`nvidia-smi` shows the driver). CPU-only also works for runtime — only training is slow without a GPU.

---

## 2. Start the Full Stack

```bash
bash scripts/run_dev.sh
```

Starts both services as background processes:
- **API** → `http://localhost:8000`
- **Dashboard** → `http://localhost:5173`
- **API docs (Swagger)** → `http://localhost:8000/docs`

---

## 3. Dataset Replay Demo

The legacy hand-crafted synthetic-scenario seeder was retired when the dataset switched to the Isaac-Sim 19-channel schema. The supported demo flow is dataset replay:

```bash
# Boot API + dashboard + replay the held-out tail of the dataset
bash scripts/run_demo.sh

# Strict mode (no fallbacks; model + class_mapping must load)
bash scripts/run_demo.sh --strict-replay --model lightgbm

# Or run the replay alone against an already-running API
python scripts/replay_dataset_demo.py --model lightgbm --limit 200 --delay 0.3
```

Watch the running accuracy live at `http://localhost:5173/validation`.

To wire Isaac Sim itself in, see [docs/isaac_sim_integration.md](https://github.com/YKesX/DTX-AI/blob/main/docs/isaac_sim_integration.md) in the repo.

---

## 4. Retrain the Models

```bash
source .venv/bin/activate
python scripts/train_models.py
```

This is the exact notebook sweep (5 splits × per-model HP grid = 220 fits). On an RTX 3070 Ti the full run takes ~15 minutes. Artifacts are written in place under `services/ai/ai/models/`:

- `random_forest/best_rf.pkl`, `lightgbm/best_lgbm.pkl`, `xgboost/best_xgb.pkl`, `lstm_ae/best_lstmae.pth`
- `shared/scaler.pkl`, `shared/feature_order.json`, `shared/model_best.pkl`
- A fresh `metadata.json` next to each artifact

---

## 5. Run Tests

```bash
# All tests (from repo root)
PYTHONPATH="packages:services:services/ai:apps/api:apps/sim" .venv/bin/pytest -q

# Unit tests only
PYTHONPATH="packages:services:services/ai:apps/api:apps/sim" .venv/bin/pytest -q tests/unit

# Integration tests only
.venv/bin/pytest -q tests/integration/

# Smoke tests only
.venv/bin/pytest -q tests/smoke/
```

Current checked-in suite structure:

- `tests/unit/` — helper-heavy module coverage for event-route helpers, SQLite/database helpers, config parsing, WebSocket connection management, and Isaac Sim adapter/stub behavior
- `tests/smoke/` — stable runtime checks for schemas, replay helpers, model loading, and the rule-based fallback path
- `tests/integration/` — ASGI-level API route coverage across ingestion, metrics, timeline, and operator-action flows

At the time of the `v2.0` docs refresh, the suite passes locally at `54 passed`.

---

## Troubleshooting

**LightGBM / XGBoost crash on macOS:**
```bash
brew install libomp
```

**PYTHONPATH issues (`from ai.pipeline import ...` fails):**
```bash
export PYTHONPATH="$PYTHONPATH:$(pwd)/packages:$(pwd)/services:$(pwd)/services/ai"
```

**Port already in use:**
```bash
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9
```

**SQLite database locked:**
Delete `apps/api/api/dtx_ai.db` and restart the API — it recreates on startup.

**`InconsistentVersionWarning` when loading `.pkl` artifacts:**
Your installed `scikit-learn` is newer than the version the artifact was pickled with. Either reinstall from `services/ai/requirements.txt` (pinned to `scikit-learn==1.8.0`) or rerun `python scripts/train_models.py` to regenerate the artifacts against your current version.
