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

# Demo holdout. A fixed 20% stratified row-level slice is useful for readable
# dashboard demos because small samples cover the full class vocabulary. When
# a dataset provides real episode/run identifiers, training can use
# ``split_episode_pool_and_holdout`` for a stricter grouped holdout instead.
HOLDOUT_RATIO = 0.2
HOLDOUT_RANDOM_STATE = 42

# Preferred group identifiers for honest episode-level splits. The fixed
# dataset should include one of these columns; until then we derive a stable
# episode group from contiguous fault-label runs so sequence models do not
# train/test on overlapping windows from the same run.
EPISODE_ID_CANDIDATES = [
    "episode_id",
    "scenario_id",
    "run_id",
    "simulation_run_id",
    "trajectory_id",
]


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

    # Drop rows with missing fault labels (both NaN and string "nan")
    df = df[df["fault_label"].notna()].copy()
    df = df[df["fault_label"].astype(str).str.lower().str.strip() != "nan"].reset_index(drop=True)
    
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
    """Split the full dataset into an 80% pool and a 20% row-level demo holdout.

    Stratified on ``fault_label`` with a fixed random seed so the split is
    identical for every caller. The pool index order is preserved for
    reproducibility.
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


def find_episode_column(df: pd.DataFrame) -> str | None:
    """Return the first known episode/run identifier column in ``df``."""
    for column in EPISODE_ID_CANDIDATES:
        if column in df.columns:
            return column
    return None


def episode_groups(df: pd.DataFrame) -> pd.Series:
    """Return a group id per row for episode-aware splitting.

    Prefer explicit dataset columns such as ``episode_id`` or ``scenario_id``.
    If the current CSV does not have one, fall back to contiguous label runs.
    That fallback is intentionally conservative for telemetry windows: it
    prevents a train window and a test window from sharing neighbouring frames.
    """
    explicit_column = find_episode_column(df)
    if explicit_column is not None:
        return df[explicit_column].astype(str).reset_index(drop=True)

    if "fault_label" not in df.columns:
        return pd.Series(df.index.astype(str), index=df.index).reset_index(drop=True)

    labels = df["fault_label"].reset_index(drop=True)
    return labels.ne(labels.shift()).cumsum().astype(str)


def _group_labels(df: pd.DataFrame, groups: pd.Series) -> pd.DataFrame:
    labels = df["fault_label"].reset_index(drop=True)
    group_frame = pd.DataFrame({"group": groups.reset_index(drop=True), "label": labels})
    return (
        group_frame.groupby("group", sort=False)["label"]
        .agg(lambda s: int(s.mode().iloc[0]))
        .reset_index()
    )


def _can_stratify_group_labels(labels: pd.Series, test_size: float) -> bool:
    counts = labels.value_counts()
    if counts.empty or (counts < 2).any():
        return False
    n_groups = len(labels)
    n_test = max(1, int(round(n_groups * test_size)))
    n_train = n_groups - n_test
    return n_test >= labels.nunique() and n_train >= labels.nunique()


def split_episode_pool_and_holdout(
    df: pd.DataFrame,
    holdout_ratio: float = HOLDOUT_RATIO,
    random_state: int = HOLDOUT_RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split by episode/run group, stratifying group labels when possible."""
    groups = episode_groups(df)
    group_frame = _group_labels(df, groups)
    stratify = (
        group_frame["label"]
        if _can_stratify_group_labels(group_frame["label"], holdout_ratio)
        else None
    )
    train_groups, holdout_groups = train_test_split(
        group_frame["group"],
        test_size=holdout_ratio,
        random_state=random_state,
        stratify=stratify,
    )
    train_set = set(train_groups.astype(str))
    holdout_set = set(holdout_groups.astype(str))
    train_mask = groups.astype(str).isin(train_set)
    holdout_mask = groups.astype(str).isin(holdout_set)
    training_pool = df.loc[train_mask.values].reset_index(drop=True)
    holdout = df.loc[holdout_mask.values].reset_index(drop=True)
    return training_pool, holdout


def split_temporal_pool_and_holdout(
    df: pd.DataFrame,
    holdout_ratio: float = HOLDOUT_RATIO,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chronological split for drift/generalisation diagnostics."""
    if df.empty:
        return df.copy(), df.copy()
    ordered = df.sort_values("timestamp_s").reset_index(drop=True) if "timestamp_s" in df.columns else df.reset_index(drop=True)
    split_idx = max(1, int(len(ordered) * (1.0 - holdout_ratio)))
    split_idx = min(split_idx, len(ordered) - 1) if len(ordered) > 1 else 1
    return (
        ordered.iloc[:split_idx].copy().reset_index(drop=True),
        ordered.iloc[split_idx:].copy().reset_index(drop=True),
    )


def get_training_pool(df: pd.DataFrame) -> pd.DataFrame:
    """Convenience: return only the 80% training pool."""
    return split_training_pool_and_holdout(df)[0]


def get_demo_holdout(df: pd.DataFrame) -> pd.DataFrame:
    """Convenience: return only the 20% demo holdout the models never see."""
    return split_training_pool_and_holdout(df)[1]


def engineer_features(df: pd.DataFrame, window: int = 0, step: int = 0):
    """
    Feature engineering with optional sliding window support.

    Args:
        df:     DataFrame containing FEATURES columns and 'fault_label'.
        window: Sliding window size. If 0 (default), returns df unchanged
                (no-op — used by tree-based models and TabNet).
                If > 0, applies sliding window and returns (X, y) numpy arrays
                shaped [N_windows, window, len(FEATURES)] and [N_windows].
        step:   Step size between windows. Defaults to window // 2 (50% overlap).
                Ignored when window=0.

    Returns:
        window=0: original DataFrame (unchanged)
        window>0: tuple (X_windows, y_windows)
                  X_windows shape: [N, window, len(FEATURES)]
                  y_windows shape: [N] — label of the last row in each window
    """
    if window == 0:
        return df  # no-op for tree-based models and TabNet

    import numpy as np

    X = df[FEATURES].values
    y = df['fault_label'].values

    effective_step = step if step > 0 else window // 2

    windows_X = []
    windows_y = []

    for i in range(0, len(X) - window + 1, effective_step):
        windows_X.append(X[i:i + window])
        windows_y.append(y[i + window - 1])  # label of last row in window

    return np.array(windows_X), np.array(windows_y)


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
