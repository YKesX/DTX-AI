#!/usr/bin/env python3
"""Replay dataset rows through ``POST /events/`` for validation demos.

Default ``--split holdout`` is the shuffled stratified demo holdout. Use
``--split episode_holdout`` for grouped episode/run validation or
``--split temporal`` for chronological tail checks.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from socket import timeout as SocketTimeout
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
ai_path = str(REPO_ROOT / "services" / "ai")
if ai_path not in sys.path:
    sys.path.insert(0, ai_path)

from preprocessing import (  # noqa: E402
    CLASS_NAMES,
    FEATURES,
    LABEL_TO_INT,
    episode_groups,
    get_demo_holdout,
    load_data,
    split_episode_pool_and_holdout,
    split_temporal_pool_and_holdout,
)

try:
    from ai.model_loader import load_runtime_model
except Exception:  # pragma: no cover - optional preflight dependency
    load_runtime_model = None  # type: ignore[assignment]


def normalize_label(value: Any) -> str:
    """Translate numeric/string ground-truth labels to a canonical class name."""
    raw = str(value).strip().lower()
    if raw in LABEL_TO_INT:
        return raw
    if raw.isdigit() and 0 <= int(raw) < len(CLASS_NAMES):
        return CLASS_NAMES[int(raw)]
    return raw


def prepare_replay_rows(
    split: str = "holdout",
    limit: int | None = None,
    *,
    shuffle: bool = True,
    shuffle_seed: int = 0,
) -> pd.DataFrame:
    """Pick the rows to replay through ``POST /events/``.

    The default split is ``holdout`` — the canonical 20% shuffled demo slice
    used for readable dashboard demos.

    ``episode_holdout`` is the honest grouped split for validation: complete
    episodes/runs are held out together. ``temporal`` is the chronological
    tail and is useful for drift checks.

    ``shuffle`` is on by default so a small ``--limit`` covers all 6 fault
    classes instead of a single contiguous block (the underlying CSV is
    sorted by class). ``shuffle_seed=0`` re-shuffles every invocation; pass
    a fixed integer for reproducible demos.
    """
    raw_df = load_data(str(REPO_ROOT / "services" / "ai" / "dtx_ai_master_dataset.csv"))
    raw_df["_source_row_id"] = raw_df.index.astype(int)

    if split == "holdout":
        split_df = get_demo_holdout(raw_df)
    elif split == "episode_holdout":
        _, split_df = split_episode_pool_and_holdout(raw_df)
    elif split == "temporal":
        _, split_df = split_temporal_pool_and_holdout(raw_df)
    elif split == "all":
        split_df = raw_df.copy().reset_index(drop=True)
    else:
        raise ValueError(
            f"Unsupported split '{split}'. Use 'holdout', 'episode_holdout', 'temporal', or 'all'."
        )

    split_df = split_df.copy().reset_index(drop=True)
    split_df["_episode_group"] = episode_groups(split_df).astype(str).values

    if shuffle:
        seed = None if shuffle_seed == 0 else shuffle_seed
        split_df = split_df.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    if limit is not None:
        split_df = split_df.iloc[: max(limit, 0)].copy()
    return split_df


# Backwards-compat shim — kept so the smoke test can import the helper, but
# no longer used by the demo itself. Callers should prefer
# ``preprocessing.split_training_pool_and_holdout`` for the canonical split.
def chronological_split(df: pd.DataFrame, test_ratio: float = 0.2) -> dict[str, pd.DataFrame]:
    if df.empty:
        return {"train": df.copy(), "test": df.copy(), "all": df.copy()}
    split_idx = max(1, int(len(df) * (1.0 - test_ratio)))
    split_idx = min(split_idx, len(df) - 1) if len(df) > 1 else 1
    train = df.iloc[:split_idx].copy().reset_index(drop=True)
    test = df.iloc[split_idx:].copy().reset_index(drop=True)
    return {"train": train, "test": test, "all": df.copy().reset_index(drop=True)}


def build_event_payload(
    row: pd.Series,
    *,
    replay_index: int,
    split: str,
    model: str,
    strict: bool,
) -> dict[str, Any]:
    """Build a ``POST /events/`` payload from one dataset row."""
    ground_truth_int = int(row["fault_label"])
    ground_truth_name = CLASS_NAMES[ground_truth_int] if 0 <= ground_truth_int < len(CLASS_NAMES) else "unknown"

    payload: dict[str, Any] = {
        "asset_id": f"isaac-asset-{row.get('_source_row_id', replay_index)}",
        "zone_id": "isaac-zone",
        "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    for feature in FEATURES:
        if feature in row and pd.notna(row[feature]):
            payload[feature] = float(row[feature])

    payload["metadata"] = {
        "source": "dataset_replay",
        "dataset": "dtx_ai_master_dataset",
        "row_id": int(row.get("_source_row_id", replay_index - 1)),
        "replay_index": replay_index,
        "split": split,
        "ground_truth_label": str(ground_truth_int),
        "ground_truth_name": ground_truth_name,
        "active_model": model,
        "replay_strict": bool(strict),
    }
    if "_episode_group" in row and pd.notna(row["_episode_group"]):
        payload["metadata"]["episode_group"] = str(row["_episode_group"])
    return payload


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
        f"Start backend first (bash scripts/run_dev.sh). Last error: {last_err}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay dataset rows through the DTX-AI API.")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--model", default="lightgbm")
    parser.add_argument(
        "--split", default="holdout", choices=["holdout", "episode_holdout", "temporal", "all"],
        help="'holdout' (default) replays the shuffled demo holdout; "
             "'episode_holdout' holds out whole episodes/runs; 'temporal' replays the "
             "chronological tail; 'all' includes rows used in training.",
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument(
        "--no-shuffle", action="store_true",
        help="Replay rows in dataset order (default is to shuffle so a small "
             "--limit shows every fault class instead of a single contiguous block).",
    )
    parser.add_argument(
        "--shuffle-seed", type=int, default=0,
        help="Fixed shuffle seed for reproducible demos (default 0 = re-shuffle every run).",
    )
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--wait-timeout", type=float, default=20.0)
    return parser.parse_args()


def preflight_requested_model(model_key: str, strict: bool) -> None:
    if load_runtime_model is None:
        print("Warning: ai.model_loader unavailable; skipping preflight.", file=sys.stderr)
        return
    runtime = load_runtime_model(requested_model=model_key, strict_selection=True)
    if runtime.available:
        print(f"Model preflight OK: requested={model_key} runtime={runtime.key}")
        return
    message = f"Requested model '{model_key}' is unavailable. Reason: {runtime.reason}"
    if strict:
        raise RuntimeError(message)
    print(
        f"Warning: {message}\nReplay may fall back to another model. Use --strict to fail fast.",
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

    rows = prepare_replay_rows(
        split=args.split,
        limit=args.limit,
        shuffle=not args.no_shuffle,
        shuffle_seed=args.shuffle_seed,
    )
    if rows.empty:
        print("No rows available for replay.", file=sys.stderr)
        sys.exit(1)

    class_dist = rows["fault_label"].value_counts().sort_index().to_dict()
    print(
        f"Dataset replay: split={args.split} rows={len(rows)} model={args.model} "
        f"strict={int(args.strict)} shuffle={int(not args.no_shuffle)} "
        f"class_distribution={class_dist}"
    )

    ok = failed = 0
    for i, (_, row) in enumerate(rows.iterrows(), start=1):
        payload = build_event_payload(
            row, replay_index=i, split=args.split, model=args.model, strict=args.strict,
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
                f"[{i:>4}/{len(rows)}] model={runtime_model:<14} gt={gt:<16} "
                f"pred={pred:<16} score={float(score):.4f} correct={correct}"
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
        f"Replay complete  ok={ok}  failed={failed}  "
        f"total_replayed={metrics.get('total_replayed', 0)}  "
        f"running_accuracy={metrics.get('running_accuracy', 0.0):.4f}"
    )
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
