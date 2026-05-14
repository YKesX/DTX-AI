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
| **Anomaly Score** | Normalised float `[0.0..1.0]` representing model confidence in its predicted class. For tree models it is `max(predict_proba)` over the non-nominal classes; for the LSTM-AE+CLS it is the softmax probability of the argmax class |
| **Dataset Replay Mode** | Validation mode where held-out dataset rows are replayed through the live API with ground-truth labels for real-time accuracy tracking |
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
| **Reconstruction MSE** | Mean squared error between the LSTM-AE input and its reconstructed output. Surfaced in `event.metadata.lstm_reconstruction_mse` for downstream monitoring; no longer used as the primary anomaly signal — class confidence is |
| **View-model** | Normalised flat object shape produced by `normalizeAlert.js`, consumed by all dashboard React components |
| **dtx-ai-shared** | The shared Pydantic v2 schema package installed as an editable pip package — single source of truth for inter-service contracts |
