---
id: validation-layer
title: Validation Layer
sidebar_position: 9
---

# Validation Layer — `feat/dashboard-ops-validation`

This branch introduces a **dataset replay validation mode** that proves trained models are driving outputs by replaying held-out chronological rows and tracking ground-truth vs prediction accuracy in real time.

---

## Dataset Replay Mode

The replay system feeds held-out rows from the Kaggle predictive-maintenance dataset through the live `POST /events/` endpoint. Each row includes a `ground_truth_label` in the `metadata` field, which the API uses to update accuracy counters **without bypassing the real inference pipeline**.

:::info Key Design Decision
Replay events travel through the **identical code path** as real sensor events. There is no separate mock inference path — this validates the full stack end-to-end.
:::

```bash
# Run replay with LightGBM
python scripts/replay_dataset_demo.py --model lightgbm

# Strict mode — no fallbacks
python scripts/replay_dataset_demo.py --model lightgbm --strict
```

---

## LiveReplayMetrics Singleton

`live_metrics.py` — thread-safe in-memory singleton tracking:

| Counter | Description |
|---|---|
| `total_events` | Total events processed in this session |
| `correct_predictions` | Events where `predicted_label == ground_truth_name` |
| `accuracy` | Running float (`correct / total`) |
| `per_class_ground_truth` | Distribution of GT labels |
| `per_class_predicted` | Distribution of predicted labels |
| `confusion_matrix` | `dict[gt_label][pred_label] → count` |
| `per_model_counts` | Events processed per model family |

Resets on `DELETE /alerts/clear`. Exposed read-only at `GET /metrics/live`.

---

## Strict Replay Mode

When `DTX_REPLAY_STRICT=1` or `--strict` flag is passed:

- The **requested model must load** — `ImportError` or missing artifact fails hard
- **SHAP must succeed** — no fallback explanation text allowed
- **LSTM-AE must have** `default_threshold` configured in `metadata.json`

Used to prove the full pipeline is functional without any fallbacks masking issues.

---

## Validation Dashboard (`/validation`)

The Validation page polls `GET /metrics/live` every 4 seconds and renders:

| Component | What it shows |
|---|---|
| `ReplaySummaryCards` | Total events / Correct predictions / Accuracy % |
| `ClassDistributionCharts` | GT label distribution vs Predicted distribution bar charts |
| `ConfusionMatrix` | Dynamic table — cross-class prediction errors |
| `ReplayEventTable` | Recent replay events with GT/prediction + correct/incorrect badge |

---

## Operator Workflow Validation

The branch also validates the full operator action workflow:

```
Alert created
    └─► ACKNOWLEDGE  (operator confirms they see the alert)
            └─► ASSIGN  (assigned to a named operator)
                    └─► ESCALATE  (flagged for senior review)
                            └─► RESOLVE  (marked resolved)
```

Each action creates an `AlertActionRecord` in the `event_actions` SQLite table.

`GET /alerts/{event_id}/actions` returns:
- Full action history
- Derived `AlertOperatorState` (current workflow position)

### Validation Constraints

| Field | Constraint |
|---|---|
| `action_type` | Must be a valid `AlertActionType` enum value |
| `note` | Max 500 characters |
| `assignee` | Max 120 characters (required for `ASSIGN` action) |
