#!/usr/bin/env python3
"""
scripts/seed_events.py — POST sample events to the running DTX-AI API.

Usage:
    python scripts/seed_events.py [--url http://localhost:8000] [--file data/sample_events.json]
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


def post_event(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{url}/events/",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed sample events into the DTX-AI API.")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument(
        "--file",
        default=str(Path(__file__).parent.parent / "data" / "sample_events.json"),
        help="Path to events JSON file",
    )
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between events")
    args = parser.parse_args()

    events_path = Path(args.file)
    if not events_path.exists():
        print(f"ERROR: Events file not found: {events_path}", file=sys.stderr)
        sys.exit(1)

    events = json.loads(events_path.read_text())
    print(f"Seeding {len(events)} events to {args.url} …")

    for i, event in enumerate(events, 1):
        try:
            result = post_event(args.url, event)
            severity = result.get("anomaly", {}).get("severity", "?")
            score = result.get("anomaly", {}).get("anomaly_score", 0)
            print(f"  [{i}/{len(events)}] {event['asset_id']} → score={score:.3f} severity={severity}")
        except urllib.error.URLError as exc:
            print(f"  [{i}/{len(events)}] FAILED: {exc}")
        time.sleep(args.delay)

    print("Done.")


if __name__ == "__main__":
    main()
