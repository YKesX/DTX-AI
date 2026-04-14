---
id: setup
title: Setup & Running
sidebar_position: 11
---

# Setup & Running Locally

## Prerequisites

- Python **3.11+**
- Node.js **18+** and npm
- Git
- macOS: `brew install libomp` (required for LightGBM and XGBoost)
- Optional: NVIDIA Isaac Sim 4.x (only for digital twin — not required for demo)

---

## 1. Clone & Setup

```bash
git clone https://github.com/YKesX/DTX-AI.git
cd DTX-AI
bash scripts/setup.sh
```

The setup script:
- Installs Python deps for API (`apps/api/requirements.txt`)
- Installs Python deps for AI service (`services/ai/requirements.txt`)
- Installs the shared package: `pip install -e packages/shared`
- Installs frontend npm packages: `cd apps/dashboard && npm install`

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

## 3. Seed Demo Data

```bash
# Synthetic scenario seeder (bearing faults, overheating, etc.)
bash scripts/run_demo.sh

# Or: seed directly
python scripts/seed_demo_events.py
```

---

## 4. Dataset Replay Validation

```bash
# Replay held-out test rows through the live API
python scripts/replay_dataset_demo.py --model lightgbm

# With strict mode (no fallbacks)
python scripts/replay_dataset_demo.py --model lightgbm --strict

# Watch accuracy live at http://localhost:5173/validation
```

---

## 5. Run Tests

```bash
# All tests (from repo root)
pytest

# Integration tests only
pytest tests/integration/

# Smoke tests only
pytest tests/smoke/

# Specific test file
pytest tests/smoke/test_ai_pipeline.py -v
```

---

## Troubleshooting

**LightGBM / XGBoost crash on macOS:**
```bash
brew install libomp
```

**PYTHONPATH issues (AI pipeline not found):**
```bash
export PYTHONPATH="$PYTHONPATH:$(pwd)/services/ai:$(pwd)/packages/shared"
```

**Port already in use:**
```bash
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9
```

**SQLite database locked:**
Delete `apps/api/api/dtx_ai.db` and restart the API — it recreates on startup.
