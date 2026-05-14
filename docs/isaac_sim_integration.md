# Isaac Sim Integration Guide

Audience: the team wiring NVIDIA Isaac Sim into DTX-AI.

The training dataset (`services/ai/dtx_ai_master_dataset.csv`) is now produced
by Isaac Sim and matches the runtime API schema field-for-field. This guide
describes the contract in both directions and what an Isaac Sim build should
publish so the models do useful work.

---

## 1. The data contract

### Inbound — telemetry events

The API entry point is `POST /events/`. Every sensor field maps to a real
Isaac Sim sensor / joint reading; field names are identical to the dataset
CSV columns and to `services/ai/preprocessing.py:FEATURES`.

| Field                            | Unit          | Source in Isaac Sim |
|----------------------------------|---------------|---------------------|
| `imu_lin_acc_{x,y,z}`            | m/s²          | `ImuSensor` linear acceleration |
| `imu_ang_vel_{x,y,z}`            | rad/s         | `ImuSensor` angular velocity |
| `vibration_magnitude`            | m/s²          | scalar L2 of the IMU linear-accel vector |
| `lift_joint_position`            | m or rad      | `ArticulationView.get_joint_positions()` for the lift joint |
| `lift_force_z`                   | N             | force sensor on the lift joint |
| `lift_joint_velocity`            | m/s or rad/s  | `ArticulationView.get_joint_velocities()` |
| `pseudo_pressure_pa`             | Pa            | hydraulic proxy from the lift cylinder force |
| `drive_joint_velocity`           | rad/s         | drive joint velocity |
| `drive_joint_effort`             | N·m           | drive joint torque |
| `roller_{fl,fr,bl,br}_velocity`  | rad/s         | four wheel joint velocities |
| `power_dissipated_w`             | W             | sum of `effort * velocity` across drives |
| `temperature_c`                  | °C            | thermal solver on the motor housing |

`asset_id` and `zone_id` are free-form strings; use the Isaac Sim prim path
or any stable per-asset ID, and the warehouse cell name respectively.

Set `metadata.source = "isaac_sim"` on every event so the API can distinguish
sim events from replay or operator-injected events in the SQLite log.

### Outbound — twin updates

When the API confirms an anomaly it fires a fire-and-forget call to
`apps/sim/sim/adapter.py:notify(update)` with a `TwinUpdate` payload:

```python
TwinUpdate(
    event_id=UUID,
    asset_id=str,
    zone_id=str,
    new_status=AssetStatus,   # normal | degraded | fault | offline
    severity=Severity,        # info | warning | critical
    label=str,                # e.g. "bearing_wear / score=0.97"
    timestamp=datetime,
)
```

`adapter.notify()` is a stub today — it logs the update and, if
`ISAAC_SIM_ENABLED=true`, calls `sim.scene.update_asset_status(...)`. The
Isaac Sim team owns the body of `update_asset_status` (recolour the asset,
attach an overlay, trigger a maintenance animation, etc.).

### Event flow

```
┌────────────────────────────┐    19-channel JSON     ┌──────────────┐
│ scripts/replay_dataset_demo│───────────────────────▶│              │
│ (held-out tail of CSV)     │                        │              │
└────────────────────────────┘                        │   POST       │
┌────────────────────────────┐                        │  /events/    │── runtime model ──▶ DashboardAlert
│ Isaac Sim adapter (you)    │───────────────────────▶│              │                       │
└────────────────────────────┘                        │              │            TwinUpdate ▼
                                                      └──────────────┘            ──▶ Isaac Sim
                                                                                    (round-trip)
```

---

## 2. The 6 fault classes the model knows

| Code | Label             | Discriminating signals (per training-data means) |
|------|-------------------|--------------------------------------------------|
| 0 | `nominal`         | `power_dissipated_w` ≈ 0, `temperature_c` ≈ 25, rollers ≈ 0 |
| 1 | `bearing_wear`    | `power_dissipated_w` ≈ 300, `drive_joint_effort` slightly lower than nominal |
| 2 | `overheat`        | `temperature_c` ≈ 49, `power_dissipated_w` ≈ 2000, rollers ≈ 0.6, `pseudo_pressure_pa` ≈ +2500 |
| 3 | `overload`        | `power_dissipated_w` ≈ 30, otherwise close to nominal |
| 4 | `pressure_fault`  | `pseudo_pressure_pa` ≈ −8500, `lift_force_z` ≈ −685, `lift_joint_position` ≈ 1.9 |
| 5 | `wheel_slip`      | rollers ≈ 0.7, `drive_joint_velocity` ≈ 0.37, `temperature_c` ≈ 52, `power_dissipated_w` ≈ 1160 |

To drive a class from Isaac Sim, change the underlying physics so the
relevant signals end up in that class's envelope. Examples:

- **bearing_wear** — add a small friction term on a bearing joint that costs
  ~300 W of dissipation but otherwise leaves kinematics intact.
- **overheat** — degrade cooling on the drive motor until `temperature_c`
  drifts above ~45 °C while the asset is loaded.
- **overload** — instantiate a heavier payload than the asset is rated for;
  drive effort and power dissipation both climb modestly.
- **pressure_fault** — clamp the lift cylinder so it cannot extend; the
  pseudo-pressure proxy goes deeply negative and the lift force inverts.
- **wheel_slip** — drop the friction coefficient between the rollers and the
  ground; rollers spin faster than the drive commands.

Real-world noise + drift should be injected on top of every regime (white
Gaussian on every channel at ~1 % of nominal range, occasional sensor
dropouts published as `null`, gradual ramps over 30–120 s rather than step
changes).

Cadence: 1 Hz is plenty. The runtime classifier scores single events
independently; there is no sequence-length requirement.

---

## 3. What is still wrong with the dataset

The new dataset is a clear improvement over the previous toy CSV — it uses
real Isaac-Sim-style channels and real fault physics — but the models still
score F1 ≈ 1.0 on a held-out 20 % test split. That number is suspicious for
the same reasons as before. Concretely:

### 3.1 Rows are still sorted by label

`fault_label` lives in 6 contiguous 1 800-row blocks across `timestamp_s`.
A random `train_test_split` consequently sees adjacent rows in train and
test, which leaks per-class behaviour. Use the chronological split
(`scripts/replay_dataset_demo.py:chronological_split`) for honest evaluation;
the training script intentionally mirrors the notebook's stratified-random
split so the numbers match the notebook one-for-one.

### 3.2 Per-class signatures barely overlap

The means listed in §2 are far apart relative to the within-class variance.
A 3-deep decision stump on `(power_dissipated_w, pseudo_pressure_pa,
roller_fl_velocity)` already separates most pairs. The classifier isn't
really doing hard work yet.

### 3.3 No fault precursors

Real bearing wear ramps up over weeks; overheating builds over minutes.
The CSV jumps directly from `nominal` to a steady fault state with no
transition region. Whichever class is currently driving the asset, the
sensors are squarely in that class's envelope — no ambiguous events exist.

### 3.4 No mixed faults

A wheel slipping at high temperature isn't in the training distribution —
there is no `wheel_slip + overheat` regime. When Isaac Sim eventually
simulates compound faults the model will collapse to whichever class is
closest and report it with high confidence; this is a known limitation of
single-label multiclass and is not a bug.

### 3.5 No environmental noise

Vibration magnitude in the CSV is essentially constant (~9.81 ≈ g, since the
asset is at rest under gravity). Real telemetry has a noise floor; the model
has not learned to ignore it.

---

## 4. Concrete next steps

### For the dataset

1. **Add small Gaussian noise to every channel** (σ ≈ 1 % of nominal range)
   plus rare 5–10 σ outliers (~0.5 % of ticks) to teach the model to ignore
   sensor noise vs sustain. The current zero-variance vibration column is
   the obvious tell.
2. **Insert ramp-up and ramp-down regions between faults** so train and test
   see ambiguous near-boundary events. Without these the F1=1.0 result is
   meaningless.
3. **Simulate at least one compound fault scenario** even if only as a
   diagnostic — overheat + bearing_wear is a natural pair (an overheating
   bearing accelerates wear).
4. **Re-train with a chronological split** rather than the notebook's
   stratified-random one. Drop F1 to whatever it actually is. If it drops
   below 0.9, you finally have a model worth tuning.
5. **Optionally re-include `Zone` or an equivalent categorical** if your
   sim emits one — the current FEATURES list is purely numeric, but
   per-zone behaviour could be informative.

### For Isaac Sim integration

In rough order of difficulty:

1. **Implement `apps/sim/sim/scene.update_asset_status`** — read
   `asset_id` / `zone_id` / `status` / `severity` and recolour the asset
   in the scene. `notify()` already routes to it.
2. **Build the sim → API bridge.** Walk Isaac Sim's per-asset sensor outputs
   at 1 Hz and POST them to `/events/` with all 19 channels. The minimal
   reference is
   [`scripts/replay_dataset_demo.py:build_event_payload + post_event`](../scripts/replay_dataset_demo.py).
3. **Drive the 6 fault regimes** from named demo scenarios (e.g.
   `--scenario overheat`) so the dashboard shows a coherent story.
4. **Stamp `metadata.source = "isaac_sim"`** plus `metadata.scenario` and
   any sim run-ID on every POST.
5. **Wire operator actions back into the sim** if you want bidirectional
   feedback — `POST /alerts/{id}/actions` already persists them and the
   dashboard surfaces them via `GET /alerts`.

Owners: the Isaac Sim team. The ML / API team will keep
[`packages/shared/schemas.py`](../packages/shared/schemas.py),
[`apps/sim/sim/adapter.py`](../apps/sim/sim/adapter.py), and the model
artifacts stable while you build against them.
