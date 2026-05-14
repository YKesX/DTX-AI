---
id: ai-xai
title: AI / XAI Service
sidebar_position: 8
---

# AI / XAI Service

All ML inference and explainability logic lives in `services/ai/`. It is imported into the API process — not a network service.

---

## Model Registry

Four model families are supported. Active model is selected by event `metadata.active_model`, then the `DTX_ACTIVE_MODEL` env var, then `model_registry.json`'s `active_model`.

| Model | Artifact | Family | XAI Support | Test F1 |
|---|---|---|---|---|
| LightGBM | `best_lgbm.pkl` | `lightgbm` | ✅ SHAP TreeExplainer | 0.9991 |
| XGBoost | `best_xgb.pkl` | `xgboost` | ✅ SHAP TreeExplainer | 0.9991 |
| Random Forest | `best_rf.pkl` | `random_forest` | ✅ SHAP TreeExplainer | 0.9985 |
| LSTM-AE + classifier head | `best_lstmae.pth` | `lstm_autoencoder_pytorch` | ❌ Fallback only | 0.9981 |

Models are loaded once on first call and cached in-process via `model_loader.py`. The metrics above are on a stratified-random 20% held-out test split and should be read as "the model has learned the regime labels of the synthetic-ish dataset"; see [Known Issues](/docs/known-issues) for why these numbers are not yet trustworthy.

---

## Feature Set (19 raw sensor channels)

The runtime uses the raw 19-channel sensor vector defined in
[`services/ai/preprocessing.py:FEATURES`](https://github.com/YKesX/DTX-AI/blob/main/services/ai/preprocessing.py)
and persisted to `services/ai/ai/models/shared/feature_order.json`. No rolling-window features are computed at runtime — the previous 9-feature pipeline (with `vib_rolling_mean`, `temp_drift`, etc.) was retired when the dataset switched to the richer Isaac-Sim-style schema.

| Group | Channels |
|---|---|
| IMU linear acceleration | `imu_lin_acc_x`, `imu_lin_acc_y`, `imu_lin_acc_z` |
| IMU angular velocity | `imu_ang_vel_x`, `imu_ang_vel_y`, `imu_ang_vel_z` |
| Vibration | `vibration_magnitude` |
| Lift | `lift_joint_position`, `lift_force_z`, `lift_joint_velocity` |
| Hydraulic | `pseudo_pressure_pa` |
| Drive | `drive_joint_velocity`, `drive_joint_effort` |
| Rollers | `roller_fl_velocity`, `roller_fr_velocity`, `roller_bl_velocity`, `roller_br_velocity` |
| Bulk | `power_dissipated_w`, `temperature_c` |

A `StandardScaler` fit on the training split is applied before every inference call via `services/ai/ai/models/shared/scaler.pkl`. Feature order is positional — both the scaler and the model must see channels in the FEATURES order.

---

## Inference Pipeline

For each incoming `EventIn`, `ai.pipeline.run_pipeline` executes:

```
1. Build 19-channel feature vector from EventIn fields
   (missing channels → 0.0)
2. Apply StandardScaler (scaler.pkl)
3. Run the active model:
     • Tree model: predict_proba → argmax class + max-prob
     • LSTM-AE+CLS: forward → (reconstruction, logits)
                    softmax(logits) → argmax class + class confidence
4. Map class id → AnomalyType + Severity via detector._CLASS_MAP
5. Merge with rule-based guardrails (non-strict mode only)
6. SHAP TreeExplainer (tree models) or fallback attribution
7. Compose ExplanationResult (summary + recommendation)
```

`run_pipeline` is async and offloads CPU-bound inference to `asyncio.to_thread`.

The LSTM-AE+CLS also stamps the following diagnostic fields into `event.metadata` so downstream tooling can inspect the model's view:

- `lstm_predicted_class` — int
- `lstm_class_confidence` — softmax probability of the argmax
- `lstm_reconstruction_mse` — MSE of the autoencoder reconstruction
- `lstm_class_probabilities` — full softmax distribution

---

## LSTM-AE+CLS Architecture

Defined in [`services/ai/ai/lstm_classifier.py`](https://github.com/YKesX/DTX-AI/blob/main/services/ai/ai/lstm_classifier.py); the same class is imported by both the runtime and the training notebook so `state_dict` keys always line up.

```
input (B, 1, 19)
   │
   ▼
LSTM encoder ─► last hidden (B, hidden) ─► Linear ─► latent (B, latent)
                                                          │
        ┌─────────────────────────────────────────────────┴──────────┐
        ▼                                                            ▼
Linear ─► initial hidden                                  classifier head
LSTM decoder ──► Linear ─► reconstruction (B, 1, 19)      Linear ─ ReLU ─ Linear
                                                          ─► logits (B, num_classes)
```

Best hyperparameters on the current dataset: `epochs=50, hidden=32, latent=8, lr=1e-3, batch=64, λ_recon=1.0, λ_cls=1.0`.

---

## XAI — Explainability Layer

**SHAP TreeExplainer** is used for all tree-based models. It computes each feature's contribution to the model's prediction using Shapley values from cooperative game theory.

```python
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X)
# Top-3 features by |shap_value| → contributing_features dict
```

The top-3 features by absolute SHAP value are surfaced in the dashboard `ExplanationPanel` as a horizontal bar chart, making the model's reasoning visible to operators.

### LSTM-AE Explainability
LSTM-AE does **not** support SHAP (`supports_tree_xai: false` in registry). When active, `explain()` returns a generic per-class summary string — no per-feature attribution. Adding `DeepExplainer` support is tracked in [Known Issues](/docs/known-issues).

---

## Fallback Chain

In non-strict mode (`DTX_REPLAY_STRICT=0`), failures fall back gracefully:

```
ML model inference fails
    └─► Rule-based detector (threshold on raw channels)
            └─► Fallback explanation (rule-based attribution, no SHAP)
```

The rule-based detector uses 4 channels:

| Channel | Threshold | Maps to |
|---|---|---|
| `temperature_c` | > 40 °C | `OVERHEAT` |
| `\|pseudo_pressure_pa\|` | > 1000 Pa | `PRESSURE_FAULT` |
| `power_dissipated_w` | > 500 W | `OVERLOAD` |
| `vibration_magnitude` | > 15 m/s² | `BEARING_WEAR` |

In strict mode (`DTX_REPLAY_STRICT=1`), any failure raises an exception — used to validate the full pipeline end-to-end during dataset replay.

---

## Fault Classes

| Code | Label | Default severity | Discriminating signal |
|---|---|---|---|
| 0 | `nominal`        | info     | power ≈ 0, temperature ≈ 25 °C |
| 1 | `bearing_wear`   | warning  | power ≈ 300 W, drive effort dip |
| 2 | `overheat`       | critical | temperature ≈ 49 °C, power ≈ 2 kW, rollers ≈ 0.6 |
| 3 | `overload`       | warning  | power ≈ 30 W on otherwise nominal channels |
| 4 | `pressure_fault` | warning  | pseudo_pressure ≈ −8.5 kPa, lift_force_z ≈ −685 N |
| 5 | `wheel_slip`     | warning  | rollers ≈ 0.7, drive_joint_velocity ≈ 0.37 |

---

## Retraining

Every artifact in `services/ai/ai/models/` can be regenerated with:

```bash
source .venv/bin/activate
python scripts/train_models.py
```

The script is a one-for-one mirror of [`services/ai/dtxai_model_training.ipynb`](https://github.com/YKesX/DTX-AI/blob/main/services/ai/dtxai_model_training.ipynb) cells 2–10: 5-split × per-model HP sweep (220 fits total), GPU is used automatically for the LSTM via PyTorch if a CUDA-capable device is present. On an RTX 3070 Ti the full run takes ~15 minutes.
