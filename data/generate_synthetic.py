"""
Synthetic event generator.

Generates realistic-looking warehouse sensor events with configurable
anomaly injection rate.  Output is written to data/synthetic_events.json.

Usage:
    python data/generate_synthetic.py --count 200 --anomaly-rate 0.2
"""

from __future__ import annotations

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ASSETS = [
    ("conveyor-belt-01", "zone-A"),
    ("conveyor-belt-02", "zone-D"),
    ("forklift-03", "zone-B"),
    ("storage-rack-07", "zone-C"),
    ("pump-station-02", "zone-A"),
    ("robotic-arm-01", "zone-E"),
]

# Normal operating ranges
NORMAL_RANGES = {
    "vibration":   (0.5, 8.0),
    "temperature": (18.0, 65.0),
    "humidity":    (30.0, 70.0),
    "pressure":    (990.0, 1030.0),
}

# Anomalous ranges
ANOMALY_RANGES = {
    "vibration":   (10.1, 30.0),
    "temperature": (76.0, 105.0),
    "humidity":    (86.0, 99.0),
    "pressure":    (1051.0, 1100.0),
}


def _sample(ranges: dict, key: str) -> float:
    lo, hi = ranges[key]
    return round(random.uniform(lo, hi), 2)


def generate_event(ts: datetime, inject_anomaly: bool) -> dict:
    asset_id, zone_id = random.choice(ASSETS)
    r = ANOMALY_RANGES if inject_anomaly else NORMAL_RANGES
    return {
        "event_id": str(uuid.uuid4()),
        "asset_id": asset_id,
        "zone_id": zone_id,
        "timestamp": ts.isoformat(),
        "vibration":    _sample(r, "vibration"),
        "temperature":  _sample(r, "temperature"),
        "humidity":     _sample(r, "humidity"),
        "pressure":     _sample(r, "pressure"),
        "metadata": {"synthetic": True, "anomaly_injected": inject_anomaly},
    }


def main(count: int = 100, anomaly_rate: float = 0.15) -> None:
    base_ts = datetime.now(timezone.utc) - timedelta(hours=count)
    events = []
    for i in range(count):
        ts = base_ts + timedelta(minutes=i * (60 / count))
        inject = random.random() < anomaly_rate
        events.append(generate_event(ts, inject))

    out_path = Path(__file__).parent / "synthetic_events.json"
    out_path.write_text(json.dumps(events, indent=2))
    print(f"Generated {count} events ({int(count * anomaly_rate)} expected anomalies) → {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--anomaly-rate", type=float, default=0.15)
    args = parser.parse_args()
    main(args.count, args.anomaly_rate)
