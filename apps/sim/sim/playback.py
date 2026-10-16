"""
Playback engine — reads a scenario JSON and replays it to POST /positions.

Usage:
    python -m sim.playback --scenario scenarios/forklift_patrol.json --speed 1.0
"""

import argparse
import json
import time
import requests
from pathlib import Path


def run(scenario_path: str, speed: float = 1.0, api_url: str = "http://localhost:8000") -> None:
    path = Path(scenario_path)
    frames = json.loads(path.read_text())

    print(f"[Playback] {len(frames)} frame yüklendi: {path.name}")
    print(f"[Playback] Hız: {speed}x  →  API: {api_url}/positions/")

    prev_t = None
    for i, frame in enumerate(frames):
        # Frameler arası bekleme (speed ile ölçeklendirilmiş)
        t = frame.get("t", i * 0.5)
        if prev_t is not None:
            wait = (t - prev_t) / speed
            if wait > 0:
                time.sleep(wait)
        prev_t = t

        payload = {
            "entity_id":   frame["entity_id"],
            "entity_type": frame.get("entity_type", "forklift"),
            "x":           frame["x"],
            "y":           frame["y"],
            "z":           frame.get("z", 0.0),
            "heading":     frame.get("heading", 0.0),
            "zone_id":     frame.get("zone_id", ""),
        }

        try:
            r = requests.post(f"{api_url}/positions/", json=payload, timeout=2)
            status = "✓" if r.status_code == 202 else f"✗ {r.status_code}"
        except requests.exceptions.ConnectionError:
            status = "✗ API'ye bağlanılamadı"

        print(f"  [{i+1:03d}] t={t:.1f}s  {frame['entity_id']}  "
              f"({frame['x']:.1f}, {frame['y']:.1f})  {status}")

    print("[Playback] Tamamlandı.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DTX-AI Entity Playback")
    parser.add_argument("--scenario", required=True, help="Senaryo JSON dosyası")
    parser.add_argument("--speed", type=float, default=1.0, help="Oynatma hızı (2.0 = 2x hızlı)")
    parser.add_argument("--api", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()
    run(args.scenario, args.speed, args.api)