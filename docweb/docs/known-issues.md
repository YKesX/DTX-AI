---
id: known-issues
title: Release Scope & Limitations
sidebar_position: 13
---

# v3.0 Final — Release Scope & Limitations

The final release includes Dashboard, Events, AI Validation, Settings,
dataset replay, and ESP32 hardware ingestion. The application is intended
for a local capstone demonstration.

## Model and dataset boundaries

The canonical per-episode temporal split uses a 60-row purge gap. All seven
model families have recorded validation and holdout metrics. High scores
reflect strongly separated class signatures; they do not establish performance
on arbitrary real equipment. Fault transitions, compound faults, and realistic
environmental noise are limited in the supplied dataset. See the retained
[dataset limitations](https://github.com/YKesX/DTX-AI/blob/main/docs/dataset_limitations.md).

Tree models support SHAP feature attribution. Deep models use model-specific
fallback explanations; full per-feature deep-model SHAP is not implemented.
Historical alerts retain explanation text but not all live SHAP feature values.

## Hardware boundaries

The DS18B20 supplies temperature and the BMP280 supplies barometric pressure.
Other model inputs are derived or synthesized, as recorded in event metadata.
Hardware predictions have no ground-truth accuracy metric. Both-sensor failures
skip event submission; partial failures identify synthesized replacements.
Firmware builds do not substitute for testing wiring and sensor behavior on a board.

## Runtime boundaries

- The simulator adapter and position playback are retained. Scene hooks currently log updates and require host USD integration.
- T5 explanations require the separately distributed fine-tuned model files. Without them, the UI labels the LSTM-AE fallback.
- Event history requests return at most the latest 200 records.
- Browser preferences are local to that browser and are not account settings.
- SQLite and in-process inference target local workloads.
- The API has permissive development CORS and no production authentication.
- PyTorch is installed separately as documented in setup instructions.
- Model artifacts depend on the library versions in the requirements files.
