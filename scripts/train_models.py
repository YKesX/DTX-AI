#!/usr/bin/env python3
"""Retrain every model in services/ai/ai/models/ from scratch.

Methodology (mirrored cell-for-cell by services/ai/dtxai_model_training.ipynb):

    1. Canonical leakage-safe split — the dataset is ~60 Hz telemetry in 13
       contiguous fault runs, so row-level random splits leak near-duplicate
       neighbouring frames. Instead:
           demo holdout = last 20% of every run  (purge gap 60 rows)
           train / val  = first 75% / last 25% of the remaining pool
                          (again per-run temporal, again purge-gapped)
       Validation F1 is comparable across hyperparameter configs because the
       split is FIXED; the demo holdout is touched exactly once per family,
       for the final test report.
    2. Class imbalance — every model trains class-weighted (the new dataset
       is unbalanced: 3 000–4 200 rows per class).
    3. Early stopping — boosted trees stop on validation loss; torch models
       keep the best-validation-F1 epoch (LSTM-AE stays capped at 20 epochs).
    4. NaN robustness — the dataset has real sensor dropouts. Scaled models
       impute medians inside their pipeline; LightGBM/XGBoost consume NaN
       natively and stay unscaled.
    5. Per-family scalers — each family dir gets its own scaler.pkl so the
       runtime never applies another model's scaler.

This is the file the runtime registry actually reads.
"""

from __future__ import annotations

import copy
import json
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import f_classif
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight, compute_sample_weight
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
    PURGE_GAP_ROWS,
    engineer_features,
    episode_groups,
    load_data,
    split_demo_pool_and_holdout,
    split_pool_train_val,
)
from ai.lstm_classifier import LSTMAutoencoderClassifier  # noqa: E402
from ai.cnn_classifier import CNNClassifier  # noqa: E402
from ai.bilstm_classifier import BiLSTMClassifier  # noqa: E402

# ── Notebook CELL 2: CONFIGURATION ─────────────────────────────────────────
RANDOM_STATE = 42
SPLIT_DESCRIPTION = (
    f"episode-temporal 60/20/20 (train/val/demo-holdout), purge gap {PURGE_GAP_ROWS} rows"
)

RF_N_ESTIMATORS = [200, 400]
RF_MAX_DEPTH = [8, 16, None]

GBM_MAX_ROUNDS = 1000           # early stopping decides the real count
GBM_EARLY_STOPPING = 50
LGBM_LEARNING_RATE = [0.03, 0.1]
LGBM_MAX_DEPTH = [-1, 6]
LGBM_NUM_LEAVES = [31, 63]
XGB_LEARNING_RATE = [0.03, 0.1]
XGB_MAX_DEPTH = [4, 6]

# LSTM-AE stays capped at 20 epochs (anti-memorisation cap).
LSTM_MAX_EPOCHS = 20
LSTM_PATIENCE = 4
LSTM_HIDDEN_DIMS = [32, 64]
LSTM_LATENT_DIMS = [8, 16]
LSTM_LR_LIST = [0.001, 0.003]
LSTM_BATCH_SIZE = 64
LSTM_DROPOUT = 0.2
LSTM_WEIGHT_DECAY = 1e-4
LAMBDA_RECON = 1.0
LAMBDA_CLS = 1.0

TABNET_N_D_LIST = [8, 16]
TABNET_N_STEPS_LIST = [2, 3]

CNN_MAX_EPOCHS = 40
CNN_PATIENCE = 6
CNN_CONV_CHANNELS_LIST = [16, 32]
CNN_HIDDEN_DIMS = [32, 64]
CNN_KERNEL_SIZES = [3, 5]
CNN_LR = 0.001
CNN_BATCH_SIZE = 64
CNN_DROPOUT = 0.2
CNN_WINDOW_SIZE = 30

BILSTM_MAX_EPOCHS = 40
BILSTM_PATIENCE = 6
BILSTM_HIDDEN_DIMS = [64, 128]
BILSTM_LAYERS = [1, 2]
BILSTM_LR_LIST = [0.001, 0.003]
BILSTM_BATCH_SIZE = 64
BILSTM_DROPOUT = 0.3
BILSTM_WINDOW_SIZE = 30
WINDOW_STEP = 5


def build_scaling_pipeline() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])


# ── Notebook CELL 3: canonical splits ──────────────────────────────────────
def prepare_canonical_splits(df: pd.DataFrame) -> dict:
    """One fixed leakage-safe split shared by every sweep.

    Returns raw (unscaled, un-imputed) partitions plus per-row episode groups
    so windowed models never build a window across a split or run boundary.
    """
    pool, demo_holdout = split_demo_pool_and_holdout(df)
    train_df, val_df = split_pool_train_val(pool)
    return {
        "pool": pool,
        "demo_holdout": demo_holdout,
        "train": train_df,
        "val": val_df,
        "train_groups": episode_groups(train_df),
        "val_groups": episode_groups(val_df),
        "pool_groups": episode_groups(pool),
        "holdout_groups": episode_groups(demo_holdout),
    }


def scaled_partitions(splits: dict) -> tuple[pd.DataFrame, pd.DataFrame, Pipeline]:
    """Median-impute + standardise; the pipeline is fit on train only."""
    scaler = build_scaling_pipeline()
    X_train = pd.DataFrame(
        scaler.fit_transform(splits["train"][FEATURES]), columns=FEATURES,
    )
    X_val = pd.DataFrame(scaler.transform(splits["val"][FEATURES]), columns=FEATURES)
    return X_train, X_val, scaler


def windowed_partitions(
    splits: dict, scaler: Pipeline, window: int, step: int = WINDOW_STEP,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Per-episode sliding windows for CNN/Bi-LSTM, after scaling."""
    out = []
    for part, group_key in (("train", "train_groups"), ("val", "val_groups")):
        part_df = splits[part]
        scaled = pd.DataFrame(scaler.transform(part_df[FEATURES]), columns=FEATURES)
        scaled["fault_label"] = part_df["fault_label"].astype(int).values
        scaled["_g"] = splits[group_key].astype(str).values
        xs, ys = [], []
        for _, seg in scaled.groupby("_g", sort=False):
            seg = seg.drop(columns=["_g"])
            if len(seg) < window:
                continue
            X_w, y_w = engineer_features(seg, window=window, step=step)
            if len(X_w):
                xs.append(X_w)
                ys.append(y_w)
        if not xs:
            raise ValueError(f"No {window}-row windows could be built for split '{part}'.")
        out.append((np.concatenate(xs, axis=0), np.concatenate(ys, axis=0)))
    (X_train_w, y_train_w), (X_val_w, y_val_w) = out
    return X_train_w, y_train_w, X_val_w, y_val_w


# ── Notebook CELL 4: evaluation helpers ────────────────────────────────────
def evaluate(model, X_val, y_val, model_name: str, param: dict):
    y_pred = model.predict(X_val)
    y_prob = model.predict_proba(X_val) if hasattr(model, "predict_proba") else None
    acc = accuracy_score(y_val, y_pred)
    f1 = f1_score(y_val, y_pred, average="macro")
    precision = precision_score(y_val, y_pred, average="macro", zero_division=0)
    auroc = float("nan")
    if y_prob is not None:
        try:
            auroc = roc_auc_score(y_val, y_prob, multi_class="ovr", average="macro")
        except ValueError:
            pass
    param_str = ", ".join(f"{k}={v}" for k, v in param.items())
    print(
        f"[{model_name:>13}] {param_str:<58}  "
        f"acc={acc:.4f}  f1={f1:.4f}  auroc={auroc:.4f}"
    )
    return {
        "model": model_name,
        "split": SPLIT_DESCRIPTION,
        "param": param_str,
        "param_dict": dict(param),
        "accuracy": float(acc),
        "f1": float(f1),
        "precision": float(precision),
        "auroc": (None if np.isnan(auroc) else float(auroc)),
    }


def torch_val_scores(model, X_val_t, y_val_np) -> tuple[float, float, float, np.ndarray]:
    model.eval()
    with torch.no_grad():
        out = model(X_val_t)
        logits = out[1] if isinstance(out, tuple) else out
        y_pred = torch.argmax(F.softmax(logits, dim=-1), dim=-1).cpu().numpy()
    return (
        float(accuracy_score(y_val_np, y_pred)),
        float(f1_score(y_val_np, y_pred, average="macro")),
        float(precision_score(y_val_np, y_pred, average="macro", zero_division=0)),
        y_pred,
    )


def fit_torch_with_early_stopping(
    model: nn.Module,
    loader: DataLoader,
    X_val_t: torch.Tensor,
    y_val_np: np.ndarray,
    *,
    lr: float,
    weight_decay: float,
    class_weights: torch.Tensor,
    max_epochs: int,
    patience: int,
    autoencoder: bool = False,
) -> tuple[dict, int, float]:
    """Train with per-epoch val-F1 early stopping; return the best epoch's state."""
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    cls_loss_fn = nn.CrossEntropyLoss(weight=class_weights)
    recon_loss_fn = nn.MSELoss()

    best_f1, best_state, best_epoch, bad_epochs = -1.0, None, 0, 0
    for epoch in range(1, max_epochs + 1):
        model.train()
        for X_batch, y_batch in loader:
            optimizer.zero_grad()
            if autoencoder:
                X_recon, logits = model(X_batch)
                loss = (
                    LAMBDA_RECON * recon_loss_fn(X_recon, X_batch)
                    + LAMBDA_CLS * cls_loss_fn(logits, y_batch)
                )
            else:
                loss = cls_loss_fn(model(X_batch), y_batch)
            loss.backward()
            optimizer.step()

        _, val_f1, _, _ = torch_val_scores(model, X_val_t, y_val_np)
        if val_f1 > best_f1:
            best_f1, best_epoch, bad_epochs = val_f1, epoch, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            bad_epochs += 1
            if bad_epochs >= patience:
                break
    model.load_state_dict(best_state)
    return best_state, best_epoch, best_f1


def class_weight_tensor(y: np.ndarray, device: torch.device) -> torch.Tensor:
    classes = np.unique(y)
    weights = compute_class_weight(class_weight="balanced", classes=classes, y=y)
    full = np.ones(len(CLASS_NAMES), dtype=np.float32)
    for cls, w in zip(classes, weights):
        full[int(cls)] = w
    return torch.tensor(full, dtype=torch.float32, device=device)


# ── Notebook CELL 5: shortcut/sanity baselines ─────────────────────────────
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
        "temperature_only": ["temperature_c"],
        "no_temperature": [c for c in FEATURES if c != "temperature_c"],
        "top3_anova": top3,
        "full": FEATURES,
    }
    results = []
    for name, columns in feature_sets.items():
        model = lgb.LGBMClassifier(
            n_estimators=100, max_depth=3, learning_rate=0.1,
            random_state=RANDOM_STATE, class_weight="balanced", verbose=-1,
        )
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="X does not have valid feature names")
            model.fit(X_train[columns], y_train)
            pred = model.predict(X_holdout[columns])
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
        "split": SPLIT_DESCRIPTION,
        "top_anova_features": ranking.head(10).to_dict(orient="records"),
        "baselines": results,
        "notes": (
            "If temperature_only is close to full, the dataset is shortcut-dominated. "
            "If no_temperature collapses, non-temperature channels are not carrying the labels."
        ),
    }
    (SHARED_DIR / "sanity_baselines.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"[save] {SHARED_DIR}/sanity_baselines.json")


# ── Notebook CELL 6: RandomForest sweep ────────────────────────────────────
def sweep_random_forest(splits: dict):
    total = len(RF_N_ESTIMATORS) * len(RF_MAX_DEPTH)
    print(f"\n=== RandomForest sweep ({total} configs, fixed canonical split) ===")
    X_train, X_val, scaler = scaled_partitions(splits)
    y_train = splits["train"]["fault_label"].astype(int)
    y_val = splits["val"]["fault_label"].astype(int)

    best = {"f1": -1.0}
    for n in RF_N_ESTIMATORS:
        for d in RF_MAX_DEPTH:
            model = RandomForestClassifier(
                n_estimators=n, max_depth=d, random_state=RANDOM_STATE,
                class_weight="balanced", n_jobs=-1,
            )
            model.fit(X_train, y_train)
            result = evaluate(model, X_val, y_val, "RandomForest",
                              {"n_estimators": n, "max_depth": d})
            if result["f1"] > best["f1"]:
                best = {**result, "model_obj": model, "scaler": scaler}
    print(f"--- best RF: {best['param']}  f1={best['f1']:.4f}")
    return best


# ── Notebook CELL 7: LightGBM sweep (early stopping) ───────────────────────
def sweep_lightgbm(splits: dict):
    total = len(LGBM_LEARNING_RATE) * len(LGBM_MAX_DEPTH) * len(LGBM_NUM_LEAVES)
    print(f"\n=== LightGBM sweep ({total} configs, early stopping {GBM_EARLY_STOPPING}) ===")
    X_train = splits["train"][FEATURES]
    X_val = splits["val"][FEATURES]
    y_train = splits["train"]["fault_label"].astype(int)
    y_val = splits["val"]["fault_label"].astype(int)

    best = {"f1": -1.0}
    for lr in LGBM_LEARNING_RATE:
        for d in LGBM_MAX_DEPTH:
            for leaves in LGBM_NUM_LEAVES:
                model = lgb.LGBMClassifier(
                    n_estimators=GBM_MAX_ROUNDS, max_depth=d, num_leaves=leaves,
                    learning_rate=lr, random_state=RANDOM_STATE,
                    class_weight="balanced", verbose=-1,
                )
                model.fit(
                    X_train, y_train,
                    eval_set=[(X_val, y_val)],
                    callbacks=[lgb.early_stopping(GBM_EARLY_STOPPING, verbose=False)],
                )
                rounds = int(model.best_iteration_ or GBM_MAX_ROUNDS)
                result = evaluate(model, X_val, y_val, "LightGBM",
                                  {"learning_rate": lr, "max_depth": d,
                                   "num_leaves": leaves, "best_rounds": rounds})
                if result["f1"] > best["f1"]:
                    best = {**result, "model_obj": model, "scaler": None}
    print(f"--- best LightGBM: {best['param']}  f1={best['f1']:.4f}")
    return best


# ── Notebook CELL 8: XGBoost sweep (early stopping + sample weights) ───────
def sweep_xgboost(splits: dict):
    total = len(XGB_LEARNING_RATE) * len(XGB_MAX_DEPTH)
    print(f"\n=== XGBoost sweep ({total} configs, early stopping {GBM_EARLY_STOPPING}) ===")
    X_train = splits["train"][FEATURES]
    X_val = splits["val"][FEATURES]
    y_train = splits["train"]["fault_label"].astype(int)
    y_val = splits["val"]["fault_label"].astype(int)
    sample_weight = compute_sample_weight("balanced", y_train)

    best = {"f1": -1.0}
    for lr in XGB_LEARNING_RATE:
        for d in XGB_MAX_DEPTH:
            model = xgb.XGBClassifier(
                n_estimators=GBM_MAX_ROUNDS, max_depth=d, learning_rate=lr,
                random_state=RANDOM_STATE, eval_metric="mlogloss",
                early_stopping_rounds=GBM_EARLY_STOPPING, verbosity=0,
            )
            model.fit(
                X_train, y_train,
                sample_weight=sample_weight,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )
            rounds = int(getattr(model, "best_iteration", GBM_MAX_ROUNDS) or GBM_MAX_ROUNDS)
            result = evaluate(model, X_val, y_val, "XGBoost",
                              {"learning_rate": lr, "max_depth": d, "best_rounds": rounds})
            if result["f1"] > best["f1"]:
                best = {**result, "model_obj": model, "scaler": None}
    print(f"--- best XGBoost: {best['param']}  f1={best['f1']:.4f}")
    return best


# ── Notebook CELL 9: LSTM-AE+CLS sweep (epoch cap 20, early stopping) ──────
def sweep_lstm_ae(splits: dict, num_classes: int):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    total = len(LSTM_HIDDEN_DIMS) * len(LSTM_LATENT_DIMS) * len(LSTM_LR_LIST)
    print(f"\n=== LSTM-AE+CLS sweep ({total} configs, max {LSTM_MAX_EPOCHS} epochs, "
          f"patience {LSTM_PATIENCE}) on {device} ===")
    if device.type == "cuda":
        print(f"[env] {torch.cuda.get_device_name(0)}")

    X_train, X_val, scaler = scaled_partitions(splits)
    y_train = splits["train"]["fault_label"].astype(int).values
    y_val = splits["val"]["fault_label"].astype(int).values

    X_train_t = torch.tensor(X_train.values, dtype=torch.float32, device=device).unsqueeze(1)
    X_val_t = torch.tensor(X_val.values, dtype=torch.float32, device=device).unsqueeze(1)
    y_train_t = torch.tensor(y_train, dtype=torch.long, device=device)
    loader = DataLoader(TensorDataset(X_train_t, y_train_t),
                        batch_size=LSTM_BATCH_SIZE, shuffle=True)
    weights = class_weight_tensor(y_train, device)

    best = {"f1": -1.0}
    config_idx = 0
    for hidden_dim in LSTM_HIDDEN_DIMS:
        for latent_dim in LSTM_LATENT_DIMS:
            for lr in LSTM_LR_LIST:
                config_idx += 1
                t0 = time.time()
                model = LSTMAutoencoderClassifier(
                    input_dim=len(FEATURES), hidden_dim=hidden_dim,
                    latent_dim=latent_dim, num_classes=num_classes,
                    dropout=LSTM_DROPOUT,
                ).to(device)
                state, best_epoch, _ = fit_torch_with_early_stopping(
                    model, loader, X_val_t, y_val,
                    lr=lr, weight_decay=LSTM_WEIGHT_DECAY, class_weights=weights,
                    max_epochs=LSTM_MAX_EPOCHS, patience=LSTM_PATIENCE,
                    autoencoder=True,
                )
                acc, f1, precision, _ = torch_val_scores(model, X_val_t, y_val)
                flag = ""
                if f1 > best["f1"]:
                    flag = "  *** new best"
                    best = {
                        "model": "LSTM-AE", "split": SPLIT_DESCRIPTION,
                        "param": f"hidden={hidden_dim}, latent={latent_dim}, "
                                 f"lr={lr}, best_epoch={best_epoch}",
                        "param_dict": {
                            "hidden": hidden_dim, "latent": latent_dim, "lr": lr,
                            "epochs": best_epoch, "max_epochs": LSTM_MAX_EPOCHS,
                            "batch": LSTM_BATCH_SIZE,
                            "lambda_recon": LAMBDA_RECON, "lambda_cls": LAMBDA_CLS,
                        },
                        "accuracy": acc, "f1": f1, "precision": precision,
                        "auroc": None,
                        "state_dict": copy.deepcopy(state),
                        "scaler": scaler,
                    }
                print(
                    f"[{config_idx:>2}/{total}] h={hidden_dim:<3} l={latent_dim:<3} "
                    f"lr={lr:<6} best_epoch={best_epoch:<3} acc={acc:.4f} f1={f1:.4f} "
                    f"({time.time()-t0:.1f}s){flag}"
                )
    print(f"--- best LSTM-AE: {best['param']}  f1={best['f1']:.4f}")
    return best, device


# ── Notebook CELL 10: TabNet sweep ─────────────────────────────────────────
def sweep_tabnet(splits: dict):
    total = len(TABNET_N_D_LIST) * len(TABNET_N_STEPS_LIST)
    print(f"\n=== TabNet sweep ({total} configs) ===")
    if TabNetClassifier is None:
        print(f"[TabNet] skipped: pytorch-tabnet unavailable ({TABNET_IMPORT_ERROR})")
        return {
            "model": "TabNet", "split": "skipped", "param": "skipped",
            "param_dict": {}, "accuracy": 0.0, "f1": -1.0, "precision": 0.0,
            "auroc": None, "skipped": True,
            "skip_reason": f"pytorch-tabnet unavailable: {TABNET_IMPORT_ERROR}",
        }

    X_train, X_val, scaler = scaled_partitions(splits)
    y_train = splits["train"]["fault_label"].astype(int)
    y_val = splits["val"]["fault_label"].astype(int)

    # evaluate() expects DataFrame in / predict out; TabNet wants numpy.
    class TabNetWrapper:
        def __init__(self, m):
            self.m = m
        def predict(self, X):
            return self.m.predict(X.values if isinstance(X, pd.DataFrame) else X)
        def predict_proba(self, X):
            return self.m.predict_proba(X.values if isinstance(X, pd.DataFrame) else X)
        def save_model(self, path):
            self.m.save_model(path)

    best = {"f1": -1.0}
    for n_d in TABNET_N_D_LIST:
        for n_steps in TABNET_N_STEPS_LIST:
            model = TabNetClassifier(
                n_d=n_d, n_a=n_d, n_steps=n_steps, gamma=1.5,
                n_independent=1, n_shared=2, momentum=0.02,
                mask_type="sparsemax",
                optimizer_fn=torch.optim.Adam,
                optimizer_params=dict(lr=2e-2, weight_decay=1e-3),
                scheduler_params={"step_size": 10, "gamma": 0.9},
                scheduler_fn=torch.optim.lr_scheduler.StepLR,
                verbose=0, seed=RANDOM_STATE,
            )
            model.fit(
                X_train.values, y_train.values,
                eval_set=[(X_val.values, y_val.values)],
                eval_name=["val"], eval_metric=["balanced_accuracy"],
                weights=1,                       # balanced sampling
                max_epochs=50, patience=7,
                batch_size=256, virtual_batch_size=128,
                num_workers=0, drop_last=False,
            )
            wrapped = TabNetWrapper(model)
            result = evaluate(wrapped, X_val, y_val, "TabNet",
                              {"n_d": n_d, "n_steps": n_steps})
            if result["f1"] > best.get("f1", -1.0):
                best = {**result, "model_obj": wrapped, "scaler": scaler}
    print(f"--- best TabNet: {best['param']}  f1={best['f1']:.4f}")
    return best


# ── Notebook CELL 11: CNN sweep (windowed, early stopping) ─────────────────
def sweep_cnn(splits: dict, num_classes: int):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    total = len(CNN_CONV_CHANNELS_LIST) * len(CNN_HIDDEN_DIMS) * len(CNN_KERNEL_SIZES)
    print(f"\n=== CNN sweep ({total} configs, window {CNN_WINDOW_SIZE}, "
          f"max {CNN_MAX_EPOCHS} epochs, patience {CNN_PATIENCE}) on {device} ===")

    _, _, scaler = scaled_partitions(splits)
    X_train_w, y_train_w, X_val_w, y_val_w = windowed_partitions(
        splits, scaler, CNN_WINDOW_SIZE,
    )
    print(f"[data] windows: train={X_train_w.shape}  val={X_val_w.shape}")

    X_train_t = torch.tensor(X_train_w, dtype=torch.float32, device=device)
    X_val_t = torch.tensor(X_val_w, dtype=torch.float32, device=device)
    y_train_t = torch.tensor(y_train_w, dtype=torch.long, device=device)
    loader = DataLoader(TensorDataset(X_train_t, y_train_t),
                        batch_size=CNN_BATCH_SIZE, shuffle=True)
    weights = class_weight_tensor(y_train_w, device)

    best = {"f1": -1.0}
    config_idx = 0
    for conv_channels in CNN_CONV_CHANNELS_LIST:
        for hidden_dim in CNN_HIDDEN_DIMS:
            for kernel_size in CNN_KERNEL_SIZES:
                config_idx += 1
                t0 = time.time()
                model = CNNClassifier(
                    input_dim=len(FEATURES), num_classes=num_classes,
                    window_size=CNN_WINDOW_SIZE, conv_channels=conv_channels,
                    kernel_size=kernel_size, hidden_dim=hidden_dim,
                    dropout=CNN_DROPOUT,
                ).to(device)
                state, best_epoch, _ = fit_torch_with_early_stopping(
                    model, loader, X_val_t, y_val_w,
                    lr=CNN_LR, weight_decay=1e-4, class_weights=weights,
                    max_epochs=CNN_MAX_EPOCHS, patience=CNN_PATIENCE,
                )
                acc, f1, precision, _ = torch_val_scores(model, X_val_t, y_val_w)
                if f1 > best["f1"]:
                    best = {
                        "model": "CNN", "split": SPLIT_DESCRIPTION,
                        "param": f"conv_channels={conv_channels}, hidden={hidden_dim}, "
                                 f"kernel={kernel_size}, best_epoch={best_epoch}",
                        "param_dict": {
                            "conv_channels": conv_channels, "hidden_dim": hidden_dim,
                            "kernel_size": kernel_size, "lr": CNN_LR,
                            "epochs": best_epoch, "max_epochs": CNN_MAX_EPOCHS,
                            "dropout": CNN_DROPOUT, "window": CNN_WINDOW_SIZE,
                        },
                        "accuracy": acc, "f1": f1, "precision": precision,
                        "auroc": None,
                        "state_dict": copy.deepcopy(state),
                        "scaler": scaler,
                    }
                print(
                    f"[{config_idx:>2}/{total}] cc={conv_channels:<3} h={hidden_dim:<3} "
                    f"k={kernel_size:<3} best_epoch={best_epoch:<3} acc={acc:.4f} "
                    f"f1={f1:.4f} ({time.time()-t0:.1f}s)"
                )
    print(f"--- best CNN: {best['param']}  f1={best['f1']:.4f}")
    return best, device


# ── Notebook CELL 12: Bi-LSTM sweep (windowed, early stopping) ─────────────
def sweep_bilstm(splits: dict, num_classes: int):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    total = len(BILSTM_HIDDEN_DIMS) * len(BILSTM_LAYERS) * len(BILSTM_LR_LIST)
    print(f"\n=== Bi-LSTM sweep ({total} configs, window {BILSTM_WINDOW_SIZE}, "
          f"max {BILSTM_MAX_EPOCHS} epochs, patience {BILSTM_PATIENCE}) on {device} ===")

    _, _, scaler = scaled_partitions(splits)
    X_train_w, y_train_w, X_val_w, y_val_w = windowed_partitions(
        splits, scaler, BILSTM_WINDOW_SIZE,
    )
    X_train_t = torch.tensor(X_train_w, dtype=torch.float32, device=device)
    X_val_t = torch.tensor(X_val_w, dtype=torch.float32, device=device)
    y_train_t = torch.tensor(y_train_w, dtype=torch.long, device=device)
    loader = DataLoader(TensorDataset(X_train_t, y_train_t),
                        batch_size=BILSTM_BATCH_SIZE, shuffle=True)
    weights = class_weight_tensor(y_train_w, device)

    best = {"f1": -1.0}
    config_idx = 0
    for hidden_dim in BILSTM_HIDDEN_DIMS:
        for num_layers in BILSTM_LAYERS:
            for lr in BILSTM_LR_LIST:
                config_idx += 1
                t0 = time.time()
                model = BiLSTMClassifier(
                    input_dim=len(FEATURES), num_classes=num_classes,
                    window_size=BILSTM_WINDOW_SIZE, hidden_dim=hidden_dim,
                    num_layers=num_layers, dropout=BILSTM_DROPOUT,
                ).to(device)
                state, best_epoch, _ = fit_torch_with_early_stopping(
                    model, loader, X_val_t, y_val_w,
                    lr=lr, weight_decay=1e-4, class_weights=weights,
                    max_epochs=BILSTM_MAX_EPOCHS, patience=BILSTM_PATIENCE,
                )
                acc, f1, precision, _ = torch_val_scores(model, X_val_t, y_val_w)
                if f1 > best["f1"]:
                    best = {
                        "model": "Bi-LSTM", "split": SPLIT_DESCRIPTION,
                        "param": f"hidden={hidden_dim}, layers={num_layers}, "
                                 f"lr={lr}, best_epoch={best_epoch}",
                        "param_dict": {
                            "hidden_dim": hidden_dim, "num_layers": num_layers,
                            "lr": lr, "epochs": best_epoch,
                            "max_epochs": BILSTM_MAX_EPOCHS,
                            "dropout": BILSTM_DROPOUT, "window": BILSTM_WINDOW_SIZE,
                        },
                        "accuracy": acc, "f1": f1, "precision": precision,
                        "auroc": None,
                        "state_dict": copy.deepcopy(state),
                        "scaler": scaler,
                    }
                print(
                    f"[{config_idx:>2}/{total}] h={hidden_dim:<4} layers={num_layers} "
                    f"lr={lr:<6} best_epoch={best_epoch:<3} acc={acc:.4f} f1={f1:.4f} "
                    f"({time.time()-t0:.1f}s)"
                )
    print(f"--- best Bi-LSTM: {best['param']}  f1={best['f1']:.4f}")
    return best, device


# ── Saving ─────────────────────────────────────────────────────────────────
def _final_report(y_true, y_pred, label: str) -> dict[str, float]:
    seen = sorted(set(int(v) for v in list(y_true) + list(y_pred)))
    names = [CLASS_NAMES[i] if 0 <= i < len(CLASS_NAMES) else str(i) for i in seen]
    print(f"\n=== {label} — canonical demo holdout ===")
    print(classification_report(y_true, y_pred, labels=seen, target_names=names, zero_division=0))
    return {
        "test_accuracy": float(accuracy_score(y_true, y_pred)),
        "test_f1": float(f1_score(y_true, y_pred, average="macro")),
        "test_precision": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
    }


def _base_metadata(best: dict, family: str, artifact_name: str) -> dict:
    return {
        "model_name": artifact_name,
        "model_family": family,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trained_on_dataset": "dtx_ai_master_dataset.csv",
        "feature_count": len(FEATURES),
        "num_classes": len(CLASS_NAMES),
        "feature_order_ref": "services/ai/models/shared/feature_order.json",
        "class_mapping": {str(i): n for i, n in enumerate(CLASS_NAMES)},
        "training_split": SPLIT_DESCRIPTION,
        "best_params": best["param_dict"],
        "leakage_controls": (
            "per-episode temporal split with purge gap; demo holdout is the "
            "future tail of every fault run and is never used in training"
        ),
    }


def _dump_scaler(out_dir: Path, scaler) -> bool:
    if scaler is None:
        return False
    joblib.dump(scaler, out_dir / "scaler.pkl")
    return True


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
    scaler_saved = _dump_scaler(out_dir, best["scaler"])
    metadata = {
        **_base_metadata(best, family, artifact_name),
        "scaler_required": scaler_saved,
        "scaler_path": f"services/ai/models/{out_dir.name}/scaler.pkl" if scaler_saved else None,
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
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"[save] {out_dir}/{artifact_name}  +  metadata.json")
    return test_metrics


def save_lstm_artifact(best: dict, device: torch.device, num_classes: int,
                       demo_holdout: pd.DataFrame):
    out_dir = MODELS_ROOT / "lstm_ae"
    out_dir.mkdir(parents=True, exist_ok=True)
    pth_path = out_dir / "best_lstmae.pth"
    torch.save(best["state_dict"], pth_path)
    _dump_scaler(out_dir, best["scaler"])

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
    test_metrics = _final_report(y_holdout, y_pred, "LSTM-AE+CLS")

    metadata = {
        **_base_metadata(best, "lstm_autoencoder_pytorch", "best_lstmae.pth"),
        "scaler_required": True,
        "scaler_path": "services/ai/models/lstm_ae/scaler.pkl",
        "input_shape": {"batch": "N", "sequence_length": 1, "feature_dim": len(FEATURES)},
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
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"[save] {pth_path}  +  metadata.json")
    return test_metrics


def save_tabnet_artifact(best: dict, demo_holdout: pd.DataFrame):
    if best.get("skipped"):
        print(f"[save] TabNet skipped; no artifact written ({best.get('skip_reason', 'unknown')})")
        return None
    out_dir = MODELS_ROOT / "tabnet"
    out_dir.mkdir(parents=True, exist_ok=True)

    X_holdout = pd.DataFrame(best["scaler"].transform(demo_holdout[FEATURES]), columns=FEATURES)
    y_holdout = demo_holdout["fault_label"].astype(int).values
    y_pred = best["model_obj"].predict(X_holdout)
    test_metrics = _final_report(y_holdout, y_pred, "TabNet")

    best["model_obj"].save_model(str(out_dir / "best_tabnet"))
    _dump_scaler(out_dir, best["scaler"])
    metadata = {
        **_base_metadata(best, "tabnet_pytorch", "best_tabnet.zip"),
        "scaler_required": True,
        "scaler_path": "services/ai/models/tabnet/scaler.pkl",
        "metrics": {
            "val_accuracy": round(best["accuracy"], 6),
            "val_f1": round(best["f1"], 6),
            "val_precision": round(best["precision"], 6),
            **{k: round(v, 6) for k, v in test_metrics.items()},
        },
        "decision_type": "multiclass_classifier",
        "default_threshold": 0.5,
        "supports_tree_xai": False,
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"[save] {out_dir}/best_tabnet.zip  +  metadata.json")
    return test_metrics


def _windowed_holdout_eval(model, scaler, demo_holdout: pd.DataFrame,
                           window: int, device: torch.device):
    """Score a windowed torch model on the demo holdout, windows per episode."""
    scaled = pd.DataFrame(scaler.transform(demo_holdout[FEATURES]), columns=FEATURES)
    scaled["fault_label"] = demo_holdout["fault_label"].astype(int).values
    scaled["_g"] = episode_groups(demo_holdout).astype(str).values
    xs, ys = [], []
    for _, seg in scaled.groupby("_g", sort=False):
        seg = seg.drop(columns=["_g"])
        if len(seg) < window:
            continue
        X_w, y_w = engineer_features(seg, window=window, step=WINDOW_STEP)
        if len(X_w):
            xs.append(X_w)
            ys.append(y_w)
    X_holdout_w = np.concatenate(xs, axis=0)
    y_holdout = np.concatenate(ys, axis=0)
    X_t = torch.tensor(X_holdout_w, dtype=torch.float32, device=device)
    with torch.no_grad():
        y_pred = torch.argmax(F.softmax(model(X_t), dim=-1), dim=-1).cpu().numpy()
    return y_holdout, y_pred


def save_cnn_artifact(best: dict, device: torch.device, num_classes: int,
                      demo_holdout: pd.DataFrame):
    out_dir = MODELS_ROOT / "cnn"
    out_dir.mkdir(parents=True, exist_ok=True)
    p = best["param_dict"]

    final_model = CNNClassifier(
        input_dim=len(FEATURES), num_classes=num_classes,
        window_size=p["window"], conv_channels=p["conv_channels"],
        kernel_size=p["kernel_size"], hidden_dim=p["hidden_dim"],
        dropout=p["dropout"],
    ).to(device)
    final_model.load_state_dict(best["state_dict"])
    final_model.eval()

    y_holdout, y_pred = _windowed_holdout_eval(
        final_model, best["scaler"], demo_holdout, p["window"], device,
    )
    test_metrics = _final_report(y_holdout, y_pred, "CNN")

    torch.save(best["state_dict"], out_dir / "best_cnn.pth")
    _dump_scaler(out_dir, best["scaler"])
    metadata = {
        **_base_metadata(best, "cnn_pytorch", "best_cnn.pth"),
        "scaler_required": True,
        "scaler_path": "services/ai/models/cnn/scaler.pkl",
        "metrics": {
            "val_accuracy": round(best["accuracy"], 6),
            "val_f1": round(best["f1"], 6),
            "val_precision": round(best["precision"], 6),
            **{k: round(v, 6) for k, v in test_metrics.items()},
        },
        "decision_type": "multiclass_classifier",
        "default_threshold": 0.5,
        "supports_tree_xai": False,
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"[save] {out_dir}/best_cnn.pth  +  metadata.json")
    return test_metrics


def save_bilstm_artifact(best: dict, device: torch.device, num_classes: int,
                         demo_holdout: pd.DataFrame):
    out_dir = MODELS_ROOT / "bilstm"
    out_dir.mkdir(parents=True, exist_ok=True)
    p = best["param_dict"]

    final_model = BiLSTMClassifier(
        input_dim=len(FEATURES), num_classes=num_classes, window_size=p["window"],
        hidden_dim=p["hidden_dim"], num_layers=p["num_layers"], dropout=p["dropout"],
    ).to(device)
    final_model.load_state_dict(best["state_dict"])
    final_model.eval()

    y_holdout, y_pred = _windowed_holdout_eval(
        final_model, best["scaler"], demo_holdout, p["window"], device,
    )
    test_metrics = _final_report(y_holdout, y_pred, "Bi-LSTM")

    torch.save(best["state_dict"], out_dir / "best_bilstm.pth")
    _dump_scaler(out_dir, best["scaler"])
    metadata = {
        **_base_metadata(best, "bilstm_pytorch", "best_bilstm.pth"),
        "scaler_required": True,
        "scaler_path": "services/ai/models/bilstm/scaler.pkl",
        "metrics": {
            "val_accuracy": round(best["accuracy"], 6),
            "val_f1": round(best["f1"], 6),
            "val_precision": round(best["precision"], 6),
            **{k: round(v, 6) for k, v in test_metrics.items()},
        },
        "decision_type": "multiclass_classifier",
        "default_threshold": 0.5,
        "supports_tree_xai": False,
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"[save] {out_dir}/best_bilstm.pth  +  metadata.json")
    return test_metrics


# ── Notebook CELL 13: Global Leaderboard & winner retrain ──────────────────
def save_overall_best(candidates: dict, splits: dict, device: torch.device):
    records = []
    for name, b in candidates.items():
        if b and b.get("f1", -1.0) >= 0:
            records.append({
                "model": name,
                "val_f1": b.get("f1", 0.0),
                "val_accuracy": b.get("accuracy", 0.0),
                "holdout_f1": (b.get("test_metrics") or {}).get("test_f1"),
                "holdout_accuracy": (b.get("test_metrics") or {}).get("test_accuracy"),
            })
    # mergesort = stable, so val-F1 ties resolve to the earlier candidate
    # (fixed dict order) instead of an arbitrary quicksort permutation.
    results_df = (
        pd.DataFrame(records)
        .sort_values(by=["val_f1", "val_accuracy"], ascending=False, kind="mergesort")
        .reset_index(drop=True)
    )
    print("\n" + "=" * 70)
    print("FULL RESULTS TABLE (LEADERBOARD — selected on val, reported on holdout)")
    print("=" * 70)
    print(results_df.to_string(index=False))

    overall_name = results_df.iloc[0]["model"]
    overall = candidates[overall_name]
    print(f"\n=== Global Winner: {overall_name} (val F1: {overall['f1']:.4f}) ===")

    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    # Remove every stale winner artifact first — a .pkl from a previous tree
    # winner must not survive next to this run's .pth (and vice versa).
    for stale in ("model_best.pkl", "model_best.pth", "model_best.zip"):
        (SHARED_DIR / stale).unlink(missing_ok=True)
    (SHARED_DIR / "feature_order.json").write_text(json.dumps(FEATURES, indent=2) + "\n")
    (SHARED_DIR / "leaderboard.json").write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "split": SPLIT_DESCRIPTION,
            "winner": overall_name,
            "results": records,
        }, indent=2) + "\n"
    )

    pool = splits["pool"]
    demo_holdout = splits["demo_holdout"]
    y_pool = pool["fault_label"].astype(int)
    p = overall["param_dict"]

    if overall_name in ("LightGBM", "XGBoost"):
        # Retrain on the full pool with the early-stopped round count.
        rounds = int(p.get("best_rounds", 200))
        if overall_name == "LightGBM":
            final_model = lgb.LGBMClassifier(
                n_estimators=rounds, max_depth=p["max_depth"],
                num_leaves=p["num_leaves"], learning_rate=p["learning_rate"],
                random_state=RANDOM_STATE, class_weight="balanced", verbose=-1,
            )
            final_model.fit(pool[FEATURES], y_pool)
        else:
            final_model = xgb.XGBClassifier(
                n_estimators=rounds, max_depth=p["max_depth"],
                learning_rate=p["learning_rate"], random_state=RANDOM_STATE,
                eval_metric="mlogloss", verbosity=0,
            )
            final_model.fit(pool[FEATURES], y_pool,
                            sample_weight=compute_sample_weight("balanced", y_pool))
        joblib.dump(final_model, SHARED_DIR / "model_best.pkl")
        # The winner consumes raw features; keep a reference pipeline anyway so
        # shared/scaler.pkl can never go stale relative to model_best.
        reference_scaler = build_scaling_pipeline().fit(pool[FEATURES])
        joblib.dump(reference_scaler, SHARED_DIR / "scaler.pkl")
        X_holdout_eval = demo_holdout[FEATURES]
        y_pred = final_model.predict(X_holdout_eval)

    elif overall_name == "RandomForest":
        final_model = RandomForestClassifier(
            n_estimators=p["n_estimators"], max_depth=p["max_depth"],
            random_state=RANDOM_STATE, class_weight="balanced", n_jobs=-1,
        )
        scaler = build_scaling_pipeline()
        X_pool_s = pd.DataFrame(scaler.fit_transform(pool[FEATURES]), columns=FEATURES)
        final_model.fit(X_pool_s, y_pool)
        joblib.dump(final_model, SHARED_DIR / "model_best.pkl")
        joblib.dump(scaler, SHARED_DIR / "scaler.pkl")
        X_holdout_eval = pd.DataFrame(scaler.transform(demo_holdout[FEATURES]), columns=FEATURES)
        y_pred = final_model.predict(X_holdout_eval)

    else:
        # Torch/TabNet winners: reuse the per-family sweep artifact (no pool
        # retrain — early-stopped epoch counts don't transfer cleanly), but
        # mirror the winner's scaler + artifact into shared/.
        if overall.get("scaler") is not None:
            joblib.dump(overall["scaler"], SHARED_DIR / "scaler.pkl")
        if overall_name == "TabNet":
            import shutil
            src = MODELS_ROOT / "tabnet" / "best_tabnet.zip"
            if src.exists():
                shutil.copyfile(src, SHARED_DIR / "model_best.zip")
        else:
            torch.save(overall["state_dict"], SHARED_DIR / "model_best.pth")
        print(f"[{overall_name}] sweep artifact mirrored into shared/.")
        return overall_name

    _final_report(
        demo_holdout["fault_label"].astype(int).values, y_pred,
        f"model_best ({overall_name}, retrained on full pool)",
    )
    print(f"[save] {SHARED_DIR}/model_best.*  +  scaler.pkl  +  feature_order.json")
    return overall_name


# ── orchestration ──────────────────────────────────────────────────────────
def main():
    print(f"[env] python={sys.version.split()[0]} torch={torch.__version__} cuda={torch.cuda.is_available()}")
    print(f"[data] loading {AI_ROOT}/dtx_ai_master_dataset.csv")
    df = load_data(str(AI_ROOT / "dtx_ai_master_dataset.csv"))

    splits = prepare_canonical_splits(df)
    print(
        f"[data] split={SPLIT_DESCRIPTION}\n"
        f"[data] train={splits['train'].shape}  val={splits['val'].shape}  "
        f"demo_holdout={splits['demo_holdout'].shape}\n"
        f"[data] holdout distribution: "
        f"{splits['demo_holdout']['fault_label'].value_counts().sort_index().to_dict()}"
    )
    num_classes = len(CLASS_NAMES)

    run_sanity_baselines(splits["pool"], splits["demo_holdout"])

    demo_holdout = splits["demo_holdout"]

    best_rf = sweep_random_forest(splits)
    best_rf["test_metrics"] = save_tree_artifact(
        best_rf, demo_holdout, MODELS_ROOT / "random_forest", "best_rf.pkl",
        "random_forest", supports_tree_xai=True)

    best_lgbm = sweep_lightgbm(splits)
    best_lgbm["test_metrics"] = save_tree_artifact(
        best_lgbm, demo_holdout, MODELS_ROOT / "lightgbm", "best_lgbm.pkl",
        "lightgbm", supports_tree_xai=True)

    best_xgb = sweep_xgboost(splits)
    best_xgb["test_metrics"] = save_tree_artifact(
        best_xgb, demo_holdout, MODELS_ROOT / "xgboost", "best_xgb.pkl",
        "xgboost", supports_tree_xai=True)

    best_tabnet = sweep_tabnet(splits)
    best_tabnet["test_metrics"] = save_tabnet_artifact(best_tabnet, demo_holdout)

    best_cnn, device = sweep_cnn(splits, num_classes)
    best_cnn["test_metrics"] = save_cnn_artifact(best_cnn, device, num_classes, demo_holdout)

    best_bilstm, device = sweep_bilstm(splits, num_classes)
    best_bilstm["test_metrics"] = save_bilstm_artifact(best_bilstm, device, num_classes, demo_holdout)

    best_lstm, device = sweep_lstm_ae(splits, num_classes)
    best_lstm["test_metrics"] = save_lstm_artifact(best_lstm, device, num_classes, demo_holdout)

    candidates = {
        "RandomForest": best_rf,
        "LightGBM": best_lgbm,
        "XGBoost": best_xgb,
        "TabNet": best_tabnet,
        "CNN": best_cnn,
        "Bi-LSTM": best_bilstm,
        "LSTM-AE": best_lstm,
    }
    save_overall_best(candidates, splits, device)

    print("\n[done] all artifacts retrained with the leakage-safe canonical split.")


if __name__ == "__main__":
    main()
