---
id: glossary
title: Glossary
sidebar_position: 14
---

# Glossary

| Term | Definition |
|---|---|
| **Anomaly Detection** | Process of identifying sensor patterns that deviate significantly from normal behavior, indicating potential equipment faults |
| **XAI (Explainable AI)** | Techniques that make AI model decisions interpretable to humans. In DTX-AI, SHAP values show which sensor features most influenced each classification |
| **SHAP** | SHapley Additive exPlanations — game-theory-based method assigning each input feature a contribution score for a specific prediction |
| **TreeExplainer** | SHAP explainer optimized for tree-based models (Random Forest, LightGBM, XGBoost) |
| **Feature Attribution** | The contribution score assigned to each input feature explaining why a model made a particular prediction |
| **Anomaly Score** | Normalized float `[0.0..1.0]` representing model confidence that an event is anomalous. Scores ≥ 0.5 trigger `is_anomaly=True` |
| **Dataset Replay Mode** | Validation mode where held-out dataset rows are replayed through the live API with ground-truth labels for real-time accuracy tracking |
| **Strict Replay Mode** | `DTX_REPLAY_STRICT=1` — disables all fallbacks; model, SHAP, and threshold must all succeed |
| **Ground Truth Label** | The actual known fault class for a dataset row, compared against model prediction to compute accuracy |
| **Canonical Label** | Normalized string representation of a fault class (`no_fault`, `bearing_fault`, `overheating`, `combined`) |
| **DashboardAlert** | Composed broadcast object: `EventIn` + `AnomalyResult` + `ExplanationResult` + `alert_id` |
| **EventLog** | Flat denormalized row persisted to the SQLite `events` table for each processed event |
| **Operator Workflow** | Sequence of actions on an alert: acknowledge → assign → escalate → resolve |
| **Asset Drilldown** | Per-asset historical sensor trend chart showing the last N readings with anomaly scores |
| **LiveReplayMetrics** | Thread-safe in-memory singleton tracking accuracy, confusion matrix, and per-model counts during a replay session |
| **Window Buffer** | Per-asset rolling buffer of the last 5 sensor readings used to compute rolling statistical features |
| **Model Registry** | `model_registry.json` — lists all available model artifacts, paths, family types, and XAI support flags |
| **RuntimeModel** | Python dataclass (`model_loader.py`) holding a loaded model object, its metadata, scaler, feature order, and availability status |
| **Isaac Sim** | NVIDIA Isaac Sim 4.x — robotics simulation platform used for digital twin visualization. Integrated via `apps/sim/` (currently stubbed) |
| **Digital Twin** | Virtual replica of a physical warehouse asset that mirrors its operational status in the simulation environment |
| **USD** | Universal Scene Description — NVIDIA's file format for 3D scenes in Omniverse/Isaac Sim |
| **TwinUpdate** | Schema object sent from the API to the Isaac Sim adapter carrying new asset status and severity |
| **Bearing Fault** | Class 1 fault — abnormal vibration patterns indicating mechanical bearing degradation in rotating equipment |
| **Overheating** | Class 2 fault — elevated temperature readings indicating thermal runaway or cooling system failure |
| **No Fault** | Class 0 — normal operating state, no anomaly detected |
| **Combined** | Class 3 — multiple sensor readings simultaneously elevated, indicating a compound fault |
| **LSTM-AE** | LSTM Autoencoder — learns to reconstruct normal time-series; high reconstruction error (MSE) indicates an anomaly |
| **Reconstruction Error** | Mean squared error between LSTM-AE input and output. Values above `default_threshold` are classified as anomalies |
| **View-model** | Normalized flat object shape produced by `normalizeAlert.js`, consumed by all dashboard React components |
| **dtx-ai-shared** | The shared Pydantic v2 schema package installed as an editable pip package — single source of truth for inter-service contracts |
