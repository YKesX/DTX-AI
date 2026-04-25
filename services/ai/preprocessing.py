# -*- coding: utf-8 -*-
"""Data preprocessing utilities for the industrial IoT fault detection model.

This module loads the local master dataset, performs feature engineering, 
splits the data into train/test sets, fits and persists a StandardScaler, 
and provides helpers for preprocessing single records for inference.
"""

# preprocessing.py

import pandas as pd
import numpy as np
import joblib
import threading
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


_scaler_cache: dict = {}
_scaler_cache_lock = threading.Lock()


FEATURES = [
    'Vibration (mm/s)', 'Temperature (°C)', 'Pressure (bar)',
    'vib_rolling_mean', 'vib_rolling_std', 'vib_rolling_max',
    'temp_rolling_mean', 'temp_drift', 'pressure_rolling_mean'
]


def load_data(file_name="dtx_ai_master_dataset.csv"):
    """Loads dataset from local CSV with correct encoding and cleaning."""
    # encoding='latin1' to handle special characters
    df = pd.read_csv(file_name, encoding='latin1')
    
    # ── FIX: Rename the broken temperature column ──
    # This maps 'Temperature (ï¿½C)' back to 'Temperature (°C)'
    rename_dict = {col: 'Temperature (°C)' for col in df.columns if 'Temperature' in col}
    df = df.rename(columns=rename_dict)

    #Drop unused columns
    to_drop = ['Zone', 'RMS Vibration', 'Mean Temp']
    for col in to_drop:
        if col in df.columns:
            df = df.drop(columns=[col])


    # Parse and sort by timestamp
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df = df.sort_values('Timestamp').reset_index(drop=True)

    # Debug: Print actual column names to see the mismatch
    print("Actual column names:", df.columns.tolist())

    return df


def engineer_features(df, window=5):
    """Derives rolling features from raw sensor columns."""

    # Vibration features
    df['vib_rolling_mean'] = df['Vibration (mm/s)'].rolling(window).mean()
    df['vib_rolling_std']  = df['Vibration (mm/s)'].rolling(window).std()
    df['vib_rolling_max']  = df['Vibration (mm/s)'].rolling(window).max()

    # Temperature features
    df['temp_rolling_mean'] = df['Temperature (°C)'].rolling(window).mean()
    df['temp_drift']        = df['Temperature (°C)'].diff(window)

    # Pressure features
    df['pressure_rolling_mean'] = df['Pressure (bar)'].rolling(window).mean()

    # Drop NaN rows produced by rolling calculations
    df = df.dropna().reset_index(drop=True)

    return df


def split_and_scale(df):
    """Splits data into train/test sets and applies StandardScaler."""

    X = df[FEATURES]
    y = df['Fault Label']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y  # preserves class ratio in both splits
    )

    # Fit scaler only on train data — prevents data leakage into test set
    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(
        scaler.fit_transform(X_train),
        columns=FEATURES,
        index=X_train.index
    )
    X_test_scaled = pd.DataFrame(
        scaler.transform(X_test),
        columns=FEATURES,
        index=X_test.index
    )

    # Save scaler for inference
    joblib.dump(scaler, 'scaler.pkl')

    return X_train_scaled, X_test_scaled, y_train, y_test


def preprocess_single(raw_input: dict, scaler_path='scaler.pkl', window_buffer: list = None):
    """
    Processes a single incoming data point for live inference.

    Args:
        raw_input:      dict with keys:
                          'Vibration (mm/s)', 'Temperature (°C)',
                          'Pressure (bar)', 'Timestamp'
        scaler_path:    path to saved scaler.pkl
        window_buffer:  list of last N raw reading dicts (min 5 required).
                        This function mutates the buffer in place and will
                        keep only the most recent 5 readings after each call.

    Returns:
        X_scaled: np.array ready for model.predict()
    """

    window_size = 5

    if window_buffer is None:
        raise ValueError("A window_buffer list must be provided.")

    # 1. Append the new reading first
    window_buffer.append(raw_input)

    # 2. Keep only the most recent 'window_size' records
    if len(window_buffer) > window_size:
        window_buffer[:] = window_buffer[-window_size:]

    # 3. IF BUFFER IS NOT FULL: Return None instead of crashing
    if len(window_buffer) < window_size:
        return None
    
    # Build DataFrame from buffer
    df_buffer = pd.DataFrame(window_buffer)
    df_buffer['Timestamp'] = pd.to_datetime(df_buffer['Timestamp'])

    # Engineer rolling features on buffer
    df_buffer = engineer_features(df_buffer, window=window_size)

    # Take only the latest row (current reading)
    latest = df_buffer.iloc[[-1]]
    X = latest[FEATURES]

    # Load scaler (cached by path to avoid repeated filesystem IO)
    if scaler_path not in _scaler_cache:
        with _scaler_cache_lock:
            if scaler_path not in _scaler_cache:
                _scaler_cache[scaler_path] = joblib.load(scaler_path)
    scaler = _scaler_cache[scaler_path]
    X_scaled = scaler.transform(X)

    return X_scaled


def run_preprocessing():
    """Runs full preprocessing pipeline and saves all outputs."""

    print("Loading data...")
    df = load_data()

    print("Engineering features...")
    df = engineer_features(df)

    print("Splitting and scaling...")
    X_train, X_test, y_train, y_test = split_and_scale(df)

    # Save processed data for model notebooks
    X_train.to_csv('X_train.csv', index=False)
    X_test.to_csv('X_test.csv',  index=False)
    y_train.to_csv('y_train.csv', index=False)
    y_test.to_csv('y_test.csv',  index=False)

    print("Done.")
    print(f"  X_train : {X_train.shape}")
    print(f"  X_test  : {X_test.shape}")
    print(f"  Classes : {y_train.value_counts().to_dict()}")

    return X_train, X_test, y_train, y_test


if __name__ == "__main__":
    run_preprocessing()