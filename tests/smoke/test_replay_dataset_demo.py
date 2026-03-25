import importlib.util
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "replay_dataset_demo.py"
spec = importlib.util.spec_from_file_location("replay_dataset_demo", SCRIPT_PATH)
replay = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(replay)


def test_chronological_split_keeps_order():
    df = pd.DataFrame({"Timestamp": pd.date_range("2026-01-01", periods=10, freq="h")})
    splits = replay.chronological_split(df, test_ratio=0.2)
    assert len(splits["train"]) == 8
    assert len(splits["test"]) == 2
    assert splits["train"]["Timestamp"].is_monotonic_increasing
    assert splits["test"]["Timestamp"].is_monotonic_increasing


def test_build_event_payload_contains_replay_metadata():
    row = pd.Series(
        {
            "_source_row_id": 42,
            "Timestamp": pd.Timestamp("2026-03-25T10:00:00Z"),
            "Fault Label": 1,
            "Vibration (mm/s)": 12.3,
            "Temperature (°C)": 65.2,
            "Pressure (bar)": 9.9,
            "Machine ID": "machine-01",
            "Warehouse Section": "zone-A",
        }
    )
    payload = replay.build_event_payload(
        row,
        replay_index=3,
        split="test",
        source="ziya",
        model="random_forest",
        strict=True,
    )

    metadata = payload["metadata"]
    assert metadata["source"] == "dataset_replay"
    assert metadata["dataset"] == "ziya"
    assert metadata["row_id"] == 42
    assert metadata["split"] == "test"
    assert metadata["ground_truth_name"] == "bearing_fault"
    assert metadata["active_model"] == "random_forest"
    assert metadata["replay_strict"] is True
