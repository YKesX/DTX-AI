# DTX-AI Project Kanban Board

## Project Status Overview

Based on codebase analysis as of 2026-03-25:
- **Done**: 9 features (Core infrastructure & MVP)
- **In Progress**: 2 features (Refinement phase)
- **To Do**: 1 feature (Future phase)

---

## Kanban Board

| To Do                              | In Progress                          | Done                                 |
|------------------------------------|--------------------------------------|--------------------------------------|
| HW-01 ESP32 health input           | WEB-03 Trend grafiği                 | DT-01 Mini repo sainresi             |
|                                    | OPS-02 Kanban ölçüleri               |               |
|                                    |                                      | AI-01 Core feature extraction        |
|                                    |                                      | AI-02 Event scoring                  |
|                                    |                                      | XAI-01 Top feature explanation       |
|                                    |                                      | DT-03 Alert visualization            |
|                                    |                                      | WEB-01 Canlı durum paneli            |
|                                    |                                      | WEB-02 Olay tablosu                  |
|                                    |                                      | OPS-01 Replay mode                   |

---

## Feature Status Details

### ✅ DONE (9 items)

**DT-01: Mini repo sainresi** - Repository structure fully established with modular architecture
- Location: `apps/api/`, `apps/dashboard/`, `services/ai/`
- Status: Complete

**DT-02: Entity playback** - Event seeding and demo scenario generation
- Location: `scripts/seed_demo_events.py`, `data/generate_synthetic.py`
- Status: Complete with 7 demo scenarios

**AI-01: Core feature extraction** - Feature engineering pipeline
- Location: `services/ai/preprocessing.py`, `services/ai/ai/detector.py`
- Features: Window-based feature computation, rolling statistics, normalization
- Status: Fully implemented with support for vibration, temperature, pressure, humidity

**AI-02: Event scoring** - Anomaly detection with model registry
- Location: `services/ai/ai/detector.py`, `services/ai/ai/model_loader.py`
- Models: LightGBM, RandomForest, XGBoost, LSTM-AE
- Status: Complete with fallback mechanisms

**XAI-01: Top feature explanation** - SHAP-based explainability
- Location: `services/ai/xai_explainer.py`, `services/ai/ai/explainer.py`
- Status: Implemented with tree model support and graceful fallbacks

**DT-03: Alert visualization** - Real-time alert display
- Location: `apps/dashboard/src/components/dashboard/AlertPanel.jsx`
- Status: Complete with live WebSocket updates

**WEB-01: Canlı durum paneli** - Live status dashboard
- Location: `apps/dashboard/`
- Status: React + Vite + Tailwind CSS fully functional

**WEB-02: Olay tablosu** - Event history table
- Location: `apps/dashboard/src/components/dashboard/EventTable.jsx`
- Status: Complete with sorting and filtering

**OPS-01: Replay mode** - Event replay with delay control
- Location: `scripts/seed_demo_events.py` with `--delay` parameter
- Status: Fully functional

### 🔄 IN PROGRESS (2 items)

**WEB-03: Trend grafiği** - Time-series trending visualization
- Location: `apps/dashboard/src/components/dashboard/TrendChart.jsx`
- Notes: Component structure exists, refinements ongoing
- Priority: Medium

**OPS-02: Kanban ölçüleri** - Kanban board metrics and tracking
- Location: `kanban.md` (this file)
- Notes: Initial setup complete, feature tracking ongoing
- Priority: Low

### ⏳ TO DO (1 item)

**HW-01: ESP32 health input** - Hardware sensor
