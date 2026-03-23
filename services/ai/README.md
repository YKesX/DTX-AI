# services/ai — Anomaly Detection & XAI Pipeline

## Responsibilities
- Score warehouse events with an anomaly detection model
- Generate plain-language explanations via XAI (SHAP stub)
- Expose `run_pipeline(event)` as the single callable for apps/api

## Structure

```
services/ai/
├── ai/
│   ├── pipeline.py      # Orchestration entry point
│   ├── detector.py      # Anomaly detection model (stub → real model)
│   └── explainer.py     # XAI explanation generator (stub → SHAP)
├── requirements.txt
└── README.md
```

## Running standalone (for testing)

```bash
cd services/ai
pip install -r requirements.txt
python -m ai.pipeline
```
