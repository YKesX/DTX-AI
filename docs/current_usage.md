# Current Usage (Software Demo Path)

This guide covers the **current demoable software stack** (no Isaac Sim required).

## 1) Setup

```bash
cd DTX-AI
bash scripts/setup.sh
```

This creates `.venv`, installs Python dependencies, installs dashboard packages, and copies `.env` files from examples.

## 2) One-command demo path

```bash
bash scripts/run_demo.sh --scenario mixed --count 10 --delay 0.8
```

Useful flags:

- `--setup` run setup first
- `--model lightgbm|random_forest|xgboost|lstm_ae`
- `--scenario normal|bearing_fault|overheating|combined|mixed|gradual_drift|intermittent_spike`
- `--no-seed` start API + dashboard only

## 3) Manual service startup (optional)

```bash
bash scripts/run_dev.sh
```

- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:5173

## 4) Run scenario generation directly

```bash
python scripts/seed_demo_events.py --scenario mixed --count 10 --delay 0.8
```

## 5) Model selection and behavior

- Active model comes from `services/ai/ai/models/shared/model_registry.json` (`active_model`), unless overridden by `DTX_ACTIVE_MODEL`.
- Supported runtime families in this stage:
  - LightGBM
  - RandomForest
  - XGBoost
  - LSTM-AE
- If a selected model artifact/dependency cannot be loaded, runtime falls back to another enabled model from registry.
- If no configured model can be loaded, runtime falls back to the safe rule-based detector so demo flow still works.
- LSTM-AE threshold behavior is explicit:
  - if `default_threshold` is present in metadata, it is used
  - if missing, runtime falls back cleanly (no fake threshold)

## 6) Artifact locations

- Registry and shared files:
  - `services/ai/ai/models/shared/model_registry.json`
  - `services/ai/ai/models/shared/feature_order.json`
  - `services/ai/ai/models/shared/scaler.pkl`
- Model artifacts + metadata:
  - `services/ai/ai/models/lightgbm/`
  - `services/ai/ai/models/random_forest/`
  - `services/ai/ai/models/xgboost/`
  - `services/ai/ai/models/lstm_ae/`

## 7) What remains for later stages

- Isaac Sim integration into the end-to-end live path
- hardware sensor ingestion (ESP32 or equivalent)
- unified train/validation evaluation protocol across all model families
