#!/usr/bin/env python3
"""Replay held-out dataset rows through POST /events for validation demo mode."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from socket import timeout as SocketTimeout
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
ai_path = str(REPO_ROOT / "services" / "ai")
if ai_path not in sys.path:
    sys.path.insert(0, ai_path)

# Verify the preprocessing module exists before importing
preprocessing_file = Path(ai_path) / "preprocessing.py"
if not preprocessing_file.exists():
    raise ImportError(f"preprocessing module not found at {preprocessing_file}")

from preprocessing import engineer_features, load_data  # noqa: E402

try:
    from ai.model_loader import load_runtime_model
except Exception:  # pragma: no cover - optional preflight dependency
    load_runtime_model = None


LABEL_MAP = {
    "0": "no_fault",
    "1": "bearing_fault",
    "2": "overheating",
    0: "no_fault",
    1: "bearing_fault",
    2: "overheating",
    "no_fault": "no_fault",
    "bearing_fault": "bearing_fault",
    "overheating": "overheating",
    "normal": "no_fault",
}


def normalize_label(value: Any) -> str:
    raw = str(value).strip().lower()
    return LABEL_MAP.get(raw, raw)


def chronological_split(df: pd.DataFrame, test_ratio: float = 0.2) -> dict[str, pd.DataFrame]:
    if df.empty:
        return {"train": df.copy(), "test": df.copy(), "all": df.copy()}
    split_idx = max(1, int(len(df) * (1.0 - test_ratio)))
    split_idx = min(split_idx, len(df) - 1) if len(df) > 1 else 1
    train = df.iloc[:split_idx].copy().reset_index(drop=True)
    test = df.iloc[split_idx:].copy().reset_index(drop=True)
    return {"train": train, "test": test, "all": df.copy().reset_index(drop=True)}


def prepare_replay_rows(source: str = "ziya", split: str = "test", limit: int | None = None) -> pd.DataFrame:
    if source != "ziya":
        raise ValueError(f"Unsupported source '{source}'. Only 'ziya' is currently supported.")

    raw_df = load_data().copy()
    raw_df["_source_row_id"] = raw_df.index.astype(int)
    feat_df = engineer_features(raw_df, window=5)

    if "Fault Label" not in feat_df.columns:
        raise ValueError("Dataset is missing required column: Fault Label")

    split_df = chronological_split(feat_df).get(split)
    if split_df is None:
        raise ValueError(f"Unsupported split '{split}'. Use train, test, or all.")

    split_df = split_df.sort_values("Timestamp").reset_index(drop=True)
    if limit is not None:
        split_df = split_df.iloc[: max(limit, 0)].copy()
    return split_df


def _value(row: pd.Series, candidates: list[str], default: Any = None) -> Any:
    for name in candidates:
        if name in row and pd.notna(row[name]):
            return row[name]
    return default


def build_event_payload(
    row: pd.Series,
    *,
    replay_index: int,
    split: str,
    source: str,
    model: str,
    strict: bool,
) -> dict[str, Any]:
    ground_truth_raw = row.get("Fault Label")
    ground_truth_name = normalize_label(ground_truth_raw)

    asset = _value(row, ["Machine ID", "Asset ID", "asset_id"], default="dataset-machine")
    zone = _value(row, ["Warehouse Section", "Zone", "zone_id"], default="dataset-zone")

    vibration = float(_value(row, ["Vibration (mm/s)", "vibration"], default=0.0))
    temperature = float(_value(row, ["Temperature (°C)", "temperature"], default=0.0))
    pressure = float(_value(row, ["Pressure (bar)", "pressure"], default=0.0))

    humidity_value = _value(row, ["Humidity (%)", "humidity"], default=None)
    humidity = float(humidity_value) if humidity_value is not None else None

    timestamp = row.get("Timestamp")
    if hasattr(timestamp, "isoformat"):
        timestamp = timestamp.isoformat()
    else:
        timestamp = str(timestamp)

    return {
        "asset_id": str(asset),
        "zone_id": str(zone),
        "timestamp": timestamp,
        "vibration": vibration,
        "temperature": temperature,
        "humidity": humidity,
        "pressure": pressure,
        "metadata": {
            "source": "dataset_replay",
            "dataset": source,
            "row_id": int(row.get("_source_row_id", replay_index - 1)),
            "replay_index": replay_index,
            "split": split,
            "ground_truth_label": str(ground_truth_raw),
            "ground_truth_name": ground_truth_name,
            "active_model": model,
            "replay_strict": bool(strict),
        },
    }


def post_event(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{base_url}/events/",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def fetch_live_metrics(base_url: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"{base_url}/metrics/live", timeout=10) as resp:
        return json.loads(resp.read())


def wait_for_api(base_url: str, timeout_sec: float = 20.0) -> None:
    deadline = time.time() + max(timeout_sec, 0.0)
    health_url = f"{base_url}/health"
    last_err = "unknown"

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=2) as resp:
                if resp.status == 200:
                    return
                last_err = f"HTTP {resp.status}"
        except (urllib.error.URLError, SocketTimeout) as exc:
            last_err = f"{type(exc).__name__}: {exc}"
        time.sleep(0.5)

    raise RuntimeError(
        f"API is not reachable at {health_url}. "
        f"Start backend first (e.g. bash scripts/run_dev.sh). Last error: {last_err}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay dataset rows through the real DTX-AI API path.")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--model", default="lightgbm", help="Active model key to request")
    parser.add_argument("--split", default="test", choices=["train", "test", "all"], help="Replay split")
    parser.add_argument("--limit", type=int, default=100, help="Maximum rows to replay")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests (seconds)")
    parser.add_argument("--source", default="ziya", help="Dataset source identifier")
    parser.add_argument("--strict", action="store_true", help="Enable strict real-model replay validation")
    parser.add_argument(
        "--wait-timeout",
        type=float,
        default=20.0,
        help="Seconds to wait for API /health before replay starts",
    )
    return parser.parse_args()


def preflight_requested_model(model_key: str, strict: bool) -> None:
    if load_runtime_model is None:
        print(
            "Warning: local model preflight unavailable; could not import ai.model_loader.",
            file=sys.stderr,
        )
        return

    runtime = load_runtime_model(requested_model=model_key, strict_selection=True)
    if runtime.available:
        print(f"Model preflight OK: requested={model_key} runtime={runtime.key}")
        return

    message = (
        f"Requested model '{model_key}' is unavailable in current environment. "
        f"Reason: {runtime.reason}"
    )
    if strict:
        raise RuntimeError(message)

    print(
        f"Warning: {message}\n"
        "Replay may fallback to another model (often random_forest). "
        "Use --strict to fail fast.",
        file=sys.stderr,
    )


def main() -> None:
    args = parse_args()

    try:
        preflight_requested_model(args.model, args.strict)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(3)

    try:
        wait_for_api(args.url, timeout_sec=args.wait_timeout)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)

    rows = prepare_replay_rows(source=args.source, split=args.split, limit=args.limit)
    if rows.empty:
        print("No rows available for replay with current split/limit.", file=sys.stderr)
        sys.exit(1)

    print(
        f"Dataset replay started: source={args.source} split={args.split} "
        f"rows={len(rows)} model={args.model} strict={int(args.strict)}"
    )

    ok = 0
    failed = 0
    for i, (_, row) in enumerate(rows.iterrows(), start=1):
        payload = build_event_payload(
            row,
            replay_index=i,
            split=args.split,
            source=args.source,
            model=args.model,
            strict=args.strict,
        )
        try:
            response = post_event(args.url, payload)
            metadata = (response.get("event") or {}).get("metadata") or {}
            pred = metadata.get("predicted_label", "?")
            gt = metadata.get("ground_truth_name", "?")
            correct = metadata.get("prediction_correct")
            runtime_model = metadata.get("runtime_model", "?")
            score = (response.get("anomaly") or {}).get("anomaly_score", 0.0)
            ok += 1
            print(
                f"[{i:>4}/{len(rows)}] model={runtime_model:<14} gt={gt:<14} "
                f"pred={pred:<14} score={float(score):.4f} correct={correct}"
            )
        except urllib.error.HTTPError as exc:
            failed += 1
            detail = exc.read().decode("utf-8", errors="ignore")
            print(f"[{i:>4}/{len(rows)}] HTTP {exc.code}: {detail}", file=sys.stderr)
            if args.strict:
                sys.exit(1)
        except Exception as exc:  # pragma: no cover - network/runtime guard
            failed += 1
            print(f"[{i:>4}/{len(rows)}] FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            if args.strict:
                sys.exit(1)

        if args.delay > 0 and i < len(rows):
            time.sleep(args.delay)

    metrics = fetch_live_metrics(args.url)
    print("-" * 72)
    print(
        "Replay complete "
        f"ok={ok} failed={failed} total_replayed={metrics.get('total_replayed', 0)} "
        f"running_accuracy={metrics.get('running_accuracy', 0.0):.4f}"
    )

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
