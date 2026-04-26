# inference.py
"""Real-time inference pipeline for industrial IoT fault detection."""

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
    if json_output:
        print(json.dumps(json_output, indent=2))
    else:
        print("Waiting for buffer to fill...")

# ── Inference pipeline ────────────────────────────────────
def run_inference(raw_input, window_buffer):
    """
    Processes a single sensor reading and returns JSON output.
    """
    # Preprocess: Get scaled data for the model
    # Returns None if buffer < 5
    X_scaled = preprocess_single(raw_input, 'scaler.pkl', window_buffer)

    # Safety Check: If buffer is not full, do not predict
    if X_scaled is None:
        return None
    
    # Predict
    anomaly_class_id = int(model.predict(X_scaled)[0])
    anomaly_proba    = model.predict_proba(X_scaled)[0]
    anomaly_score    = float(max(anomaly_proba))

    # Map class id to label
    class_map = {
        0: "no_fault",
        1: "bearing_fault",
        2: "overheating",
        3: "pressure_spike",
        4: "cold_start_stress",
        5: "thermal_runaway",
        6: "idle_overpressure"
    }

    # Build raw sensor values for dashboard
    raw_input_data = {
        "Vibration (mm/s)": raw_input.get("Vibration (mm/s)"),
        "Temperature (°C)": raw_input.get("Temperature (°C)"),
        "Pressure (bar)":   raw_input.get("Pressure (bar)")
    }

    # Build scaled features for SHAP
    input_features = dict(zip(FEATURES, X_scaled[0].tolist()))
    
    # Build JSON output
    output = {
        "timestamp":      raw_input["Timestamp"],
        "anomaly_class":  class_map[anomaly_class_id],
        "anomaly_score":  round(anomaly_score, 4),
        "raw_input":      raw_input_data,
        "input_features": input_features
    }

    return output

# ── Main ──────────────────────────────────────────────────
if __name__ == "__main__":
    window_buffer = []

    for i in range(6):
        raw_input = get_incoming_data()

        # Manually update the timestamp for the simulation
        raw_input["Timestamp"] = f"2026-03-25T03:21:0{i}"

        output = run_inference(raw_input, window_buffer)
        print(f"--- Second {i+1} ---")
        send_output(output)
