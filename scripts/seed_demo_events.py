#!/usr/bin/env python3
"""
scripts/seed_demo_events.py — Lightweight demo event generator for DTX-AI.

Generates synthetic EventIn payloads (normal, warning, and critical cases)
and POSTs them to the running API so the dashboard can be demonstrated
without Isaac Sim or real sensor hardware.

Usage examples
--------------
# Quick demo — 10 events with 0.8 s delay:
    python scripts/seed_demo_events.py

# Replay a specific scenario (bearing_fault, overheating, combined, normal):
    python scripts/seed_demo_events.py --scenario overheating --count 5

# Send events as fast as possible (stress / integration test):
    python scripts/seed_demo_events.py --delay 0 --count 20

# Point at a non-default API:
    python scripts/seed_demo_events.py --url http://my-server:8000

Isaac Sim note
--------------
This seeder operates completely independently of Isaac Sim.
When Isaac Sim integration is ready, synthetic events can be fed through the
same POST /events/ endpoint — no changes to the API or dashboard are needed.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

# ── Scenario definitions ─────────────────────────────────────────────────────

# Each scenario is a dict with fields that override / augment a base payload.
_SCENARIOS: dict[str, list[dict[str, Any]]] = {
    "normal": [
        {
            "asset_id": "conveyor-belt-01",
            "zone_id": "zone-A",
            "vibration": 2.1,
            "temperature": 31.0,
            "humidity": 48.0,
            "pressure": 1012.0,
            "metadata": {"note": "normal ops"},
        },
        {
            "asset_id": "pump-station-02",
            "zone_id": "zone-B",
            "vibration": 3.5,
            "temperature": 40.0,
            "humidity": 52.0,
            "pressure": 1013.5,
            "metadata": {"note": "normal ops"},
        },
        {
            "asset_id": "forklift-03",
            "zone_id": "zone-C",
            "vibration": 1.2,
            "temperature": 25.0,
            "humidity": 44.0,
            "pressure": 1011.0,
            "metadata": {"note": "normal ops"},
        },
    ],
    "bearing_fault": [
        {
            "asset_id": "conveyor-belt-01",
            "zone_id": "zone-A",
            "vibration": 18.5,
            "temperature": 68.0,
            "humidity": 45.0,
            "pressure": 1012.0,
            "metadata": {"fault_type": "bearing"},
        },
        {
            "asset_id": "motor-drive-04",
            "zone_id": "zone-B",
            "vibration": 22.0,
            "temperature": 72.0,
            "humidity": 40.0,
            "pressure": 1010.0,
            "metadata": {"fault_type": "bearing"},
        },
    ],
    "overheating": [
        {
            "asset_id": "storage-rack-07",
            "zone_id": "zone-C",
            "vibration": 1.5,
            "temperature": 91.0,
            "humidity": 35.0,
            "pressure": 1010.5,
            "metadata": {"fault_type": "overheating"},
        },
        {
            "asset_id": "pump-station-02",
            "zone_id": "zone-A",
            "vibration": 4.2,
            "temperature": 98.0,
            "humidity": 32.0,
            "pressure": 1009.0,
            "metadata": {"fault_type": "overheating"},
        },
    ],
    "combined": [
        {
            "asset_id": "pump-station-02",
            "zone_id": "zone-A",
            "vibration": 21.0,
            "temperature": 95.0,
            "humidity": 88.0,
            "pressure": 1062.0,
            "metadata": {"fault_type": "combined"},
        },
        {
            "asset_id": "conveyor-belt-01",
            "zone_id": "zone-B",
            "vibration": 16.0,
            "temperature": 85.0,
            "humidity": 30.0,
            "pressure": 1055.0,
            "metadata": {"fault_type": "combined"},
        },
    ],
    "mixed": [],  # built dynamically below
}

# Build a "mixed" scenario that covers all fault types plus normals
_SCENARIOS["mixed"] = (
    _SCENARIOS["normal"][:1]
    + _SCENARIOS["bearing_fault"][:1]
    + _SCENARIOS["overheating"][:1]
    + _SCENARIOS["combined"][:1]
    + _SCENARIOS["normal"][1:2]
)


def _add_jitter(event: dict[str, Any]) -> dict[str, Any]:
    """Add small random noise to sensor readings so events look realistic."""
    out = dict(event)
    for field in ("vibration", "temperature", "humidity", "pressure"):
        if field in out and out[field] is not None:
            noise = random.uniform(-0.03, 0.03) * out[field]
            out[field] = round(out[field] + noise, 3)
    out["timestamp"] = datetime.now(timezone.utc).isoformat()
    return out


def post_event(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{url}/events/",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _pretty_result(result: dict[str, Any]) -> str:
    anomaly = result.get("anomaly", {})
    explanation = result.get("explanation", {})
    score = anomaly.get("anomaly_score", 0)
    score_str = f"{score:.3f}" if isinstance(score, (int, float)) else str(score)
    return (
        f"score={score_str}  "
        f"severity={anomaly.get('severity', '?'):<8}  "
        f"type={anomaly.get('anomaly_type', '?'):<12}  "
        f"summary={str(explanation.get('summary', ''))[:60]}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed demo events into the DTX-AI API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--url", default="http://localhost:8000", help="API base URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--scenario",
        default="mixed",
        choices=list(_SCENARIOS.keys()),
        help="Event scenario to use (default: mixed)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Total number of events to send (default: 10)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="Seconds between events (default: 0.8)",
    )
    parser.add_argument(
        "--no-jitter",
        action="store_true",
        help="Send exact values without random noise",
    )
    args = parser.parse_args()

    scenario_pool = _SCENARIOS[args.scenario]
    if not scenario_pool:
        print(f"ERROR: scenario '{args.scenario}' has no events.", file=sys.stderr)
        sys.exit(1)

    print(
        f"DTX-AI demo seeder — scenario={args.scenario} count={args.count} "
        f"delay={args.delay}s url={args.url}"
    )
    print("-" * 72)

    ok = failed = 0
    for i in range(1, args.count + 1):
        template = scenario_pool[(i - 1) % len(scenario_pool)]
        payload = template if args.no_jitter else _add_jitter(template)

        try:
            result = post_event(args.url, payload)
            print(f"  [{i:>3}/{args.count}] {payload['asset_id']:<22} → {_pretty_result(result)}")
            ok += 1
        except urllib.error.URLError as exc:
            print(f"  [{i:>3}/{args.count}] FAILED ({payload.get('asset_id', '?')}): {exc}")
            failed += 1
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            print(
                f"  [{i:>3}/{args.count}] ERROR  ({payload.get('asset_id', '?')}): "
                f"{type(exc).__name__}: {exc}"
            )
            failed += 1

        if args.delay > 0 and i < args.count:
            time.sleep(args.delay)

    print("-" * 72)
    print(f"Done. Sent {ok}/{args.count} events successfully. {failed} failed.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
