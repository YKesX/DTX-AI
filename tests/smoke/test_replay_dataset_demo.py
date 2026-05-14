import importlib.util
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "replay_dataset_demo.py"
spec = importlib.util.spec_from_file_location("replay_dataset_demo", SCRIPT_PATH)
replay = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(replay)


def test_chronological_split_helper_still_works():
    """Kept around as a backwards-compat shim — the demo no longer uses it."""
    df = pd.DataFrame({"timestamp_s": [float(i) for i in range(10)]})
    splits = replay.chronological_split(df, test_ratio=0.2)
    assert len(splits["train"]) == 8
    assert len(splits["test"]) == 2
    assert splits["train"]["timestamp_s"].is_monotonic_increasing
    assert splits["test"]["timestamp_s"].is_monotonic_increasing


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
