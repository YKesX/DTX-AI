# Sprint 1 Plan — DTX-AI

**Duration:** 2 weeks  
**Goal:** Working end-to-end vertical slice — synthetic event → anomaly → explanation → dashboard alert

---

## Sprint Goal

By the end of Sprint 1 any team member can:
1. Run `bash scripts/setup.sh` then `bash scripts/run_dev.sh`
2. Execute `python scripts/seed_events.py`
3. Watch the dashboard at `http://localhost:5173` receive and display live alerts

---

## Sprint Backlog

| # | Story | Owner | Points | Status |
|---|-------|-------|--------|--------|
| S1-1 | Repo skeleton + CI workflow | DevOps | 2 | ✅ Done |
| S1-2 | Shared event schemas (EventIn, AnomalyResult, ExplanationResult) | Backend | 2 | ✅ Done |
| S1-3 | FastAPI POST /events + GET /health + GET /alerts | Backend | 3 | ✅ Done |
| S1-4 | WebSocket /ws/events broadcast | Backend | 2 | ✅ Done |
| S1-5 | SQLite persistence layer | Backend | 2 | ✅ Done |
| S1-6 | AI rule-based anomaly detector stub | AI | 3 | ✅ Done |
| S1-7 | XAI explanation generator stub | AI | 2 | ✅ Done |
| S1-8 | Dashboard: status card + live alerts panel | Frontend | 3 | ✅ Done |
| S1-9 | Dashboard: event list + explanation panel | Frontend | 3 | ✅ Done |
| S1-10 | Isaac Sim adapter stub | Sim | 2 | ✅ Done |
| S1-11 | Seed script + sample events | Scripts | 1 | ✅ Done |
| S1-12 | Smoke tests for schemas + AI pipeline | QA | 2 | ✅ Done |

---

## Definition of Done

- [ ] All Sprint 1 tasks merged to `main`
- [ ] Smoke tests pass in CI
- [ ] Seed script produces visible alerts on dashboard
- [ ] README quick-start works on a fresh machine
- [ ] Kanban board reflects current state
