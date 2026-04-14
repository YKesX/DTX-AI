---
id: ai-xai
title: AI / XAI Service
sidebar_position: 8
---

# AI / XAI Service

All ML inference and explainability logic lives in `services/ai/`. It is imported into the API process — not a network service.

---

## Model Registry

Four model families are supported. Active model is selected via `MODEL_NAME` env var or `model_registry.json`.

| Model | Artifact | Family | XAI Support | Notes |
|---|---|---|---|---|
| LightGBM | `best_lgbm.pkl` | `lightgbm` | ✅ TreeExplainer | Primary recommended |
| XGBoost | `best_xgb.pkl` | `xgboost` | ✅ TreeExplainer | High accuracy |
| Random Forest | `best_rf.pkl` | `random_forest` | ✅ TreeExplainer | Most interpretable |
| LSTM-AE | `best_lstmae.pth` | `lstm_ae` | ❌ Fallback only | Reconstruction-error based |

Models are loaded once on first call and **cached in-process** via `model_loader.py`.

---

## Feature Engineering (9-Feature Vector)

Raw sensor readings are augmented with **per-asset rolling window statistics** (window = 5 events).

| Feature | Description |
|---|---|
| `Vibration (mm/s)` | Raw vibration reading |
| `Temperature (°C)` | Raw temperature reading |
| `Humidity (%)` | Raw humidity reading |
| `Pressure (hPa)` | Raw pressure reading |
| `vib_rolling_mean` | 5-event rolling mean of vibration |
| `vib_rolling_std` | 5-event rolling std dev of vibration |
| `vib_rolling_max` | 5-event rolling max of vibration |
| `temp_rolling_mean` | 5-event rolling mean of temperature |
| `temp_rolling_std` | 5-event rolling std dev of temperature |

The canonical feature order is defined in `models/shared/feature_order.json`. A `StandardScaler` (fitted on training data) is applied before inference via `scaler.pkl`.

---

## Inference Pipeline

For each incoming `EventIn`, the pipeline executes:

```
1. Get/init 5-event rolling window buffer for asset:zone
2. Build 9-feature vector (raw + rolling stats)
3. Apply StandardScaler (scaler.pkl)
4. model.predict_proba() → anomaly_score [0..1]
5. Threshold (default 0.5) → is_anomaly bool
6. Determine anomaly_type + severity from score + readings
7. SHAP TreeExplainer → contributing_features dict
8. Compose ExplanationResult (summary text + recommendation)
```

The `pipeline.py` entry point is `async def run_pipeline(event: EventIn)`, which offloads CPU-bound inference to `asyncio.to_thread`.

---

## XAI — Explainability Layer

**SHAP (SHapley Additive exPlanations) TreeExplainer** is used for all tree-based models. It computes each feature's contribution to the model's prediction using Shapley values from cooperative game theory.

```python
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X)
# Top-N features by |shap_value| → contributing_features dict
```

The top features by absolute SHAP value are surfaced in the dashboard `ExplanationPanel` as a horizontal bar chart, making the model's reasoning visible to operators.

### LSTM-AE Explainability
LSTM-AE does **not** support SHAP (`supports_tree_xai: false` in registry). When active, explanation degrades to a generic summary string — no per-feature attribution.

---

## Fallback Chain

In non-strict mode (`DTX_REPLAY_STRICT=0`), failures fall back gracefully:

```
ML model inference fails
    └─► Rule-based detector (threshold on raw readings)
            └─► Stub explanation text (no SHAP values)
```

In strict mode (`DTX_REPLAY_STRICT=1`), any failure raises an exception — used to validate the full pipeline end-to-end during dataset replay.

---

## Fault Classes

| Code | Name | Description |
|---|---|---|
| 0 | `no_fault` | Normal operating state |
| 1 | `bearing_fault` | Abnormal vibration — mechanical bearing degradation |
| 2 | `overheating` | Elevated temperature — thermal runaway or cooling failure |
| 3 | `combined` | Multiple sensor readings simultaneously elevated |
