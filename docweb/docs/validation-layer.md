---
id: validation-layer
title: Validation Layer
sidebar_position: 9
---

# Validation Layer

The repo ships with two demo/validation modes: a **dataset replay mode** that proves trained models are driving outputs by replaying the leakage-safe demo holdout of the training dataset and tracking ground-truth vs prediction accuracy in real time, and a **hardware demo mode** that streams live ESP32 sensor readings through the same pipeline.

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

The default `holdout` split is **leakage-safe**: the dataset is ~60 Hz telemetry, so neighbouring rows are near-duplicates and a row-level random holdout would effectively replay training data. The demo holdout is instead the **last 20% of every contiguous fault run**, with a 60-row purge gap (~1.02 s minimum separation) dropped between the training pool and the holdout, so no replayed frame was seen — or is even adjacent to a frame seen — during training.

```bash
# Dashboard demo: the leakage-safe per-episode temporal demo holdout (shuffled for display)
python scripts/replay_dataset_demo.py --model lightgbm

# Grouped validation: hold out complete episodes/runs
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

## Hardware Demo Mode (IRL / ESP32)

The second demo mode streams **live sensor readings** from the ESP32 hardware node (`HW/` — DS18B20 temperature + BMP280 pressure) into the same `POST /events/` pipeline via `scripts/hw_demo_bridge.py`. The bridge uses the two real channels (`temperature_c`, `pseudo_pressure_pa` as a baseline-deviation × gain), derives `power_dissipated_w` from the temperature delta, and synthesizes the remaining 16 channels from nominal training-pool statistics. Hardware events carry `metadata.source = "hardware_demo"`, have no ground-truth labels, and therefore do not contribute to replay-accuracy metrics. See the [Hardware Demo guide](/docs/hardware-demo) for wiring, firmware, and bridge details.

---

## Demo Orchestration API & Dashboard Panel

Both demo modes can be started from the dashboard. The AI Validation page has a **Demo Control** panel (`apps/dashboard/src/components/validation/DemoControlPanel.jsx`) that lets you choose **Dataset demo** vs **IRL demo (ESP32)**, pick the model, split, and event count, start/stop the run, and watch the demo log live.

Under the hood it calls the `/demo` routes (`apps/api/api/routes/demo.py`), which spawn `scripts/replay_dataset_demo.py` or `scripts/hw_demo_bridge.py` as a subprocess — only one demo runs at a time:

| Endpoint | Purpose |
|---|---|
| `GET /demo/models` | Enabled model registry keys for the selector |
| `GET /demo/status` | `running`, `mode`, `params`, `started_at`, `returncode`, `log_tail` |
| `POST /demo/start` | Start a dataset or hardware demo (409 if one is already running) |
| `POST /demo/stop` | Terminate the running demo process |

See the [API Reference](/docs/api-reference) for full request/response shapes.

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
| `DemoControlPanel` | Start/stop the dataset or IRL (ESP32) demo, choose model/split/count, live demo log |
| `ReplaySummaryCards` | Total events / Correct predictions / Accuracy % |
| `ClassDistributionCharts` | GT vs Predicted bar charts |
| `ConfusionMatrix` | Dynamic table — cross-class prediction errors |
| `ReplayEventTable` | Recent demo events with GT/prediction + correct/incorrect badge — includes both `dataset_replay` and `hardware_demo` sources |

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
