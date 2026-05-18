"""Data preprocessing for the Isaac-Sim-style telemetry dataset.

Schema of services/ai/dtx_ai_master_dataset.csv:

    timestamp_s, step_index   <- bookkeeping, dropped as features
    imu_lin_acc_{x,y,z}       <- linear acceleration
    imu_ang_vel_{x,y,z}       <- angular velocity
    vibration_magnitude       <- scalar vibration norm
    lift_joint_position
    lift_force_z              <- vertical lift force
    pseudo_pressure_pa        <- hydraulic line proxy pressure (Pa)
    drive_joint_velocity
    drive_joint_effort        <- drive-joint actuator torque
    lift_joint_velocity
    roller_{fl,fr,bl,br}_velocity  <- 4 wheel angular velocities
    power_dissipated_w
    temperature_c
    fault_label               <- str: nominal|bearing_wear|overheat|
                                     overload|pressure_fault|wheel_slip
"""

import threading

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# Canonical class order — also the int code each label maps to via LABEL_TO_INT.
# Position 0 is the "no anomaly" baseline so runtime code can treat class 0 as
# nominal without a separate lookup.
CLASS_NAMES = [
    "nominal",
    "bearing_wear",
    "overheat",
    "overload",
    "pressure_fault",
    "wheel_slip",
]
LABEL_TO_INT = {name: idx for idx, name in enumerate(CLASS_NAMES)}
INT_TO_LABEL = {idx: name for idx, name in enumerate(CLASS_NAMES)}

# Feature columns fed into every model. Order is fixed and persisted to
# services/ai/ai/models/shared/feature_order.json — the runtime relies on
# matching positional order to apply the saved scaler.
FEATURES = [
    "imu_lin_acc_x",
    "imu_lin_acc_y",
    "imu_lin_acc_z",
    "imu_ang_vel_x",
    "imu_ang_vel_y",
    "imu_ang_vel_z",
    "vibration_magnitude",
    "lift_joint_position",
    "lift_force_z",
    "pseudo_pressure_pa",
    "drive_joint_velocity",
    "drive_joint_effort",
    "lift_joint_velocity",
    "roller_fl_velocity",
    "roller_fr_velocity",
    "roller_bl_velocity",
    "roller_br_velocity",
    "power_dissipated_w",
    "temperature_c",
]

# Demo holdout. A fixed 20% slice of the full dataset is kept out of every
# training run (stratified by fault_label, seed=42) so that scripts/run_demo.sh
# and scripts/replay_dataset_demo.py can replay rows the models have never
# seen. Training + cross-validation operate exclusively on the remaining 80%
# pool, and the overall-best model's final test report (services/ai/ai/models/
# */metadata.json:metrics.test_*) is computed against this holdout — so the
# test_* numbers reflect honest generalisation, not in-pool resubstitution.
HOLDOUT_RATIO = 0.2
HOLDOUT_RANDOM_STATE = 42


_scaler_cache: dict = {}
_scaler_cache_lock = threading.Lock()


def load_data(file_name: str = "dtx_ai_master_dataset.csv") -> pd.DataFrame:
    """Load the dataset and convert the string ``fault_label`` to an int code.

    Returns a DataFrame containing every FEATURES column plus ``fault_label``
    (int) and ``fault_label_name`` (original string), sorted by ``timestamp_s``.
    """
    df = pd.read_csv(file_name)
    if "fault_label" not in df.columns:
        raise ValueError("Dataset is missing required column: fault_label")

    # Drop rows with missing fault labels
    df = df.dropna(subset=["fault_label"]).reset_index(drop=True)
    
    df["fault_label_name"] = df["fault_label"].astype(str)
    df["fault_label"] = df["fault_label_name"].map(LABEL_TO_INT)
    if df["fault_label"].isna().any():
        unknown = sorted(set(df.loc[df["fault_label"].isna(), "fault_label_name"]))
        raise ValueError(
            f"Dataset contains unknown fault labels not in CLASS_NAMES: {unknown}. "
            f"Update CLASS_NAMES in services/ai/preprocessing.py if these are real."
        )
    df["fault_label"] = df["fault_label"].astype(int)

    if "timestamp_s" in df.columns:
        df = df.sort_values("timestamp_s").reset_index(drop=True)

    missing = [c for c in FEATURES if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing required feature column(s): {missing}")

    return df


def split_training_pool_and_holdout(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the full dataset into an 80% training pool and a 20% demo holdout.

    Stratified on ``fault_label`` with a fixed random seed so the holdout is
    identical for every caller (training script, notebook, demo replay).
    The training pool index order is preserved for reproducibility.
    """
    train_idx, holdout_idx = train_test_split(
        df.index,
        test_size=HOLDOUT_RATIO,
        random_state=HOLDOUT_RANDOM_STATE,
        stratify=df["fault_label"],
    )
    training_pool = df.loc[sorted(train_idx)].reset_index(drop=True)
    holdout = df.loc[sorted(holdout_idx)].reset_index(drop=True)
    return training_pool, holdout


def get_training_pool(df: pd.DataFrame) -> pd.DataFrame:
    """Convenience: return only the 80% training pool."""
    return split_training_pool_and_holdout(df)[0]


def get_demo_holdout(df: pd.DataFrame) -> pd.DataFrame:
    """Convenience: return only the 20% demo holdout the models never see."""
    return split_training_pool_and_holdout(df)[1]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """No-op for the new 19-channel schema.

    Kept as a stable import point for the notebook and training script; the
    previous rolling-window feature engineering is no longer needed now that
    the raw sensor set is rich enough to discriminate the 6 fault classes
    on its own.
    """
    return df


def split_and_scale(df: pd.DataFrame):
    """Stratified 80/20 split, scaler fit on train only — no leakage."""
    X = df[FEATURES]
    y = df["fault_label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y,
    )
    scaler = StandardScaler().fit(X_train)
    X_train_s = pd.DataFrame(scaler.transform(X_train), columns=FEATURES, index=X_train.index)
    X_test_s = pd.DataFrame(scaler.transform(X_test), columns=FEATURES, index=X_test.index)
    joblib.dump(scaler, "scaler.pkl")
    return X_train_s, X_test_s, y_train, y_test


def preprocess_single(
    raw_input: dict,
    scaler_path: str = "scaler.pkl",
    window_buffer=None,  # kept for backward signature compat — unused
):
    """Transform a single sensor reading dict into a model-ready row.

    ``raw_input`` must contain every key in FEATURES. Returns a (1, len(FEATURES))
    numpy array after applying the cached StandardScaler.
    """
    missing = [c for c in FEATURES if c not in raw_input]
    if missing:
        raise ValueError(f"Missing required input feature(s): {missing}")

    row = pd.DataFrame([{c: raw_input[c] for c in FEATURES}], columns=FEATURES)

    if scaler_path not in _scaler_cache:
        with _scaler_cache_lock:
            if scaler_path not in _scaler_cache:
                _scaler_cache[scaler_path] = joblib.load(scaler_path)
    scaler = _scaler_cache[scaler_path]
    return scaler.transform(row)


def run_preprocessing():
    """CLI helper: load + scale + dump to CSV for the notebook."""
    print("Loading data...")
    df = load_data()
    print(f"Loaded {df.shape}, classes: {df['fault_label_name'].value_counts().to_dict()}")
    X_train, X_test, y_train, y_test = split_and_scale(df)
    X_train.to_csv("X_train.csv", index=False)
    X_test.to_csv("X_test.csv", index=False)
    y_train.to_csv("y_train.csv", index=False)
    y_test.to_csv("y_test.csv", index=False)
    print(f"  X_train: {X_train.shape}")
    print(f"  X_test:  {X_test.shape}")


if __name__ == "__main__":
    run_preprocessing()
