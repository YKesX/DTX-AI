# DTX-AI v3.0 Final — AI and XAI Pipeline

`ai.pipeline.run_pipeline(event)` runs inference and explanation inside the
FastAPI process. The registry supports Random Forest, LightGBM, XGBoost,
TabNet, CNN, Bi-LSTM, and LSTM-AE with a classifier head.

- `preprocessing.py`: canonical 19 features, six classes, and temporal splits.
- `ai/model_loader.py`: registry-based artifact loading and caching.
- `ai/detector.py`: model dispatch, window buffering, and rule-based fallback.
- `ai/explainer.py` and `ai/xai_explainer.py`: explanations and tree-model SHAP.
- `ai/models/`: trained artifacts, scalers, metadata, leaderboard, and baselines.
- `dtx_ai_master_dataset.csv`: reproducible training and replay dataset.
- `dtxai_model_training.ipynb`: retained training experiment record.

Install dependencies using `scripts/setup.sh` from the repository root.
PyTorch is installed separately as described in `requirements.txt`.
Start the full application with `bash scripts/run_dev.sh`; retrain with
`python scripts/train_models.py`. Strict replay requires the selected model
to load and disables silent fallback.

See [dataset limitations](../../docs/dataset_limitations.md) and
[usage](../../docs/current_usage.md) for interpretation and runtime commands.
