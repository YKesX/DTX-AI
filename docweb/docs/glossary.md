---
id: glossary
title: Glossary
sidebar_position: 14
---

# Glossary

| Term | Definition |
|---|---|
| **Anomaly Detection** | Identifying sensor patterns that deviate from normal behaviour, indicating potential equipment faults |
| **XAI (Explainable AI)** | Techniques that make AI model decisions interpretable to humans. In DTX-AI, SHAP values show which sensor channels most influenced each classification |
| **SHAP** | SHapley Additive exPlanations — game-theory-based method assigning each input feature a contribution score for a specific prediction |
| **TreeExplainer** | SHAP explainer optimised for tree-based models (Random Forest, LightGBM, XGBoost) |
| **Feature Attribution** | The contribution score assigned to each input channel explaining why a model made a particular prediction |
| **Anomaly Score** | Normalised float `[0.0..1.0]` representing model confidence in its predicted class. For tree models and TabNet it is `max(predict_proba)` over the non-nominal classes; for the torch models it is the softmax probability of the argmax class |
| **Dataset Replay Mode** | Validation mode where demo-holdout rows are replayed through the live API with ground-truth labels for real-time accuracy tracking |
| **Demo Holdout** | The canonical leakage-safe evaluation slice: the last 20% of every contiguous fault run (per-episode temporal split), never seen during training. Served by `--split holdout` and used for all reported holdout metrics |
| **Purge Gap** | `PURGE_GAP_ROWS` (60 rows, ~1.02 s at 60 Hz) dropped between the training pool and the demo holdout so no held-out frame is adjacent to — or shares a sliding window with — a training frame |
| **Hardware Demo** | IRL demo mode: an ESP32 node (`HW/`, DS18B20 + BMP280) streams live readings via `scripts/hw_demo_bridge.py` into `POST /events/` with `metadata.source = "hardware_demo"` |
| **Strict Replay Mode** | `DTX_REPLAY_STRICT=1` — disables all fallbacks; the requested model and its class mapping must be available |
| **Ground Truth Label** | The actual known fault class for a dataset row, compared against the model prediction to compute accuracy |
| **Canonical Label** | Normalised string representation of a fault class (one of `nominal`, `bearing_wear`, `overheat`, `overload`, `pressure_fault`, `wheel_slip`) |
| **DashboardAlert** | Composed broadcast object: `EventIn` + `AnomalyResult` + `ExplanationResult` + `alert_id` |
| **EventLog** | Flat denormalised row persisted to the SQLite `events` table |
| **Operator Workflow** | Sequence of actions on an alert: acknowledge → assign → escalate → resolve |
| **Asset Drilldown** | Per-asset historical trend chart for the four most operator-relevant channels |
| **LiveReplayMetrics** | Thread-safe in-memory singleton tracking accuracy, confusion matrix, and per-model counts during a replay session |
| **Model Registry** | `model_registry.json` — lists all available model artifacts, paths, family types, and XAI support flags |
| **RuntimeModel** | Python dataclass (`model_loader.py`) holding a loaded model object, its metadata, scaler, feature order, and availability status |
| **Isaac Sim** | NVIDIA Isaac Sim 4.x — robotics simulation platform used for telemetry generation and digital-twin visualisation. The training dataset is sourced from it |
| **Digital Twin** | Virtual replica of a physical warehouse asset that mirrors its operational status in the simulation environment |
| **USD** | Universal Scene Description — NVIDIA's file format for 3D scenes in Omniverse/Isaac Sim |
| **TwinUpdate** | Schema object sent from the API to the Isaac Sim adapter carrying new asset status and severity |
| **Nominal** | Class 0 — normal operating state, no fault |
| **Bearing Wear** | Class 1 — drive-joint friction signature, ~300 W of unusual power dissipation |
| **Overheat** | Class 2 — elevated `temperature_c` with high `power_dissipated_w` and pseudo-pressure |
| **Overload** | Class 3 — modest power dissipation on otherwise nominal channels |
| **Pressure Fault** | Class 4 — `pseudo_pressure_pa` deeply negative, `lift_force_z` inverted |
| **Wheel Slip** | Class 5 — roller velocities desynchronised from drive joint, elevated temperature |
| **LSTM-AE + CLS** | LSTM Autoencoder with a multi-class classification head on the latent vector. The encoder learns a latent representation, the decoder reconstructs the input (auxiliary loss), and the classifier head predicts the fault class |
| **Windowed Model** | CNN and Bi-LSTM consume 30-step sliding windows built per-episode (windows never cross fault-run boundaries). At runtime the detector buffers 30 events before windowed inference and falls back to rules until the buffer fills |
| **Leaderboard** | `shared/leaderboard.json` — validation and demo-holdout metrics for all 7 model families plus the global winner (selected on validation F1, ties broken deterministically) |
| **Reconstruction MSE** | Mean squared error between the LSTM-AE input and its reconstructed output. Surfaced in `event.metadata.lstm_reconstruction_mse` for downstream monitoring; no longer used as the primary anomaly signal — class confidence is |
| **View-model** | Normalised flat object shape produced by `normalizeAlert.js`, consumed by all dashboard React components |
| **dtx-ai-shared** | The shared Pydantic v2 schema package installed as an editable pip package — single source of truth for inter-service contracts |
