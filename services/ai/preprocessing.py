# -*- coding: utf-8 -*-
"""Data preprocessing utilities for the industrial IoT fault detection model.

This module downloads the source dataset from Kaggle, performs feature
engineering, splits the data into train/test sets, fits and persists a
StandardScaler, and provides helpers for preprocessing single records for
inference and running the end-to-end preprocessing pipeline.
"""

# preprocessing.py

import pandas as pd
import numpy as np
import kagglehub
import joblib
import os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


FEATURES = [
    'Vibration (mm/s)', 'Temperature (°C)', 'Pressure (bar)',
    'vib_rolling_mean', 'vib_rolling_std', 'vib_rolling_max',
    'temp_rolling_mean', 'temp_drift', 'pressure_rolling_mean'
]


def load_data():
    """Downloads dataset from Kaggle and loads into DataFrame."""
    path = kagglehub.dataset_download("ziya07/industrial-iot-fault-detection-dataset")

    files = os.listdir(path)
    csv_file = [f for f in files if f.endswith('.csv')][0]

    df = pd.read_csv(f"{path}/{csv_file}")

    # Drop constant columns — same value across all rows, no predictive value
    df = df.drop(columns=['RMS Vibration', 'Mean Temp'])

    # Parse and sort by timestamp
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df = df.sort_values('Timestamp').reset_index(drop=True)

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

    if window_buffer is None or len(window_buffer) < window_size:
        raise ValueError(f"window_buffer must contain at least {window_size} previous readings")

    # Add current reading to buffer
    window_buffer.append(raw_input)

    # Prune buffer to keep only the last `window_size` readings
    if len(window_buffer) > window_size:
        window_buffer[:] = window_buffer[-window_size:]

    # Build DataFrame from buffer
    df_buffer = pd.DataFrame(window_buffer)
    df_buffer['Timestamp'] = pd.to_datetime(df_buffer['Timestamp'])

    # Engineer rolling features on buffer
    df_buffer = engineer_features(df_buffer, window=window_size)

    # Take only the latest row (current reading)
    latest = df_buffer.iloc[[-1]]
    X = latest[FEATURES]

    # Load scaler and transform
    scaler = joblib.load(scaler_path)
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