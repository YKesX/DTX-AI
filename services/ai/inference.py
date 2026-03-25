# inference.py
# Stub inference pipeline — full integration to be completed

import json
import joblib
import pandas as pd
import sys
sys.path.append('./services/ai')

from preprocessing import preprocess_single, FEATURES

# ── Load model and scaler ─────────────────────────────────
model  = joblib.load('model_best.pkl')
scaler = joblib.load('scaler.pkl')

# ── STUB: replace with real data source ───────────────────
def get_incoming_data():
    """
    STUB — returns a single raw sensor reading.
    Replace with real ESP32 / playback input.
    """
    return {
        "Vibration (mm/s)": 0.75,
        "Temperature (°C)": 95.2,
        "Pressure (bar)":   8.1,
        "Timestamp":        "2026-03-25T03:21:00"
    }

# ── STUB: replace with real output target ─────────────────
def send_output(json_output):
    """
    STUB — prints JSON output.
    Replace with real API call / WebSocket.
    """
    print(json.dumps(json_output, indent=2))

# ── Inference pipeline ────────────────────────────────────
def run_inference(raw_input, window_buffer):
    """
    Processes a single sensor reading and returns JSON output.
    """
    # Preprocess
    X_scaled = preprocess_single(raw_input, 'scaler.pkl', window_buffer)

    # Predict
    anomaly_class_id = model.predict(X_scaled)[0]
    anomaly_proba    = model.predict_proba(X_scaled)[0]
    anomaly_score    = float(max(anomaly_proba))

    # Map class id to label
    class_map = {
        0: "no_fault",
        1: "bearing_fault",
        2: "overheating"
    }

    # Build input_features dict
    input_features = dict(zip(FEATURES, X_scaled[0].tolist()))

    # Build JSON output
    output = {
        "timestamp":      raw_input["Timestamp"],
        "anomaly_class":  class_map[anomaly_class_id],
        "anomaly_score":  round(anomaly_score, 4),
        "input_features": input_features
    }

    return output

# ── Main ──────────────────────────────────────────────────
if __name__ == "__main__":
    window_buffer = []

    raw_input = get_incoming_data()

    # Fill buffer if not enough history
    if len(window_buffer) < 5:
        window_buffer = [raw_input] * 5

    output = run_inference(raw_input, window_buffer)
    send_output(output)