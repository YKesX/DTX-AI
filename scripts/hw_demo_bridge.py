#!/usr/bin/env python3
"""Bridge the ESP32 hardware demo node into the DTX-AI backend.

Polls the ESP32's ``GET /reading`` endpoint (DS18B20 temperature + BMP280
pressure, see HW/README.md), maps the two real measurements onto the
dataset's channel vocabulary, synthesizes the remaining channels from
nominal-class training statistics, and streams the result through
``POST /events/`` — so the dashboard shows IRL events exactly like the
dataset replay demo.

Channel mapping
---------------
* ``temperature_c``        <- DS18B20 reading, used as-is.
* ``pseudo_pressure_pa``   <- BMP280 deviation from a startup baseline,
                              multiplied by ``--pressure-gain``. The dataset's
                              pseudo-pressure is a hydraulic-line *delta*
                              (tens of kPa around 0), while the BMP280 reports
                              ~101 kPa absolute with only small ambient
                              wiggles — the gain lets a controlled change in air pressure around
                              the sensor land inside the fault range.
* ``power_dissipated_w``   <- nominal median + ``--power-per-degree`` for
                              every °C above the startup temperature baseline
                              (heating the probe mimics the overheat power
                              signature). All other channels are derived in
                              the source simulation anyway, so they are
                              synthesized as nominal median + small Gaussian
                              jitter; classification is therefore driven by
                              the two *real* sensors.

No ground-truth labels are attached — IRL events show model predictions on
the dashboard but do not contribute to replay-accuracy metrics.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import signal
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ai_path = str(REPO_ROOT / "services" / "ai")
if ai_path not in sys.path:
    sys.path.insert(0, ai_path)

from preprocessing import FEATURES, get_training_pool, load_data  # noqa: E402

def sensor_values(reading: dict[str, Any]) -> tuple[float | None, float | None]:
    """Only accept finite, in-range readings with no explicit sensor fault."""
    age = reading.get("sample_age_ms")
    if age is not None and (not isinstance(age, (int, float)) or not math.isfinite(age) or age < 0 or age > 3000):
        return None, None

    def value(key: str, health_key: str, low: float, high: float) -> float | None:
        raw = reading.get(key)
        if reading.get(health_key) is False or isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None
        return float(raw) if math.isfinite(raw) and low <= raw <= high else None

    return (value("temperature_c", "ds18b20_ok", -55, 125),
            value("pressure_pa", "bmp280_ok", 30000, 110000))


def fetch_json(url: str, timeout: float = 5.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def nominal_channel_stats() -> dict[str, dict[str, float]]:
    """Median/std of every channel over nominal rows of the training pool.

    Computed from the training pool only (never the demo holdout) so the
    synthesized channels carry no information about held-out data.
    """
    df = load_data(str(REPO_ROOT / "services" / "ai" / "dtx_ai_master_dataset.csv"))
    pool = get_training_pool(df)
    nominal = pool[pool["fault_label"] == 0]
    stats: dict[str, dict[str, float]] = {}
    for channel in FEATURES:
        series = nominal[channel].dropna()
        stats[channel] = {
            "median": float(series.median()),
            "std": float(series.std() or 0.0),
        }
    return stats


def calibrate(esp32_url: str, samples: int, interval: float) -> tuple[float, float]:
    """Average a few startup readings into temperature/pressure baselines."""
    temps: list[float] = []
    pressures: list[float] = []
    for _ in range(samples):
        reading = fetch_json(f"{esp32_url}/reading")
        temp, pressure = sensor_values(reading)
        if temp is not None:
            temps.append(temp)
        if pressure is not None:
            pressures.append(pressure)
        time.sleep(interval)
    if not temps and not pressures:
        raise RuntimeError(
            "ESP32 returned no usable sensor readings during calibration — "
            "check wiring (DS18B20 pull-up, BMP280 CSB->3V3 / SDO->GND)."
        )
    temp_baseline = sum(temps) / len(temps) if temps else float("nan")
    pressure_baseline = sum(pressures) / len(pressures) if pressures else float("nan")
    return temp_baseline, pressure_baseline


def build_event_payload(
    reading: dict[str, Any],
    stats: dict[str, dict[str, float]],
    *,
    temp_baseline: float,
    pressure_baseline: float,
    pressure_gain: float,
    power_per_degree: float,
    model: str,
    sequence: int,
    rng: random.Random,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "asset_id": "esp32-demo-node",
        "zone_id": "irl-zone",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
    }

    real_temp, real_pressure = sensor_values(reading)
    if real_temp is None and real_pressure is None:
        raise ValueError("No valid, fresh sensor readings; skipping event instead of fabricating hardware data.")
    if real_pressure is not None and not math.isfinite(pressure_baseline):
        raise ValueError("BMP280 has no calibrated baseline; restart the bridge to calibrate it.")
    real_channels = set()
    if real_temp is not None:
        real_channels.add("temperature_c")
    if real_pressure is not None:
        real_channels.add("pseudo_pressure_pa")
    derived_channels = {"power_dissipated_w"} if real_temp is not None and math.isfinite(temp_baseline) else set()

    for channel in FEATURES:
        if channel == "temperature_c" and real_temp is not None:
            payload[channel] = float(real_temp)
        elif channel == "pseudo_pressure_pa" and real_pressure is not None:
            payload[channel] = (float(real_pressure) - pressure_baseline) * pressure_gain
        elif channel in derived_channels:
            base = stats[channel]["median"]
            if real_temp is not None and math.isfinite(temp_baseline):
                base += max(0.0, float(real_temp) - temp_baseline) * power_per_degree
            payload[channel] = base
        else:
            s = stats[channel]
            payload[channel] = s["median"] + rng.gauss(0.0, s["std"] * 0.05)

    payload["metadata"] = {
        "source": "hardware_demo",
        "device": "esp32-wroom-32",
        "sensors": {"temperature": "ds18b20", "pressure": "bmp280"},
        "esp32_sequence": reading.get("sequence"),
        "raw_reading": {
            "temperature_c": real_temp,
            "pressure_pa": real_pressure,
            "bmp280_temperature_c": (
                reading.get("bmp280_temperature_c")
                if isinstance(reading.get("bmp280_temperature_c"), (int, float))
                and math.isfinite(reading["bmp280_temperature_c"])
                else None
            ),
        },
        "baselines": {
            "temperature_c": None if not math.isfinite(temp_baseline) else round(temp_baseline, 3),
            "pressure_pa": None if not math.isfinite(pressure_baseline) else round(pressure_baseline, 1),
        },
        "real_channels": sorted(real_channels),
        "derived_channels": sorted(derived_channels),
        "synthesized_channels": sorted(set(FEATURES) - real_channels - derived_channels),
        "bridge_sequence": sequence,
        "active_model": model,
    }
    return payload


def post_event(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{base_url}/events/",
        data=json.dumps(payload, allow_nan=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream ESP32 sensor readings into DTX-AI.")
    parser.add_argument("--esp32-url", default="http://dtx-esp32.local",
                        help="Base URL of the ESP32 node (default: mDNS name).")
    parser.add_argument("--url", default="http://localhost:8000",
                        help="DTX-AI API base URL.")
    parser.add_argument("--model", default="lightgbm",
                        help="Model key the backend should run for these events.")
    parser.add_argument("--interval", type=float, default=1.0,
                        help="Seconds between samples (default 1.0).")
    parser.add_argument("--count", type=int, default=0,
                        help="Stop after N events (0 = run until interrupted).")
    parser.add_argument("--calibration-samples", type=int, default=5,
                        help="Startup readings averaged into the baselines.")
    parser.add_argument("--pressure-gain", type=float, default=200.0,
                        help="Multiplier from BMP280 Pa-deviation to pseudo_pressure_pa.")
    parser.add_argument("--power-per-degree", type=float, default=40.0,
                        help="Synthesized W of dissipated power per °C above baseline.")
    parser.add_argument("--seed", type=int, default=0,
                        help="Jitter RNG seed (0 = nondeterministic).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed or None)

    print(f"[bridge] loading nominal channel statistics from the training pool...")
    stats = nominal_channel_stats()

    print(f"[bridge] probing ESP32 at {args.esp32_url} ...")
    try:
        health = fetch_json(f"{args.esp32_url}/health")
    except (urllib.error.URLError, OSError) as exc:
        print(f"[bridge] ESP32 unreachable at {args.esp32_url}: {exc}", file=sys.stderr)
        sys.exit(2)
    print(f"[bridge] ESP32 ok: {health}")

    print(f"[bridge] calibrating baselines over {args.calibration_samples} samples...")
    temp_baseline, pressure_baseline = calibrate(
        args.esp32_url, args.calibration_samples, max(args.interval, 0.2),
    )
    print(f"[bridge] baselines: temperature={temp_baseline:.2f}C "
          f"pressure={pressure_baseline:.1f}Pa")

    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(flag=True))
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))

    sequence = 0
    while not stop["flag"]:
        sequence += 1
        try:
            reading = fetch_json(f"{args.esp32_url}/reading")
            temp, pressure = sensor_values(reading)
            if temp is not None and not math.isfinite(temp_baseline):
                temp_baseline = temp
                print("[bridge] recovered DS18B20: calibrated its baseline from the first valid reading.")
            if pressure is not None and not math.isfinite(pressure_baseline):
                pressure_baseline = pressure
                print("[bridge] recovered BMP280: calibrated its baseline from the first valid reading.")
            payload = build_event_payload(
                reading, stats,
                temp_baseline=temp_baseline,
                pressure_baseline=pressure_baseline,
                pressure_gain=args.pressure_gain,
                power_per_degree=args.power_per_degree,
                model=args.model,
                sequence=sequence,
                rng=rng,
            )
            response = post_event(args.url, payload)
            metadata = (response.get("event") or {}).get("metadata") or {}
            anomaly = response.get("anomaly") or {}
            print(
                f"[{sequence:>5}] temp={payload.get('temperature_c', float('nan')):.2f}C "
                f"pressure={payload.get('pseudo_pressure_pa', float('nan')):>10.1f}Pa "
                f"pred={metadata.get('predicted_label', anomaly.get('anomaly_type', '?')):<16} "
                f"score={float(anomaly.get('anomaly_score', 0.0)):.4f} "
                f"model={metadata.get('runtime_model', '?')}"
            )
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"[{sequence:>5}] sample failed: {type(exc).__name__}: {exc}", file=sys.stderr)

        if args.count and sequence >= args.count:
            break
        time.sleep(max(args.interval, 0.05))

    print(f"[bridge] stopped after {sequence} events.")


if __name__ == "__main__":
    main()
