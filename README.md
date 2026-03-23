# DTX-AI — Smart Warehouse XAI Digital Twin

> **University Capstone Project** — AI anomaly detection, explainability, digital-twin synchronisation, and a lightweight live web dashboard for a smart warehouse scenario.

---

## Architecture Overview

```
DTX-AI/
├── apps/
│   ├── api/          # FastAPI backend — event ingestion, alert distribution, WebSocket
│   ├── dashboard/    # React + Vite frontend — live alerts, explanation panel, event log
│   └── sim/          # NVIDIA Isaac Sim adapter — isolated digital-twin sync hooks
├── services/
│   └── ai/           # Anomaly detection + XAI explanation pipeline
├── packages/
│   └── shared/       # Canonical event schemas (EventIn, AnomalyResult, …)
├── data/             # Synthetic sample events and local SQLite storage
├── docs/             # Architecture, Kanban, sprint plans, demo script
├── scripts/          # Developer convenience: setup, seed, run-dev
└── tests/            # Smoke + integration tests
```

### MVP Data Flow

```
[seed / manual event]
        │
        ▼
  POST /events  (apps/api)
        │
        ▼
  AI Pipeline  (services/ai)
  anomaly_score + anomaly_type + explanation
        │
        ├──► WebSocket /ws/events  ──►  Dashboard (apps/dashboard)
        │
        └──► Isaac Sim adapter     ──►  Digital-twin object status update
```

---

## Quick-Start (local MVP)

### Prerequisites
- Python 3.11+
- Node.js 20+
- (Optional) NVIDIA Isaac Sim 4.x for full digital-twin features

```bash
# 1. Clone and enter the repo
git clone https://github.com/YKesX/DTX-AI.git
cd DTX-AI

# 2. Run the automated setup
bash scripts/setup.sh

# 3. Start all local services (opens three terminals)
bash scripts/run_dev.sh

# 4. (In a separate terminal, after the API is up) seed sample events
python scripts/seed_events.py
```

Dashboard → http://localhost:5173  
API docs  → http://localhost:8000/docs

---

## Environment Variables

Copy the example files and fill in your values:

```bash
cp apps/api/.env.example apps/api/.env
cp apps/sim/.env.example apps/sim/.env
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python 3.11, FastAPI, Uvicorn |
| AI / XAI | Python, scikit-learn (stub), SHAP (stub) |
| Frontend | React 18, Vite, Tailwind CSS |
| Storage | SQLite (MVP) |
| Digital Twin | NVIDIA Isaac Sim 4 (optional, isolated adapter) |
| CI | GitHub Actions (lint + test) |

---

## Contributing

See [docs/kanban_workflow.md](docs/kanban_workflow.md) for the team Kanban process,
[docs/sprint_1_plan.md](docs/sprint_1_plan.md) for the first sprint plan,
and [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming and commit conventions.

---

## Project Goal

Produce a convincing end-to-end demo where:

1. A synthetic or manually triggered warehouse event arrives at the API.
2. The AI service scores the event and generates a plain-language explanation.
3. The Isaac Sim digital twin updates the affected asset's visual status.
4. The web dashboard displays the alert, explanation, and event history in real time.
