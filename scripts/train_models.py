#!/usr/bin/env python3
"""Retrain every model in services/ai/ai/models/ from scratch.

Hyperparameter grids and split configurations track the original notebook:

    SPLIT_CONFIGS       = (0.8/0.1/0.1), (0.7/0.2/0.1), (0.6/0.3/0.1),
                          (0.7/0.1/0.2), (0.6/0.1/0.3)
    N_ESTIMATORS_LIST   = [100, 200]
    MAX_DEPTH_LIST      = [3, 5]
    LEARNING_RATE_LIST  = [0.01, 0.1]
    EPOCHS_LIST         = [10, 20, 50]
    HIDDEN_DIM_LIST     = [32, 64]
    LATENT_DIM_LIST     = [8, 16]
    LSTM_LR_LIST        = [0.001, 0.01]

For each model the (split × hyperparam) grid is swept and the best-F1 model is
saved as best_<family>.pkl/.pth. Per-model best metadata is also saved.
Splits are episode/group-aware when the dataset provides an episode/run column;
otherwise the script derives conservative contiguous-run groups from labels.
CNN/Bi-LSTM windows are created only after raw train/val/test group membership
is fixed, so overlapping windows cannot cross split boundaries.

After all sweeps, the overall best model (Global Winner) is selected.
If the winner is a Tree/CNN/Bi-LSTM model, it is retrained on (train+val) 
of its own best split and saved to services/ai/ai/models/shared/.

This is the file the runtime registry actually reads.

Tree models train on CPU in <1s each; LSTM-AE uses GPU when available.
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import f_classif
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    roc_auc_score,
)
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import DataLoader, TensorDataset

import lightgbm as lgb
import xgboost as xgb
try:
    from pytorch_tabnet.tab_model import TabNetClassifier
except Exception as exc:  # pragma: no cover - optional training dependency
    TabNetClassifier = None  # type: ignore[assignment]
    TABNET_IMPORT_ERROR = exc
else:
    TABNET_IMPORT_ERROR = None

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_ROOT = REPO_ROOT / "services" / "ai"
MODELS_ROOT = AI_ROOT / "ai" / "models"
SHARED_DIR = MODELS_ROOT / "shared"

sys.path.insert(0, str(AI_ROOT))
from preprocessing import (  # noqa: E402
    CLASS_NAMES,
    FEATURES,
    episode_groups,
    engineer_features,
    find_episode_column,
    load_data,
    split_episode_pool_and_holdout,
    split_training_pool_and_holdout,
)


def build_scaling_pipeline() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
from ai.lstm_classifier import LSTMAutoencoderClassifier  # noqa: E402
from ai.cnn_classifier import CNNClassifier  # noqa: E402
from ai.bilstm_classifier import BiLSTMClassifier  # noqa: E402

# ── Notebook cell 1: CONFIGURATION ─────────────────────────────────────────
SPLIT_CONFIGS = [
    (0.8, 0.1, 0.1),
    (0.7, 0.2, 0.1),
    (0.6, 0.3, 0.1),
    (0.7, 0.1, 0.2),
    (0.6, 0.1, 0.3),
]
N_ESTIMATORS_LIST = [100, 200]
MAX_DEPTH_LIST = [3, 5]
LEARNING_RATE_LIST = [0.01, 0.1]
# LSTM epochs are capped at 20 to discourage memorisation of the synthetic
# dataset. The notebook's CELL 2 mirrors this cap one-for-one.
EPOCHS_LIST = [10, 20]
HIDDEN_DIM_LIST = [32, 64]
LATENT_DIM_LIST = [8, 16]
LSTM_LR_LIST = [0.001, 0.01]
LSTM_BATCH_SIZE = 64
LSTM_DROPOUT = 0.2
LSTM_WEIGHT_DECAY = 1e-4
LAMBDA_RECON = 1.0
LAMBDA_CLS = 1.0
RANDOM_STATE = 42

CNN_EPOCHS = [20, 40]
CNN_BATCH_SIZE = 64
CNN_CONV_CHANNELS_LIST = [16, 32]
CNN_HIDDEN_DIMS = [32, 64]
CNN_KERNEL_SIZES = [3, 5]
CNN_LR_LIST = [0.001, 0.01]
CNN_DROPOUT = 0.1
CNN_WINDOW_SIZE = 30

TABNET_N_D_LIST = [8, 16]
TABNET_N_STEPS_LIST = [2, 3]

BILSTM_EPOCHS = [50, 100]
BILSTM_BATCH_SIZE = 64
BILSTM_HIDDEN_DIMS = [64, 128]
BILSTM_LAYERS = [1, 2]
BILSTM_LR_LIST = [0.005, 0.01]
BILSTM_DROPOUT = 0.3
BILSTM_WINDOW_SIZE = 30


# ── Notebook cell 2: prepare_splits ────────────────────────────────────────
def _can_stratify(labels: pd.Series, test_size: float) -> bool:
    counts = labels.value_counts()
    if counts.empty or (counts < 2).any():
        return False
    n_items = len(labels)
    n_test = max(1, int(round(n_items * test_size)))
    n_train = n_items - n_test
    return n_test >= labels.nunique() and n_train >= labels.nunique()


def _group_label_table(y: pd.Series, groups: pd.Series) -> pd.DataFrame:
    frame = pd.DataFrame({
        "group": groups.reset_index(drop=True).astype(str),
        "label": y.reset_index(drop=True).astype(int),
    })
    return (
        frame.groupby("group", sort=False)["label"]
        .agg(lambda s: int(s.mode().iloc[0]))
        .reset_index()
    )


def _split_raw_indices(
    y: pd.Series,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    random_state: int,
    groups: pd.Series | None = None,
) -> tuple[list[int], list[int], list[int]]:
    """Split raw rows before any scaling/windowing.

    If ``groups`` is provided, split whole episode/run groups while preserving
    stratification at the group-majority-label level whenever the dataset has
    enough groups per class. This is the important bit for CNN/BiLSTM: windows
    are created only after these raw split memberships are fixed.
    """
    y_reset = y.reset_index(drop=True)
    if groups is None:
        row_idx = np.arange(len(y_reset))
        temp_idx, test_idx = train_test_split(
            row_idx, test_size=test_ratio, random_state=random_state, stratify=y_reset,
        )
        val_size_adjusted = val_ratio / (train_ratio + val_ratio)
        train_idx, val_idx = train_test_split(
            temp_idx, test_size=val_size_adjusted, random_state=random_state,
            stratify=y_reset.iloc[temp_idx],
        )
        return sorted(train_idx.tolist()), sorted(val_idx.tolist()), sorted(test_idx.tolist())

    groups_reset = groups.reset_index(drop=True).astype(str)
    group_table = _group_label_table(y_reset, groups_reset)
    test_stratify = (
        group_table["label"]
        if _can_stratify(group_table["label"], test_ratio)
        else None
    )
    train_val_groups, test_groups = train_test_split(
        group_table["group"],
        test_size=test_ratio,
        random_state=random_state,
        stratify=test_stratify,
    )

    train_val_table = group_table[group_table["group"].isin(set(train_val_groups))]
    val_size_adjusted = val_ratio / (train_ratio + val_ratio)
    val_stratify = (
        train_val_table["label"]
        if _can_stratify(train_val_table["label"], val_size_adjusted)
        else None
    )
    train_groups, val_groups = train_test_split(
        train_val_table["group"],
        test_size=val_size_adjusted,
        random_state=random_state,
        stratify=val_stratify,
    )

    train_set = set(train_groups.astype(str))
    val_set = set(val_groups.astype(str))
    test_set = set(test_groups.astype(str))
    train_idx = np.flatnonzero(groups_reset.isin(train_set).to_numpy())
    val_idx = np.flatnonzero(groups_reset.isin(val_set).to_numpy())
    test_idx = np.flatnonzero(groups_reset.isin(test_set).to_numpy())
    return sorted(train_idx.tolist()), sorted(val_idx.tolist()), sorted(test_idx.tolist())


def _windowize_split(
    X_part: pd.DataFrame,
    y_part: pd.Series,
    groups_part: pd.Series | None,
    window: int,
    step: int,
) -> tuple[np.ndarray, np.ndarray]:
    if groups_part is None:
        df_window = X_part.copy()
        df_window["fault_label"] = y_part.values
        return engineer_features(df_window, window=window, step=step)

    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    df_window = X_part.copy()
    df_window["fault_label"] = y_part.values
    df_window["_episode_group"] = groups_part.reset_index(drop=True).astype(str).values
    for _, group_df in df_window.groupby("_episode_group", sort=False):
        group_df = group_df.drop(columns=["_episode_group"])
        if len(group_df) < window:
            continue
        X_w, y_w = engineer_features(group_df, window=window, step=step)
        if len(X_w):
            xs.append(X_w)
            ys.append(y_w)
    if not xs:
        raise ValueError(
            f"No {window}-row windows could be built for this split. "
            "Use longer episodes or a smaller window size."
        )
    return np.concatenate(xs, axis=0), np.concatenate(ys, axis=0)


def prepare_splits(
    X: pd.DataFrame,
    y: pd.Series,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    random_state: int = RANDOM_STATE,
    scale_and_impute: bool = True,
    window: int = 0,
    step: int = 5,
    groups: pd.Series | None = None,
):
    train_idx, val_idx, test_idx = _split_raw_indices(
        y, train_ratio, val_ratio, test_ratio, random_state, groups=groups,
    )
    X_reset = X.reset_index(drop=True)
    y_reset = y.reset_index(drop=True).astype(int)
    groups_reset = groups.reset_index(drop=True).astype(str) if groups is not None else None

    X_train_raw = X_reset.iloc[train_idx].reset_index(drop=True)
    X_val_raw = X_reset.iloc[val_idx].reset_index(drop=True)
    X_test_raw = X_reset.iloc[test_idx].reset_index(drop=True)
    y_train = y_reset.iloc[train_idx].reset_index(drop=True)
    y_val = y_reset.iloc[val_idx].reset_index(drop=True)
    y_test = y_reset.iloc[test_idx].reset_index(drop=True)
    groups_train = groups_reset.iloc[train_idx].reset_index(drop=True) if groups_reset is not None else None
    groups_val = groups_reset.iloc[val_idx].reset_index(drop=True) if groups_reset is not None else None
    groups_test = groups_reset.iloc[test_idx].reset_index(drop=True) if groups_reset is not None else None

    if window > 0:
        if scale_and_impute:
            scaler = build_scaling_pipeline()
            X_train = pd.DataFrame(scaler.fit_transform(X_train_raw), columns=FEATURES)
            X_val = pd.DataFrame(scaler.transform(X_val_raw), columns=FEATURES)
            X_test = pd.DataFrame(scaler.transform(X_test_raw), columns=FEATURES)
        else:
            X_train, X_val, X_test = X_train_raw, X_val_raw, X_test_raw
            scaler = None

        X_train_w, y_train_w = _windowize_split(X_train, y_train, groups_train, window, step)
        X_val_w, y_val_w = _windowize_split(X_val, y_val, groups_val, window, step)
        X_test_w, y_test_w = _windowize_split(X_test, y_test, groups_test, window, step)
        return X_train_w, X_val_w, X_test_w, y_train_w, y_val_w, y_test_w, scaler

    if scale_and_impute:
        scaler = build_scaling_pipeline()
        X_train_s = pd.DataFrame(
            scaler.fit_transform(X_train_raw), columns=FEATURES, index=X_train_raw.index
        )
        X_val_s = pd.DataFrame(scaler.transform(X_val_raw), columns=FEATURES, index=X_val_raw.index)
        X_test_s = pd.DataFrame(
            scaler.transform(X_test_raw), columns=FEATURES, index=X_test_raw.index
        )
        return X_train_s, X_val_s, X_test_s, y_train, y_val, y_test, scaler

    return X_train_raw, X_val_raw, X_test_raw, y_train, y_val, y_test, None


# ── Notebook cell 3: evaluate_model (sans plotting) ────────────────────────
def evaluate(model, X_val, y_val, model_name: str, split_label: str, param: dict):
    y_pred = model.predict(X_val)
    y_prob = model.predict_proba(X_val)
    acc = accuracy_score(y_val, y_pred)
    f1 = f1_score(y_val, y_pred, average="macro")
    precision = precision_score(y_val, y_pred, average="macro", zero_division=0)
    try:
        auroc = roc_auc_score(y_val, y_prob, multi_class="ovr", average="macro")
    except ValueError:
        auroc = float("nan")
    param_str = ", ".join(f"{k}={v}" for k, v in param.items())
    print(
        f"[{model_name:>13}] split={split_label:<10} {param_str:<60}  "
        f"acc={acc:.4f}  f1={f1:.4f}  auroc={auroc:.4f}"
    )
    return {
        "model": model_name,
        "split": split_label,
        "param": param_str,
        "param_dict": dict(param),
        "accuracy": float(acc),
        "f1": float(f1),
        "precision": float(precision),
        "auroc": (None if np.isnan(auroc) else float(auroc)),
    }


def split_label(t: float, v: float, te: float) -> str:
    return f"{int(t*100)}/{int(v*100)}/{int(te*100)}"


def run_sanity_baselines(training_pool: pd.DataFrame, demo_holdout: pd.DataFrame) -> None:
    """Print shortcut diagnostics before expensive model sweeps.

    These are deliberately simple baselines. If a single shortcut feature is
    close to the full-feature score, the dataset is probably easier than the
    model leaderboard suggests.
    """
    print("\n=== Sanity baselines on canonical demo holdout ===")
    X_train = training_pool[FEATURES]
    y_train = training_pool["fault_label"].astype(int)
    X_holdout = demo_holdout[FEATURES]
    y_holdout = demo_holdout["fault_label"].astype(int)

    imputer = SimpleImputer(strategy="median")
    X_train_imp = imputer.fit_transform(X_train)
    f_scores, _ = f_classif(X_train_imp, y_train)
    ranking = (
        pd.DataFrame({"feature": FEATURES, "anova_f": f_scores})
        .sort_values("anova_f", ascending=False)
        .reset_index(drop=True)
    )
    top3 = ranking.head(3)["feature"].tolist()

    feature_sets = {
        "temperature_only": ["temperature_c"] if "temperature_c" in FEATURES else [FEATURES[-1]],
        "no_temperature": [c for c in FEATURES if c != "temperature_c"],
        "top3_anova": top3,
        "full": FEATURES,
    }
    model = lgb.LGBMClassifier(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.1,
        random_state=RANDOM_STATE,
        class_weight="balanced",
        verbose=-1,
    )

    results = []
    for name, columns in feature_sets.items():
        pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", model.__class__(**model.get_params())),
        ])
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="X does not have valid feature names")
            pipe.fit(X_train[columns], y_train)
            pred = pipe.predict(X_holdout[columns])
        results.append({
            "baseline": name,
            "features": columns,
            "feature_count": len(columns),
            "accuracy": float(accuracy_score(y_holdout, pred)),
            "macro_f1": float(f1_score(y_holdout, pred, average="macro")),
            "precision": float(precision_score(y_holdout, pred, average="macro", zero_division=0)),
        })

    out = pd.DataFrame(results).sort_values("macro_f1", ascending=False)
    print("Top ANOVA features:")
    print(ranking.head(10).to_string(index=False, formatters={"anova_f": lambda x: f"{x:.3f}"}))
    print("\nShortcut baseline table:")
    print(out[["baseline", "feature_count", "accuracy", "macro_f1", "precision"]].to_string(
        index=False,
        formatters={
            "accuracy": lambda x: f"{x:.4f}",
            "macro_f1": lambda x: f"{x:.4f}",
            "precision": lambda x: f"{x:.4f}",
        },
    ))

    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "top_anova_features": ranking.head(10).to_dict(orient="records"),
        "baselines": results,
        "notes": (
            "If temperature_only is close to full, the dataset is shortcut-dominated. "
            "If no_temperature collapses, non-temperature channels are not carrying the labels."
        ),
    }
    (SHARED_DIR / "sanity_baselines.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"[save] {SHARED_DIR}/sanity_baselines.json")


# ── Notebook cell 4: RandomForest sweep ────────────────────────────────────
def sweep_random_forest(X, y, groups: pd.Series | None = None):
    print("\n=== RandomForest sweep (5 splits × 2 × 2 = 20 configs) ===")
    best = {"f1": -1.0}
    for tr, vr, te in SPLIT_CONFIGS:
        X_train, X_val, _, y_train, y_val, _, scaler = prepare_splits(
            X, y, tr, vr, te, scale_and_impute=True, groups=groups,
        )
        for n in N_ESTIMATORS_LIST:
            for d in MAX_DEPTH_LIST:
                model = RandomForestClassifier(
                    n_estimators=n, max_depth=d,
                    random_state=RANDOM_STATE, class_weight="balanced",
                )
                model.fit(X_train, y_train)
                result = evaluate(
                    model, X_val, y_val, "RandomForest",
                    split_label(tr, vr, te),
                    {"n_estimators": n, "max_depth": d},
                )
                if result["f1"] > best["f1"]:
                    best = {**result, "model_obj": model, "scaler": scaler,
                            "split_tuple": (tr, vr, te)}
    print(f"--- best RF: {best['split']}  {best['param']}  f1={best['f1']:.4f}")
    return best


# ── Notebook cell 5: LightGBM sweep ────────────────────────────────────────
def sweep_lightgbm(X, y, groups: pd.Series | None = None):
    print("\n=== LightGBM sweep (5 splits × 2 × 2 × 2 = 40 configs) ===")
    best = {"f1": -1.0}
    for tr, vr, te in SPLIT_CONFIGS:
        X_train, X_val, _, y_train, y_val, _, scaler = prepare_splits(
            X, y, tr, vr, te, scale_and_impute=False, groups=groups,
        )
        for n in N_ESTIMATORS_LIST:
            for d in MAX_DEPTH_LIST:
                for lr in LEARNING_RATE_LIST:
                    model = lgb.LGBMClassifier(
                        n_estimators=n, max_depth=d, learning_rate=lr,
                        random_state=RANDOM_STATE, class_weight="balanced",
                        verbose=-1,
                    )
                    model.fit(X_train, y_train)
                    result = evaluate(
                        model, X_val, y_val, "LightGBM",
                        split_label(tr, vr, te),
                        {"n_estimators": n, "max_depth": d, "learning_rate": lr},
                    )
                    if result["f1"] > best["f1"]:
                        best = {**result, "model_obj": model, "scaler": scaler,
                                "split_tuple": (tr, vr, te)}
    print(f"--- best LightGBM: {best['split']}  {best['param']}  f1={best['f1']:.4f}")
    return best


# ── Notebook cell 6: XGBoost sweep ─────────────────────────────────────────
def sweep_xgboost(X, y, groups: pd.Series | None = None):
    print("\n=== XGBoost sweep (5 splits × 2 × 2 × 2 = 40 configs) ===")
    best = {"f1": -1.0}
    for tr, vr, te in SPLIT_CONFIGS:
        X_train, X_val, _, y_train, y_val, _, scaler = prepare_splits(
            X, y, tr, vr, te, scale_and_impute=False, groups=groups,
        )
        for n in N_ESTIMATORS_LIST:
            for d in MAX_DEPTH_LIST:
                for lr in LEARNING_RATE_LIST:
                    model = xgb.XGBClassifier(
                        n_estimators=n, max_depth=d, learning_rate=lr,
                        random_state=RANDOM_STATE,
                        eval_metric="mlogloss", verbosity=0,
                    )
                    model.fit(X_train, y_train)
                    result = evaluate(
                        model, X_val, y_val, "XGBoost",
                        split_label(tr, vr, te),
                        {"n_estimators": n, "max_depth": d, "learning_rate": lr},
                    )
                    if result["f1"] > best["f1"]:
                        best = {**result, "model_obj": model, "scaler": scaler,
                                "split_tuple": (tr, vr, te)}
    print(f"--- best XGBoost: {best['split']}  {best['param']}  f1={best['f1']:.4f}")
    return best


# ── Notebook cell 7: LSTM-AE+CLS sweep ─────────────────────────────────────
def sweep_lstm_ae(X, y, num_classes: int, groups: pd.Series | None = None):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    total = (
        len(SPLIT_CONFIGS) * len(EPOCHS_LIST) * len(HIDDEN_DIM_LIST)
        * len(LATENT_DIM_LIST) * len(LSTM_LR_LIST)
    )
    print(f"\n=== LSTM-AE+CLS sweep ({len(SPLIT_CONFIGS)} splits × "
          f"{len(EPOCHS_LIST)} × {len(HIDDEN_DIM_LIST)} × {len(LATENT_DIM_LIST)} × "
          f"{len(LSTM_LR_LIST)} = {total} configs) on {device} ===")
    if device.type == "cuda":
        print(f"[env] {torch.cuda.get_device_name(0)}")
    input_dim = len(FEATURES)

    best = {"f1": -1.0}
    config_idx = 0
    for tr, vr, te in SPLIT_CONFIGS:
        X_train, X_val, X_test, y_train, y_val, y_test, scaler = prepare_splits(
            X, y, tr, vr, te, scale_and_impute=True, groups=groups,
        )
        X_train_t = torch.tensor(X_train.values, dtype=torch.float32, device=device).unsqueeze(1)
        X_val_t = torch.tensor(X_val.values, dtype=torch.float32, device=device).unsqueeze(1)
        y_train_t = torch.tensor(y_train.values, dtype=torch.long, device=device)
        y_val_np = y_val.values

        loader_dataset = TensorDataset(X_train_t, y_train_t)
        loader = DataLoader(loader_dataset, batch_size=LSTM_BATCH_SIZE, shuffle=True)

        for n_epochs in EPOCHS_LIST:
            for hidden_dim in HIDDEN_DIM_LIST:
                for latent_dim in LATENT_DIM_LIST:
                    for lr in LSTM_LR_LIST:
                        config_idx += 1
                        t0 = time.time()
                        model = LSTMAutoencoderClassifier(
                            input_dim=input_dim, hidden_dim=hidden_dim,
                            latent_dim=latent_dim, num_classes=num_classes,
                            dropout=LSTM_DROPOUT,
                        ).to(device)
                        optimizer = torch.optim.Adam(
                            model.parameters(), lr=lr, weight_decay=LSTM_WEIGHT_DECAY,
                        )
                        recon_loss_fn = nn.MSELoss()
                        cls_loss_fn = nn.CrossEntropyLoss()

                        model.train()
                        for _ in range(n_epochs):
                            for X_batch, y_batch in loader:
                                optimizer.zero_grad()
                                X_recon, logits = model(X_batch)
                                loss = (
                                    LAMBDA_RECON * recon_loss_fn(X_recon, X_batch)
                                    + LAMBDA_CLS * cls_loss_fn(logits, y_batch)
                                )
                                loss.backward()
                                optimizer.step()

                        model.eval()
                        with torch.no_grad():
                            _, val_logits = model(X_val_t)
                            y_pred = torch.argmax(F.softmax(val_logits, dim=-1), dim=-1).cpu().numpy()
                        acc = float(accuracy_score(y_val_np, y_pred))
                        f1 = float(f1_score(y_val_np, y_pred, average="macro"))
                        precision = float(precision_score(y_val_np, y_pred, average="macro", zero_division=0))

                        flag = ""
                        if f1 > best["f1"]:
                            flag = "  *** new best"
                            best = {
                                "model": "LSTM-AE", "split": split_label(tr, vr, te),
                                "param": f"epochs={n_epochs}, hidden={hidden_dim}, "
                                         f"latent={latent_dim}, lr={lr}",
                                "param_dict": {
                                    "epochs": n_epochs, "hidden": hidden_dim,
                                    "latent": latent_dim, "lr": lr,
                                    "batch": LSTM_BATCH_SIZE,
                                    "lambda_recon": LAMBDA_RECON,
                                    "lambda_cls": LAMBDA_CLS,
                                },
                                "accuracy": acc, "f1": f1, "precision": precision,
                                "auroc": None,
                                "state_dict": {k: v.cpu().clone() for k, v in model.state_dict().items()},
                                "scaler": scaler,
                                "split_tuple": (tr, vr, te),
                                "X_test_t_cpu": X_test.values,
                                "y_test": y_test.values,
                            }
                        print(
                            f"[{config_idx:>3}/{total}] split={split_label(tr,vr,te):<10} "
                            f"epochs={n_epochs:<3} h={hidden_dim:<3} l={latent_dim:<3} "
                            f"lr={lr:<6} acc={acc:.4f} f1={f1:.4f} ({time.time()-t0:.1f}s){flag}"
                        )

    print(f"--- best LSTM-AE: {best['split']}  {best['param']}  f1={best['f1']:.4f}")
    return best, device

# ── Notebook cell 8: TabNet sweep ──────────────────────────────────────────
def sweep_tabnet(X, y, groups: pd.Series | None = None):
    print("\n=== TabNet sweep (1 fixed split × 2 × 2 = 4 configs) ===")
    if TabNetClassifier is None:
        print(f"[TabNet] skipped: pytorch-tabnet unavailable ({TABNET_IMPORT_ERROR})")
        return {
            "model": "TabNet",
            "split": "skipped",
            "param": "skipped",
            "param_dict": {},
            "accuracy": 0.0,
            "f1": -1.0,
            "precision": 0.0,
            "auroc": None,
            "skipped": True,
            "skip_reason": f"pytorch-tabnet unavailable: {TABNET_IMPORT_ERROR}",
        }
    best = {"f1": -1.0}
    
    # Fixed split to save extreme training times for DL models
    tr, vr, te = 0.8, 0.1, 0.1
    X_train, X_val, X_test, y_train, y_val, y_test, scaler = prepare_splits(
        X, y, tr, vr, te, scale_and_impute=True, groups=groups,
    )
    
    for n_d in TABNET_N_D_LIST:
        for n_steps in TABNET_N_STEPS_LIST:
            model = TabNetClassifier(
                n_d=n_d, n_a=n_d,
                n_steps=n_steps,
                gamma=1.5,
                n_independent=1,
                n_shared=2,
                momentum=0.02,
                mask_type='sparsemax',
                optimizer_fn=torch.optim.Adam,
                optimizer_params=dict(lr=2e-2, weight_decay=1e-3),
                scheduler_params={"step_size": 10, "gamma": 0.9},
                scheduler_fn=torch.optim.lr_scheduler.StepLR,
                verbose=0,
                seed=RANDOM_STATE,
            )
            model.fit(
                X_train.values, y_train.values,
                eval_set=[(X_val.values, y_val.values)],
                eval_name=['val'],
                eval_metric=['balanced_accuracy'],
                weights=1,
                max_epochs=50,
                patience=7,
                batch_size=256,
                virtual_batch_size=128,
                num_workers=0,
                drop_last=False,
            )
            
            # evaluate expects pd.DataFrame, TabNet predict expects numpy array.
            # evaluate internally calls model.predict(X_val) so we wrap it.
            class TabNetWrapper:
                def __init__(self, m):
                    self.m = m
                def predict(self, X):
                    return self.m.predict(X.values if isinstance(X, pd.DataFrame) else X)
                def predict_proba(self, X):
                    return self.m.predict_proba(X.values if isinstance(X, pd.DataFrame) else X)
                def save_model(self, path):
                    self.m.save_model(path)

            wrapped_model = TabNetWrapper(model)
            
            result = evaluate(
                wrapped_model, X_val, y_val, "TabNet",
                split_label(tr, vr, te),
                {"n_d": n_d, "n_steps": n_steps},
            )
            if result["f1"] > best.get("f1", -1.0):
                best = {**result, "model_obj": wrapped_model, "scaler": scaler,
                        "split_tuple": (tr, vr, te)}
                
    print(f"--- best TabNet: {best['split']}  {best['param']}  f1={best['f1']:.4f}")
    return best

# ── Notebook cell 9: CNN sweep ─────────────────────────────────────────────
def sweep_cnn(X, y, num_classes: int, groups: pd.Series | None = None):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    total = (
        len(SPLIT_CONFIGS) * len(CNN_EPOCHS) * len(CNN_CONV_CHANNELS_LIST)
        * len(CNN_HIDDEN_DIMS) * len(CNN_KERNEL_SIZES) * len(CNN_LR_LIST)
    )
    print(f"\n=== CNN sweep ({len(SPLIT_CONFIGS)} splits × {len(CNN_EPOCHS)} × "
          f"{len(CNN_CONV_CHANNELS_LIST)} × {len(CNN_HIDDEN_DIMS)} × "
          f"{len(CNN_KERNEL_SIZES)} × {len(CNN_LR_LIST)} = {total} configs) on {device} ===")
    if device.type == "cuda":
        print(f"[env] {torch.cuda.get_device_name(0)}")

    best = {"f1": -1.0}
    config_idx = 0
    input_dim = len(FEATURES)
    cnn_window_size = CNN_WINDOW_SIZE

    for tr, vr, te in SPLIT_CONFIGS:
        X_train, X_val, _, y_train, y_val, _, scaler = prepare_splits(
            X, y, tr, vr, te, scale_and_impute=True, window=cnn_window_size, groups=groups,
        )

        unique_classes = np.unique(y_train)
        weights = compute_class_weight(class_weight="balanced", classes=unique_classes, y=y_train)
        class_weights = torch.tensor(weights, dtype=torch.float32, device=device)

        X_train_t = torch.tensor(X_train, dtype=torch.float32, device=device)
        X_val_t = torch.tensor(X_val, dtype=torch.float32, device=device)
        y_train_t = torch.tensor(y_train, dtype=torch.long, device=device)
        y_val_np = y_val

        loader = DataLoader(
            TensorDataset(X_train_t, y_train_t), batch_size=CNN_BATCH_SIZE, shuffle=True,
        )

        for n_epochs in CNN_EPOCHS:
            for conv_channels in CNN_CONV_CHANNELS_LIST:
                for hidden_dim in CNN_HIDDEN_DIMS:
                    for kernel_size in CNN_KERNEL_SIZES:
                        for lr in CNN_LR_LIST:
                            config_idx += 1
                            t0 = time.time()
                            model = CNNClassifier(
                                input_dim=input_dim,
                                num_classes=num_classes,
                                window_size=cnn_window_size,
                                conv_channels=conv_channels,
                                kernel_size=kernel_size,
                                hidden_dim=hidden_dim,
                                dropout=CNN_DROPOUT,
                            ).to(device)
                            optimizer = torch.optim.Adam(
                                model.parameters(), lr=lr, weight_decay=1e-4,
                            )
                            loss_fn = nn.CrossEntropyLoss(weight=class_weights)

                            model.train()
                            for _ in range(n_epochs):
                                for X_batch, y_batch in loader:
                                    optimizer.zero_grad()
                                    logits = model(X_batch)
                                    loss = loss_fn(logits, y_batch)
                                    loss.backward()
                                    optimizer.step()

                            model.eval()
                            with torch.no_grad():
                                val_logits = model(X_val_t)
                                y_pred = torch.argmax(F.softmax(val_logits, dim=-1), dim=-1).cpu().numpy()
                            acc = float(accuracy_score(y_val_np, y_pred))
                            f1 = float(f1_score(y_val_np, y_pred, average="macro"))
                            precision = float(precision_score(y_val_np, y_pred, average="macro", zero_division=0))

                            if f1 > best["f1"]:
                                best = {
                                    "model": "CNN", "split": split_label(tr, vr, te),
                                    "param": f"epochs={n_epochs}, conv_channels={conv_channels}, "
                                             f"hidden={hidden_dim}, kernel={kernel_size}, lr={lr}",
                                    "param_dict": {
                                        "epochs": n_epochs,
                                        "conv_channels": conv_channels,
                                        "hidden_dim": hidden_dim,
                                        "kernel_size": kernel_size,
                                        "lr": lr,
                                        "dropout": CNN_DROPOUT,
                                        "window": cnn_window_size,
                                    },
                                    "accuracy": acc,
                                    "f1": f1,
                                    "precision": precision,
                                    "auroc": None,
                                    "state_dict": {k: v.cpu().clone() for k, v in model.state_dict().items()},
                                    "scaler": scaler,
                                    "split_tuple": (tr, vr, te),
                                }
                            print(
                                f"[{config_idx:>3}/{total}] split={split_label(tr,vr,te):<10} "
                                f"epochs={n_epochs:<3} cc={conv_channels:<3} h={hidden_dim:<3} "
                                f"k={kernel_size:<3} lr={lr:<6} acc={acc:.4f} f1={f1:.4f} "
                                f"({time.time()-t0:.1f}s)"
                            )

    print(f"--- best CNN: {best['split']}  {best['param']}  f1={best['f1']:.4f}")
    return best, device

# ── Notebook cell 10: Bi-LSTM sweep ────────────────────────────────────────
def sweep_bilstm(X, y, num_classes: int, groups: pd.Series | None = None):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n=== Bi-LSTM sweep on {device} ===")
    
    best = {"f1": -1.0}
    input_dim = len(FEATURES)
    window_size = BILSTM_WINDOW_SIZE
    total = len(SPLIT_CONFIGS) * len(BILSTM_EPOCHS) * len(BILSTM_HIDDEN_DIMS) * len(BILSTM_LAYERS) * len(BILSTM_LR_LIST)
    config_idx = 0

    for tr, vr, te in SPLIT_CONFIGS:
        X_train, X_val, _, y_train, y_val, _, scaler = prepare_splits(
            X, y, tr, vr, te, scale_and_impute=True, window=window_size, groups=groups,
        )

        unique_classes = np.unique(y_train)
        weights = compute_class_weight(class_weight="balanced", classes=unique_classes, y=y_train)
        class_weights = torch.tensor(weights, dtype=torch.float32, device=device)

        X_train_t = torch.tensor(X_train, dtype=torch.float32, device=device)
        X_val_t = torch.tensor(X_val, dtype=torch.float32, device=device)
        y_train_t = torch.tensor(y_train, dtype=torch.long, device=device)
        y_val_np = y_val

        loader = DataLoader(
            TensorDataset(X_train_t, y_train_t), batch_size=BILSTM_BATCH_SIZE, shuffle=True,
        )

        for n_epochs in BILSTM_EPOCHS:
            for hidden_dim in BILSTM_HIDDEN_DIMS:
                for num_layers in BILSTM_LAYERS:
                    for lr in BILSTM_LR_LIST:
                        config_idx += 1
                        t0 = time.time()
                        model = BiLSTMClassifier(
                            input_dim=input_dim,
                            num_classes=num_classes,
                            window_size=window_size,
                            hidden_dim=hidden_dim,
                            num_layers=num_layers,
                            dropout=BILSTM_DROPOUT,
                        ).to(device)
                        
                        optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
                        loss_fn = nn.CrossEntropyLoss(weight=class_weights)

                        model.train()
                        for _ in range(n_epochs):
                            for X_batch, y_batch in loader:
                                optimizer.zero_grad()
                                logits = model(X_batch)
                                loss = loss_fn(logits, y_batch)
                                loss.backward()
                                optimizer.step()

                        model.eval()
                        with torch.no_grad():
                            val_logits = model(X_val_t)
                            y_pred = torch.argmax(F.softmax(val_logits, dim=-1), dim=-1).cpu().numpy()
                        acc = float(accuracy_score(y_val_np, y_pred))
                        f1 = float(f1_score(y_val_np, y_pred, average="macro"))
                        precision = float(precision_score(y_val_np, y_pred, average="macro", zero_division=0))

                        if f1 > best["f1"]:
                            best = {
                                "model": "Bi-LSTM", "split": split_label(tr, vr, te),
                                "param_dict": {
                                    "epochs": n_epochs,
                                    "hidden_dim": hidden_dim,
                                    "num_layers": num_layers,
                                    "lr": lr,
                                    "dropout": BILSTM_DROPOUT,
                                    "window": window_size,
                                },
                                "accuracy": acc, "f1": f1, "precision": precision, "auroc": None,
                                "state_dict": {k: v.cpu().clone() for k, v in model.state_dict().items()},
                                "scaler": scaler, "split_tuple": (tr, vr, te),
                            }
                        print(
                            f"[{config_idx:>3}/{total}] split={split_label(tr,vr,te):<10} "
                            f"epochs={n_epochs:<3} h={hidden_dim:<3} layers={num_layers:<3} "
                            f"lr={lr:<6} acc={acc:.4f} f1={f1:.4f} ({time.time()-t0:.1f}s)"
                        )

    print(f"--- best Bi-LSTM: {best['split']}  f1={best['f1']:.4f}")
    return best, device
# ── Saving ─────────────────────────────────────────────────────────────────
def _final_report(y_true, y_pred, label: str) -> dict[str, float]:
    seen = sorted(set(int(v) for v in list(y_true) + list(y_pred)))
    names = [CLASS_NAMES[i] if 0 <= i < len(CLASS_NAMES) else str(i) for i in seen]
    print(f"\n=== {label} held-out test set ===")
    print(classification_report(y_true, y_pred, labels=seen, target_names=names, zero_division=0))
    return {
        "test_accuracy": float(accuracy_score(y_true, y_pred)),
        "test_f1": float(f1_score(y_true, y_pred, average="macro")),
        "test_precision": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
    }


def save_tree_artifact(best: dict, demo_holdout: pd.DataFrame, out_dir: Path,
                       artifact_name: str, family: str, supports_tree_xai: bool):
    out_dir.mkdir(parents=True, exist_ok=True)
    if best["scaler"] is not None:
        X_holdout = pd.DataFrame(best["scaler"].transform(demo_holdout[FEATURES]), columns=FEATURES)
    else:
        X_holdout = demo_holdout[FEATURES].copy()

    y_holdout = demo_holdout["fault_label"].astype(int)
    y_pred = best["model_obj"].predict(X_holdout)
    test_metrics = _final_report(y_holdout.values, y_pred, family)

    joblib.dump(best["model_obj"], out_dir / artifact_name)
    metadata = {
        "model_name": artifact_name,
        "model_family": family,
        "trained_on_dataset": "dtx_ai_master_dataset.csv",
        "feature_count": len(FEATURES),
        "num_classes": len(CLASS_NAMES),
        "feature_order_ref": "services/ai/models/shared/feature_order.json",
        "scaler_required": best["scaler"] is not None,
        "class_mapping": {str(i): n for i, n in enumerate(CLASS_NAMES)},
        "training_split": best["split"],
        "best_params": best["param_dict"],
        "metrics": {
            "val_accuracy": round(best["accuracy"], 6),
            "val_f1": round(best["f1"], 6),
            "val_precision": round(best["precision"], 6),
            "val_auroc": (None if best["auroc"] is None else round(best["auroc"], 6)),
            **{k: round(v, 6) for k, v in test_metrics.items()},
        },
        "decision_type": "multiclass_classifier",
        "default_threshold": None,
        "supports_tree_xai": supports_tree_xai,
        "notes": (
            "Trained via scripts/train_models.py with stratified group-aware "
            "splits when episode/run groups are available."
        ),
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"[save] {out_dir}/{artifact_name}  +  metadata.json")


def save_lstm_artifact(best: dict, device: torch.device, num_classes: int,
                       demo_holdout: pd.DataFrame):
    out_dir = MODELS_ROOT / "lstm_ae"
    out_dir.mkdir(parents=True, exist_ok=True)
    pth_path = out_dir / "best_lstmae.pth"
    torch.save(best["state_dict"], pth_path)

    # Reconstruct best model for honest test eval against the demo holdout.
    p = best["param_dict"]
    final_model = LSTMAutoencoderClassifier(
        input_dim=len(FEATURES), hidden_dim=p["hidden"],
        latent_dim=p["latent"], num_classes=num_classes,
        dropout=LSTM_DROPOUT,
    ).to(device)
    final_model.load_state_dict(best["state_dict"])
    final_model.eval()

    X_holdout = best["scaler"].transform(demo_holdout[FEATURES])
    y_holdout = demo_holdout["fault_label"].astype(int).values
    X_holdout_t = torch.tensor(X_holdout, dtype=torch.float32, device=device).unsqueeze(1)

    with torch.no_grad():
        recon, holdout_logits = final_model(X_holdout_t)
        y_pred = torch.argmax(F.softmax(holdout_logits, dim=-1), dim=-1).cpu().numpy()
        test_recon_mse = float(torch.mean((recon - X_holdout_t) ** 2).item())
    test_metrics = _final_report(y_holdout, y_pred, "LSTM-AE+CLS (demo holdout)")

    metadata = {
        "model_name": "best_lstmae.pth",
        "model_family": "lstm_autoencoder_pytorch",
        "trained_on_dataset": "dtx_ai_master_dataset.csv",
        "feature_count": len(FEATURES),
        "num_classes": num_classes,
        "feature_order_ref": "services/ai/models/shared/feature_order.json",
        "scaler_required": True,
        "input_shape": {"batch": "N", "sequence_length": 1, "feature_dim": len(FEATURES)},
        "class_mapping": {str(i): n for i, n in enumerate(CLASS_NAMES)},
        "training_split": best["split"],
        "best_params": {
            **best["param_dict"],
            "dropout": LSTM_DROPOUT,
            "weight_decay": LSTM_WEIGHT_DECAY,
        },
        "metrics": {
            "val_accuracy": round(best["accuracy"], 6),
            "val_f1": round(best["f1"], 6),
            "val_precision": round(best["precision"], 6),
            **{k: round(v, 6) for k, v in test_metrics.items()},
            "test_reconstruction_mse": round(test_recon_mse, 6),
        },
        "decision_type": "multiclass_classifier_with_reconstruction",
        "default_threshold": 0.5,
        "notes": (
            "Trained via scripts/train_models.py with stratified group-aware "
            "splits when episode/run groups are available. Architecture is "
            "ai.lstm_classifier.LSTMAutoencoderClassifier."
        ),
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"[save] {pth_path}  +  metadata.json")


def save_tabnet_artifact(best: dict, demo_holdout: pd.DataFrame):
    if best.get("skipped"):
        print(f"[save] TabNet skipped; no artifact written ({best.get('skip_reason', 'unknown reason')})")
        return
    out_dir = MODELS_ROOT / "tabnet"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    X_holdout = demo_holdout[FEATURES].copy()
    if best["scaler"] is not None:
        X_holdout = pd.DataFrame(best["scaler"].transform(X_holdout), columns=FEATURES)
    y_holdout = demo_holdout["fault_label"].astype(int).values
    
    try:
        y_pred = best["model_obj"].predict(X_holdout)
        test_metrics = _final_report(y_holdout, y_pred, "TabNet (demo holdout)")
    except Exception as exc:
        print(f"[save] TabNet demo holdout evaluation skipped due to exception: {exc}")
        test_metrics = {
            "test_accuracy": None,
            "test_f1": None,
            "test_precision": None,
        }
    
    best["model_obj"].save_model(str(out_dir / "best_tabnet"))
    artifact_name = "best_tabnet.zip"
    
    metadata = {
        "model_name": artifact_name,
        "model_family": "tabnet_pytorch",
        "trained_on_dataset": "dtx_ai_master_dataset.csv",
        "feature_count": len(FEATURES),
        "num_classes": len(CLASS_NAMES),
        "feature_order_ref": "services/ai/models/shared/feature_order.json",
        "scaler_required": True,
        "class_mapping": {str(i): n for i, n in enumerate(CLASS_NAMES)},
        "training_split": best["split"],
        "best_params": best["param_dict"],
        "metrics": {
            "val_accuracy": round(best["accuracy"], 6),
            "val_f1": round(best["f1"], 6),
            "val_precision": round(best["precision"], 6),
            **{k: (None if v is None else round(v, 6)) for k, v in test_metrics.items()},
        },
        "decision_type": "multiclass_classifier",
        "default_threshold": 0.5,
        "supports_tree_xai": False,
        "notes": "Trained via scripts/train_models.py (PyTorch TabNet).",
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"[save] {out_dir}/{artifact_name}  +  metadata.json")

def save_cnn_artifact(best: dict, device: torch.device, num_classes: int,
                      demo_holdout: pd.DataFrame):
    out_dir = MODELS_ROOT / "cnn"
    out_dir.mkdir(parents=True, exist_ok=True)
    p = best["param_dict"]

    final_model = CNNClassifier(
        input_dim=len(FEATURES),
        num_classes=num_classes,
        window_size=p.get("window", 1),
        conv_channels=p["conv_channels"],
        kernel_size=p["kernel_size"],
        hidden_dim=p["hidden_dim"],
        dropout=p["dropout"],
    ).to(device)
    final_model.load_state_dict(best["state_dict"])
    final_model.eval()

    X_holdout = pd.DataFrame(best["scaler"].transform(demo_holdout[FEATURES]), columns=FEATURES)
    df_holdout = X_holdout.copy()
    df_holdout["fault_label"] = demo_holdout["fault_label"].astype(int).values
    X_holdout_w, y_holdout = engineer_features(
        df_holdout, window=p["window"], step=5,
    )
    X_holdout_t = torch.tensor(X_holdout_w, dtype=torch.float32, device=device)

    with torch.no_grad():
        holdout_logits = final_model(X_holdout_t)
        y_pred = torch.argmax(F.softmax(holdout_logits, dim=-1), dim=-1).cpu().numpy()

    test_metrics = _final_report(y_holdout, y_pred, "CNN (demo holdout)")

    pth_path = out_dir / "best_cnn.pth"
    torch.save(best["state_dict"], pth_path)

    metadata = {
        "model_name": "best_cnn.pth",
        "model_family": "cnn_pytorch",
        "trained_on_dataset": "dtx_ai_master_dataset.csv",
        "feature_count": len(FEATURES),
        "num_classes": len(CLASS_NAMES),
        "feature_order_ref": "services/ai/models/shared/feature_order.json",
        "scaler_required": True,
        "class_mapping": {str(i): n for i, n in enumerate(CLASS_NAMES)},
        "training_split": best["split"],
        "best_params": best["param_dict"],
        "metrics": {
            "val_accuracy": round(best["accuracy"], 6),
            "val_f1": round(best["f1"], 6),
            "val_precision": round(best["precision"], 6),
            **{k: round(v, 6) for k, v in test_metrics.items()},
        },
        "decision_type": "multiclass_classifier",
        "default_threshold": 0.5,
        "supports_tree_xai": False,
        "notes": "Trained via scripts/train_models.py — CNN classifier saved as ai.cnn_classifier.CNNClassifier.",
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"[save] {pth_path}  +  metadata.json")
    
def save_bilstm_artifact(best: dict, device: torch.device, num_classes: int, demo_holdout: pd.DataFrame):
    out_dir = MODELS_ROOT / "bilstm"
    out_dir.mkdir(parents=True, exist_ok=True)
    p = best["param_dict"]

    final_model = BiLSTMClassifier(
        input_dim=len(FEATURES), num_classes=num_classes, window_size=p["window"],
        hidden_dim=p["hidden_dim"], num_layers=p["num_layers"], dropout=p["dropout"],
    ).to(device)
    final_model.load_state_dict(best["state_dict"])
    final_model.eval()

    X_holdout = pd.DataFrame(best["scaler"].transform(demo_holdout[FEATURES]), columns=FEATURES)
    df_holdout = X_holdout.copy()
    df_holdout["fault_label"] = demo_holdout["fault_label"].astype(int).values
    X_holdout_w, y_holdout = engineer_features(df_holdout, window=p["window"], step=5)
    X_holdout_t = torch.tensor(X_holdout_w, dtype=torch.float32, device=device)

    with torch.no_grad():
        y_pred = torch.argmax(F.softmax(final_model(X_holdout_t), dim=-1), dim=-1).cpu().numpy()

    test_metrics = _final_report(y_holdout, y_pred, "Bi-LSTM (demo holdout)")

    pth_path = out_dir / "best_bilstm.pth"
    torch.save(best["state_dict"], pth_path)

    metadata = {
        "model_name": "best_bilstm.pth",
        "model_family": "bilstm_pytorch",
        "feature_count": len(FEATURES),
        "num_classes": num_classes,
        "scaler_required": True,
        "training_split": best["split"],
        "best_params": p,
        "metrics": {"val_f1": round(best["f1"], 6), **{k: round(v, 6) for k, v in test_metrics.items()}},
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"[save] {pth_path}  +  metadata.json")


# ── Notebook cell 11: Global Leaderboard & Retrain ─────────────────────────
def save_overall_best(
    best_rf,
    best_lgbm,
    best_xgb,
    best_tabnet,
    best_cnn,
    best_bilstm,
    best_lstm,
    X,
    y,
    groups: pd.Series | None,
    demo_holdout: pd.DataFrame,
    device: torch.device,
):
    # 1. Gather all candidates
    candidates = {
        "RandomForest": best_rf,
        "LightGBM": best_lgbm,
        "XGBoost": best_xgb,
        "TabNet": best_tabnet,
        "CNN": best_cnn,
        "Bi-LSTM": best_bilstm,
        "LSTM-AE": best_lstm,
    }
    
    # 2. Build and print the leaderboard
    records = []
    for name, b in candidates.items():
        if b and "f1" in b:
            records.append({
                "model": name,
                "split": b.get("split", "N/A"),
                "accuracy": b.get("accuracy", 0.0),
                "f1": b.get("f1", 0.0),
                "precision": b.get("precision", 0.0)
            })
    
    results_df = pd.DataFrame(records).sort_values(by="f1", ascending=False).reset_index(drop=True)
    print("\n" + "="*70)
    print("FULL RESULTS TABLE (LEADERBOARD)")
    print("="*70)
    print(results_df.to_string(index=False))

    # 3. Pick Global Winner
    overall_name = results_df.iloc[0]["model"]
    overall = candidates[overall_name]
    print(f"\n=== Global Winner: {overall_name} (F1: {overall['f1']:.4f}) ===")
    
    if overall_name in ["TabNet", "LSTM-AE"]:
        # No train+val retraining for these two; the per-family save_*_artifact step
        # already wrote the best model. Still mirror the winner's scaler and
        # feature_order into shared/ (the runtime loader reads from there), plus
        # a convenience copy of the model artifact under shared/model_best.*.
        SHARED_DIR.mkdir(parents=True, exist_ok=True)
        winner_scaler = overall.get("scaler")
        if winner_scaler is not None:
            joblib.dump(winner_scaler, SHARED_DIR / "scaler.pkl")
        (SHARED_DIR / "feature_order.json").write_text(json.dumps(FEATURES, indent=2) + "\n")

        if overall_name == "TabNet":
            import shutil
            src = MODELS_ROOT / "tabnet" / "best_tabnet.zip"
            if src.exists():
                shutil.copyfile(src, SHARED_DIR / "model_best.zip")
            print(f"[save] {SHARED_DIR}/model_best.zip  +  scaler.pkl  +  feature_order.json")
        else:  # LSTM-AE
            torch.save(overall["state_dict"], SHARED_DIR / "model_best.pth")
            print(f"[save] {SHARED_DIR}/model_best.pth  +  scaler.pkl  +  feature_order.json")

        print(f"[{overall_name}] No train+val retrain — sweep artifact reused for shared/.")
        return overall_name

    tr, vr, te = overall["split_tuple"]
    p = overall["param_dict"]
    
    needs_windows = overall_name in ["CNN", "Bi-LSTM"]
    needs_scaler = overall_name in ["RandomForest", "CNN", "Bi-LSTM"]

    window_size = p.get("window", 30) if needs_windows else 0
    X_train, X_val, X_test, y_train, y_val, y_test, scaler = prepare_splits(
        X, y, tr, vr, te, scale_and_impute=needs_scaler, window=window_size, groups=groups,
    )

    # 4. Retrain Global Winner on Train+Val
    if not needs_windows:
        X_final = pd.concat([X_train, X_val])
        y_final = pd.concat([y_train, y_val])
        
        if overall_name == "RandomForest":
            final_model = RandomForestClassifier(
                n_estimators=p["n_estimators"], max_depth=p["max_depth"],
                random_state=RANDOM_STATE, class_weight="balanced",
            )
        elif overall_name == "LightGBM":
            final_model = lgb.LGBMClassifier(
                n_estimators=p["n_estimators"], max_depth=p["max_depth"],
                learning_rate=p["learning_rate"],
                random_state=RANDOM_STATE, class_weight="balanced", verbose=-1,
            )
        else: # XGBoost
            final_model = xgb.XGBClassifier(
                n_estimators=p["n_estimators"], max_depth=p["max_depth"],
                learning_rate=p["learning_rate"],
                random_state=RANDOM_STATE, eval_metric="mlogloss", verbosity=0,
            )
            
        print(f"Re-training {overall_name} on Train+Val data...")
        final_model.fit(X_final, y_final)
        
        SHARED_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(final_model, SHARED_DIR / "model_best.pkl")
        if scaler is not None:
            joblib.dump(scaler, SHARED_DIR / "scaler.pkl")
        (SHARED_DIR / "feature_order.json").write_text(json.dumps(FEATURES, indent=2) + "\n")
        print(f"[save] {SHARED_DIR}/model_best.pkl  +  (scaler if required)  +  feature_order.json")
        
        # Final eval against the canonical demo holdout
        if scaler is not None:
            X_holdout_scaled = pd.DataFrame(scaler.transform(demo_holdout[FEATURES]), columns=FEATURES)
        else:
            X_holdout_scaled = demo_holdout[FEATURES].copy()
            
        y_holdout = demo_holdout["fault_label"].astype(int)
        y_holdout_pred = final_model.predict(X_holdout_scaled)
        _final_report(
            y_holdout.values, y_holdout_pred,
            f"model_best.pkl ({overall_name}, retrained on train+val, scored on demo holdout)",
        )

    else:
        # Re-train CNN or Bi-LSTM
        X_final_w = np.concatenate([X_train, X_val], axis=0)
        y_final_w = np.concatenate([y_train, y_val], axis=0)
        num_classes = len(np.unique(y_final_w))

        if overall_name == "CNN":
            final_model = CNNClassifier(
                input_dim=len(FEATURES), num_classes=num_classes, window_size=window_size,
                conv_channels=p["conv_channels"], kernel_size=p["kernel_size"],
                hidden_dim=p["hidden_dim"], dropout=p["dropout"],
            ).to(device)
            epochs = p.get("epochs", 100)
            lr = p.get("lr", 0.005)
            batch_size = p.get("batch_size", 64)
        else:
            final_model = BiLSTMClassifier(
                input_dim=len(FEATURES), num_classes=num_classes, window_size=window_size,
                hidden_dim=p["hidden_dim"], num_layers=p["num_layers"], dropout=p["dropout"],
            ).to(device)
            epochs = int(p.get("epochs", 100))
            lr = p.get("lr", 0.005)
            batch_size = 64

        final_classes = np.unique(y_final_w)
        final_weights = compute_class_weight("balanced", classes=final_classes, y=y_final_w)
        final_weights_t = torch.tensor(final_weights, dtype=torch.float32, device=device)

        optimizer = torch.optim.Adam(final_model.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss(weight=final_weights_t)

        X_final_t = torch.tensor(X_final_w, dtype=torch.float32, device=device)
        y_final_t = torch.tensor(y_final_w, dtype=torch.long, device=device)

        final_ds = TensorDataset(X_final_t, y_final_t)
        final_loader = DataLoader(final_ds, batch_size=batch_size, shuffle=True)

        print(f"Re-training {overall_name} on Train+Val data ({epochs} epochs)...")
        final_model.train()
        for _ in range(epochs):
            for xb, yb in final_loader:
                optimizer.zero_grad()
                loss = criterion(final_model(xb), yb)
                loss.backward()
                optimizer.step()

        SHARED_DIR.mkdir(parents=True, exist_ok=True)
        torch.save(final_model.state_dict(), SHARED_DIR / "model_best.pth")
        if scaler is not None:
            joblib.dump(scaler, SHARED_DIR / "scaler.pkl")
        (SHARED_DIR / "feature_order.json").write_text(json.dumps(FEATURES, indent=2) + "\n")
        print(f"[save] {SHARED_DIR}/model_best.pth  +  (scaler if required)  +  feature_order.json")
        
        final_model.eval()
        X_holdout = pd.DataFrame(scaler.transform(demo_holdout[FEATURES]), columns=FEATURES)
        df_holdout = X_holdout.copy()
        df_holdout["fault_label"] = demo_holdout["fault_label"].astype(int).values
        X_holdout_w, y_holdout = engineer_features(df_holdout, window=window_size, step=5)
        X_holdout_t = torch.tensor(X_holdout_w, dtype=torch.float32, device=device)
        with torch.no_grad():
            y_pred = torch.argmax(F.softmax(final_model(X_holdout_t), dim=-1), dim=-1).cpu().numpy()
        _final_report(
            y_holdout, y_pred,
            f"model_best.pth ({overall_name}, retrained on train+val, scored on demo holdout)",
        )

    return overall_name


# ── orchestration ──────────────────────────────────────────────────────────
def main():
    print(f"[env] python={sys.version.split()[0]} torch={torch.__version__} cuda={torch.cuda.is_available()}")
    print(f"[data] loading {AI_ROOT}/dtx_ai_master_dataset.csv")
    df = load_data(str(AI_ROOT / "dtx_ai_master_dataset.csv"))
    df = engineer_features(df)

    # Carve out the canonical 20% holdout. When the fixed dataset provides an
    # episode/run identifier, hold out complete episodes; otherwise preserve the
    # legacy stratified row-level demo holdout for the current CSV.
    source_episode_column = find_episode_column(df)
    if source_episode_column is not None:
        training_pool, demo_holdout = split_episode_pool_and_holdout(df)
        holdout_mode = f"episode ({source_episode_column})"
    else:
        training_pool, demo_holdout = split_training_pool_and_holdout(df)
        holdout_mode = "row-stratified"
    print(
        f"[data] training_pool={training_pool.shape}  demo_holdout={demo_holdout.shape}  "
        f"holdout_mode={holdout_mode}  "
        f"(holdout distribution: {demo_holdout['fault_label'].value_counts().sort_index().to_dict()})"
    )

    X = training_pool[FEATURES]
    y = training_pool["fault_label"].astype(int)
    num_classes = int(y.nunique())
    print(f"[data] using training pool {training_pool.shape}, {num_classes} classes, "
          f"distribution: {y.value_counts().sort_index().to_dict()}")
    groups = episode_groups(training_pool)
    episode_column = find_episode_column(training_pool)
    group_source = episode_column or "derived contiguous fault-label runs"
    print(
        f"[data] split groups={groups.nunique()} source={group_source}; "
        "sweeps are stratified by group labels when possible"
    )

    run_sanity_baselines(training_pool, demo_holdout)

    # Cells 5/6/7 — independent per-model sweeps.
    best_rf = sweep_random_forest(X, y, groups)
    best_lgbm = sweep_lightgbm(X, y, groups)
    best_xgb = sweep_xgboost(X, y, groups)

    save_tree_artifact(best_rf, demo_holdout, MODELS_ROOT / "random_forest", "best_rf.pkl",
                       "random_forest", supports_tree_xai=True)
    save_tree_artifact(best_lgbm, demo_holdout, MODELS_ROOT / "lightgbm", "best_lgbm.pkl",
                       "lightgbm", supports_tree_xai=True)
    save_tree_artifact(best_xgb, demo_holdout, MODELS_ROOT / "xgboost", "best_xgb.pkl",
                       "xgboost", supports_tree_xai=True)

    # TabNet sweep.
    best_tabnet = sweep_tabnet(X, y, groups)
    save_tabnet_artifact(best_tabnet, demo_holdout)

    # CNN sweep.
    best_cnn, device = sweep_cnn(X, y, num_classes, groups)
    save_cnn_artifact(best_cnn, device, num_classes, demo_holdout)

    # Bi-LSTM sweep.
    best_bilstm, device = sweep_bilstm(X, y, num_classes, groups)
    save_bilstm_artifact(best_bilstm, device, num_classes, demo_holdout)

    # Cell 7 — LSTM-AE+CLS sweep.
    best_lstm, device = sweep_lstm_ae(X, y, num_classes, groups)
    save_lstm_artifact(best_lstm, device, num_classes, demo_holdout)

    # Cell 11 — Global Leaderboard & Retrain.
    save_overall_best(
        best_rf, best_lgbm, best_xgb, best_tabnet, best_cnn, best_bilstm, best_lstm,
        X, y, groups, demo_holdout, device
    )

    print("\n[done] all artifacts retrained against current sklearn/lightgbm/xgboost/torch versions.")


if __name__ == "__main__":
    main()
