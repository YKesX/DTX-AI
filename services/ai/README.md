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

## T5 explanations

For LSTM-AE only, the fine-tuned **T5-small** model in `ai/t5_inference.py` generates the text shown in the dashboard's
Explanation panel. Install the AI requirements and place the fine-tuned model
and tokenizer files in `services/ai/ai/models/t5_explainer/`, or set
`DTX_T5_MODEL_DIR` to their folder before starting the API. Select `lstm_ae`
for replay (or set `DTX_ACTIVE_MODEL=lstm_ae`). Restart the API after installing
weights because model loading is cached. Weights are distributed separately.

The panel labels generated text **T5 explainer**, and labels unavailable or
failed generation **LSTM-AE fallback**. Text and source survive a page reload.
Tree models continue to use SHAP. T5 prose is generated from model signals;
it is not per-feature attribution.

Download the [T5-small weights](https://drive.google.com/file/d/1JCeTJRhcbobWKzRL9DFbOj1nA2INiSvv/view) and extract the `t5_explainer` folder under `services/ai/ai/models/`. The weights remain excluded from Git.
