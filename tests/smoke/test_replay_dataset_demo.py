import importlib.util
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "replay_dataset_demo.py"
spec = importlib.util.spec_from_file_location("replay_dataset_demo", SCRIPT_PATH)
replay = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(replay)


def test_holdout_never_overlaps_training_pool():
    """The canonical demo holdout must share zero rows with the training
    pool, and within every episode the closest pool frame must be at least
    one purge gap away — this is the data-leakage regression guard."""
    import sys
    ai_root = Path(__file__).resolve().parents[2] / "services" / "ai"
    if str(ai_root) not in sys.path:
        sys.path.insert(0, str(ai_root))
    from preprocessing import (
        PURGE_GAP_ROWS,
        episode_groups,
        load_data,
        split_demo_pool_and_holdout,
    )

    df = load_data(str(ai_root / "dtx_ai_master_dataset.csv"))
    pool, holdout = split_demo_pool_and_holdout(df)

    pool_ts = set(pool["timestamp_s"])
    holdout_ts = set(holdout["timestamp_s"])
    assert not pool_ts & holdout_ts, "pool and holdout share rows"

    # Median sample period — the purge gap must hold in time units too.
    dt = float(df["timestamp_s"].diff().median())
    work = df.copy()
    work["_g"] = episode_groups(df).values
    for _, seg in work.groupby("_g"):
        last_pool = seg[seg["timestamp_s"].isin(pool_ts)]["timestamp_s"].max()
        first_holdout = seg[seg["timestamp_s"].isin(holdout_ts)]["timestamp_s"].min()
        if pd.notna(last_pool) and pd.notna(first_holdout):
            assert first_holdout - last_pool >= PURGE_GAP_ROWS * dt * 0.9, (
                f"purge gap violated: {first_holdout - last_pool:.3f}s"
            )


def test_build_event_payload_contains_replay_metadata():
    row = pd.Series({
        "_source_row_id": 42,
        "timestamp_s": 123.456,
        "fault_label": 1,
        "fault_label_name": "bearing_wear",
        "imu_lin_acc_x": -9.77, "imu_lin_acc_y": 0.0, "imu_lin_acc_z": 0.86,
        "imu_ang_vel_x": 0.0, "imu_ang_vel_y": 0.0, "imu_ang_vel_z": 0.0,
        "vibration_magnitude": 9.82,
        "lift_joint_position": -0.15, "lift_force_z": -0.44, "lift_joint_velocity": 0.0,
        "pseudo_pressure_pa": -5.56,
        "drive_joint_velocity": 0.0, "drive_joint_effort": 2812.0,
        "roller_fl_velocity": 0.01, "roller_fr_velocity": 0.0,
        "roller_bl_velocity": 0.01, "roller_br_velocity": 0.0,
        "power_dissipated_w": 299.0,
        "temperature_c": 27.2,
    })
    payload = replay.build_event_payload(
        row, replay_index=3, split="holdout", model="lightgbm", strict=True,
    )

    metadata = payload["metadata"]
    assert metadata["source"] == "dataset_replay"
    assert metadata["dataset"] == "dtx_ai_master_dataset"
    assert metadata["row_id"] == 42
    assert metadata["split"] == "holdout"
    assert metadata["ground_truth_name"] == "bearing_wear"
    assert metadata["active_model"] == "lightgbm"
    assert metadata["replay_strict"] is True
    assert payload["temperature_c"] == 27.2
    assert payload["lift_force_z"] == -0.44


def test_prepare_replay_rows_holdout_is_stratified_across_classes():
    """The default 'holdout' split must cover every fault class so a small
    --limit run still demonstrates predictions on the full class vocabulary."""
    rows = replay.prepare_replay_rows(split="holdout", limit=None, shuffle=False)
    classes_seen = set(rows["fault_label_name"].unique())
    expected = {
        "nominal", "bearing_wear", "overheat",
        "overload", "pressure_fault", "wheel_slip",
    }
    assert classes_seen == expected, f"holdout missing classes: {expected - classes_seen}"


def test_prepare_replay_rows_shuffle_covers_multiple_classes_in_first_30():
    """With shuffle=True (the demo's default), even a 30-row replay should
    hit several distinct classes — guards against the old chronological-tail
    behaviour where the first N rows were a single contiguous label block."""
    rows = replay.prepare_replay_rows(
        split="holdout", limit=30, shuffle=True, shuffle_seed=42,
    )
    classes_in_first_30 = set(rows["fault_label_name"].unique())
    assert len(classes_in_first_30) >= 4


def test_prepare_replay_rows_supports_honest_split_modes():
    episode_rows = replay.prepare_replay_rows(
        split="episode_holdout", limit=30, shuffle=True, shuffle_seed=42,
    )
    temporal_rows = replay.prepare_replay_rows(
        split="temporal", limit=30, shuffle=False,
    )

    assert len(episode_rows) == 30
    assert len(temporal_rows) == 30
    assert "_episode_group" in episode_rows.columns
    assert "_episode_group" in temporal_rows.columns
