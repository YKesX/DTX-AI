---
id: validation-layer
title: Validation Layer
sidebar_position: 9
---

# Validation Layer

The repo ships with a **dataset replay validation mode** that proves trained models are driving outputs by replaying held-out rows of the Isaac-Sim-style training dataset and tracking ground-truth vs prediction accuracy in real time.

---

## Dataset Replay Mode

The replay system feeds rows from `services/ai/dtx_ai_master_dataset.csv`
through the live `POST /events/` endpoint. Each row includes a
`ground_truth_label` (numeric class code) and `ground_truth_name` (canonical
class string) in the `metadata` field, which the API uses to update accuracy
counters **without bypassing the real inference pipeline**.

:::info Key Design Decision
Replay events travel through the **identical code path** as Isaac Sim events. There is no separate mock inference path — this validates the full stack end-to-end.
:::

```bash
# Pretty dashboard demo: shuffled stratified holdout
python scripts/replay_dataset_demo.py --model lightgbm

# Honest grouped validation: hold out complete episodes/runs
python scripts/replay_dataset_demo.py --model lightgbm --split episode_holdout

# Drift check: chronological tail
python scripts/replay_dataset_demo.py --model lightgbm --split temporal

# Strict mode — model + class_mapping must load
python scripts/replay_dataset_demo.py --model lightgbm --strict --limit 500
```

Or the bundled orchestrator that also boots the API and dashboard:

```bash
bash scripts/run_demo.sh --model lightgbm --count 200 --strict-replay
```

---

## LiveReplayMetrics Singleton

`apps/api/api/live_metrics.py` — thread-safe in-memory singleton tracking:

| Counter | Description |
|---|---|
| `total_replayed` | Events processed in this session with `metadata.source = "dataset_replay"` |
| `total_correct` | Events where `predicted_label == normalize_gt_label(ground_truth_label)` |
| `running_accuracy` | Running float (`total_correct / total_replayed`) |
| `per_class_ground_truth` | Distribution of GT labels |
| `per_class_predicted` | Distribution of predicted labels |
| `confusion_counts` | `{gt_label}->{pred_label}` keyed counts |
| `per_model` | Events processed per model family |
| `last_updated` | ISO timestamp of the most recent update |

Resets on `DELETE /alerts/clear`. Exposed read-only at `GET /metrics/live`.

---

## Strict Replay Mode

When `DTX_REPLAY_STRICT=1` or the `--strict` flag is set, the runtime:

- Loads only the requested model (no fall-through to other registry entries)
- Refuses to serve LSTM-AE without a `class_mapping` block in its metadata
- Propagates any inference exception instead of falling back to the rule-based stub

Used to prove the full pipeline is functional without any fallbacks masking issues.

---

## Validation Dashboard (`/validation`)

The Validation page polls `GET /metrics/live` every 4 seconds and renders:

| Component | What it shows |
|---|---|
| `ReplaySummaryCards` | Total events / Correct predictions / Accuracy % |
| `ClassDistributionCharts` | GT vs Predicted bar charts |
| `ConfusionMatrix` | Dynamic table — cross-class prediction errors |
| `ReplayEventTable` | Recent replay events with GT/prediction + correct/incorrect badge |

---

## Operator Workflow Validation

The replay flow also exercises the full operator action workflow:

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
| `assignee` | Max 120 characters; the API stores it only for the `ASSIGN` action |
