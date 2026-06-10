---
id: ai-xai
title: AI / XAI Service
sidebar_position: 8
---

# AI / XAI Service

All ML inference and explainability logic lives in `services/ai/`. It is imported into the API process — not a network service.

---

## Model Registry

Seven model families are supported. Active model is selected by event `metadata.active_model`, then the `DTX_ACTIVE_MODEL` env var, then `model_registry.json`'s `active_model`.

| Model | Artifact | Registry key | XAI Support | Demo-holdout macro F1 |
|---|---|---|---|---|
| Random Forest | `best_rf.pkl` | `random_forest` | ✅ SHAP TreeExplainer | 0.9977 |
| LightGBM | `best_lgbm.pkl` | `lightgbm` | ✅ SHAP TreeExplainer | 0.9982 |
| XGBoost | `best_xgb.pkl` | `xgboost` | ✅ SHAP TreeExplainer | 0.9985 |
| TabNet | `best_tabnet.zip` | `tabnet` | ❌ Fallback only | 0.9953 |
| 1-D CNN (windowed) | `best_cnn.pth` | `cnn` | ❌ Fallback only | 0.9920 |
| Bi-LSTM (windowed) | `best_bilstm.pth` | `bilstm` | ❌ Fallback only | 1.0000 |
| LSTM-AE + classifier head | `best_lstmae.pth` | `lstm_ae` | ❌ Fallback only | 0.9967 |

Models are loaded once on first call and cached in-process via `model_loader.py`. The metrics above come from `shared/leaderboard.json` and are measured on the **leakage-safe demo holdout** — the per-episode temporal tail (last 20% of every contiguous fault run, with a 60-row purge gap; see the Retraining section below). The global winner — selected on validation F1, ties broken deterministically — is the **CNN**, saved as `shared/model_best.pth`. Near-perfect scores are now a property of the dataset's separability, not split leakage; see [Known Issues](/docs/known-issues).

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

Scaled model families ship their own `scaler.pkl` inside the family directory (e.g. `services/ai/ai/models/cnn/scaler.pkl`); the runtime loader prefers the per-family scaler and only falls back to `shared/scaler.pkl` (which is always refreshed by training). LightGBM and XGBoost are intentionally **unscaled** (`requires_scaler: false`) and consume NaN sensor dropouts natively. Feature order is positional — both the scaler and the model must see channels in the FEATURES order.

---

## Inference Pipeline

For each incoming `EventIn`, `ai.pipeline.run_pipeline` executes:

```
1. Build 19-channel feature vector from EventIn fields
   (missing channels → 0.0)
2. Apply the model family's StandardScaler (per-family scaler.pkl;
   skipped for LightGBM/XGBoost, which consume raw values + NaN)
3. Run the active model:
     • Tree model / TabNet: predict_proba → argmax class + max-prob
     • CNN / Bi-LSTM (windowed): infer on the last 30 buffered events
     • LSTM-AE+CLS: forward → (reconstruction, logits)
                    softmax(logits) → argmax class + class confidence
4. Map class id → AnomalyType + Severity via detector._CLASS_MAP
5. Merge with rule-based guardrails (non-strict mode only)
6. SHAP TreeExplainer (tree models) or fallback attribution
7. Compose ExplanationResult (summary + recommendation)
```

`run_pipeline` is async and offloads CPU-bound inference to `asyncio.to_thread`.

### Windowed models (CNN, Bi-LSTM)

CNN and Bi-LSTM are trained on **30-step sliding windows** built per-episode, so windows never cross fault-run boundaries. At runtime the detector buffers incoming events and **falls back to the rule-based detector until 30 events have accumulated**; once the buffer is full it runs windowed inference on the most recent 30 frames. The buffer size is read from each model's `best_params.window` metadata.

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

Best hyperparameters on the current dataset: `hidden=32, latent=16, lr=1e-3, batch=64, dropout=0.2, λ_recon=1.0, λ_cls=1.0` — training is capped at 20 epochs (anti-memorisation cap) and keeps the best-validation-F1 epoch.

---

## XAI — Explainability Layer

**SHAP TreeExplainer** is used for all tree-based models. It computes each feature's contribution to the model's prediction using Shapley values from cooperative game theory.

```python
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X)
# Top-3 features by |shap_value| → contributing_features dict
```

The top-3 features by absolute SHAP value are surfaced in the dashboard `ExplanationPanel` as a horizontal bar chart, making the model's reasoning visible to operators.

### Deep / non-tree model explainability
TabNet, CNN, Bi-LSTM and LSTM-AE do **not** support SHAP TreeExplainer (`supports_tree_xai: false` in registry). When one of them is active, `explain()` returns a generic per-class summary string — no per-feature attribution. Adding `DeepExplainer` support is tracked in [Known Issues](/docs/known-issues).

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

The training methodology (shared by all 7 families):

1. **Single fixed canonical split** — no more sweeping multiple split configurations. The demo holdout is the **last 20% of every contiguous fault run** (per-episode temporal), with a 60-row purge gap (`PURGE_GAP_ROWS`) dropped between pool and holdout so no demo frame is adjacent to — or shares a sliding window with — any training frame. Train/val inside the remaining pool uses the same per-run temporal mechanics (75/25, again purge-gapped). Split functions: `split_demo_pool_and_holdout`, `split_pool_train_val`, `get_training_pool`, `get_demo_holdout` in `services/ai/preprocessing.py`.
2. **Class weights everywhere** — the dataset is unbalanced (3,000–4,200 rows per class): trees use `class_weight="balanced"`, XGBoost uses balanced `sample_weight`, torch models use class-weighted `CrossEntropyLoss`.
3. **Early stopping** — LightGBM/XGBoost train up to 1000 rounds with 50-round early stopping on validation loss; torch models keep the best-validation-F1 epoch with patience; LSTM-AE remains capped at 20 epochs.
4. **NaN robustness** — scaled models wrap median imputation + `StandardScaler` in their pipeline; LightGBM/XGBoost stay unscaled and consume NaN natively.
5. **Per-family scalers** — each family directory gets its own `scaler.pkl`; `shared/scaler.pkl` is refreshed as a fallback.

The run also writes `shared/leaderboard.json` (val/holdout metrics per family + the global winner), `shared/sanity_baselines.json` (ANOVA feature ranking + trivial-baseline scores), and the winner checkpoint `shared/model_best.pth` (currently the CNN). GPU is used automatically for the torch models if a CUDA-capable device is present.

[`services/ai/dtxai_model_training.ipynb`](https://github.com/YKesX/DTX-AI/blob/main/services/ai/dtxai_model_training.ipynb) is a cell-for-cell mirror of the script and is **generated** from it by `scripts/gen_training_notebook.py` — regenerate it after changing the script; never hand-edit the notebook.
