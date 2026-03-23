# Feature Map — DTX-AI

This document maps project features to architectural components and Kanban columns.

---

## Core Features (MVP)

| # | Feature | Components | Priority |
|---|---------|-----------|---------|
| F1 | Event ingestion API | apps/api | P0 |
| F2 | Synthetic anomaly detection | services/ai | P0 |
| F3 | XAI explanation generation | services/ai | P0 |
| F4 | Live WebSocket broadcast | apps/api | P0 |
| F5 | Dashboard alert panel | apps/dashboard | P0 |
| F6 | Dashboard event history | apps/dashboard | P0 |
| F7 | Dashboard explanation panel | apps/dashboard | P0 |
| F8 | SQLite event persistence | apps/api | P0 |
| F9 | Isaac Sim adapter (stub) | apps/sim | P1 |
| F10 | Seed script + synthetic data | scripts/, data/ | P0 |

---

## Post-MVP Features

| # | Feature | Notes |
|---|---------|-------|
| F11 | Trained Isolation Forest model | Replace rule-based stub |
| F12 | SHAP feature attribution | Replace linear attribution stub |
| F13 | Isaac Sim scene update (real) | Requires Isaac Sim installation |
| F14 | Real sensor ESP32 integration | Hardware milestone |
| F15 | PostgreSQL storage | Scale beyond SQLite |
| F16 | User authentication | When deploying beyond local |
| F17 | Multi-zone dashboard map | Visual warehouse floor plan |
