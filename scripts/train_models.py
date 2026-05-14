#!/usr/bin/env python3
"""Retrain every model in services/ai/ai/models/ from scratch — exact mirror of
services/ai/dtxai_model_training.ipynb cells 2/3/5/6/7/8/10.

Hyperparameter grids and split configurations match the notebook one-for-one:

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

After all four sweeps, the overall best non-LSTM model is retrained on
(train+val) of its own best split (cell 10's behaviour) and saved as
model_best.pkl + scaler.pkl into services/ai/ai/models/shared/.

This is the file the runtime registry actually reads.

Tree models train on CPU in <1s each; LSTM-AE uses GPU when available.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

import lightgbm as lgb
import xgboost as xgb

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_ROOT = REPO_ROOT / "services" / "ai"
MODELS_ROOT = AI_ROOT / "ai" / "models"
SHARED_DIR = MODELS_ROOT / "shared"

sys.path.insert(0, str(AI_ROOT))
from preprocessing import (  # noqa: E402
    CLASS_NAMES,
    FEATURES,
    engineer_features,
    load_data,
    split_training_pool_and_holdout,
)
from ai.lstm_classifier import LSTMAutoencoderClassifier  # noqa: E402

# ── Notebook cell 2: CONFIGURATION ─────────────────────────────────────────
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


# ── Notebook cell 3: prepare_splits ────────────────────────────────────────
def prepare_splits(
    X: pd.DataFrame,
    y: pd.Series,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    random_state: int = RANDOM_STATE,
):
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y, test_size=test_ratio, random_state=random_state, stratify=y,
    )
    val_size_adjusted = val_ratio / (train_ratio + val_ratio)
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp, test_size=val_size_adjusted,
        random_state=random_state, stratify=y_temp,
    )
    scaler = StandardScaler()
    X_train_s = pd.DataFrame(scaler.fit_transform(X_train), columns=FEATURES)
    X_val_s = pd.DataFrame(scaler.transform(X_val), columns=FEATURES)
    X_test_s = pd.DataFrame(scaler.transform(X_test), columns=FEATURES)
    return X_train_s, X_val_s, X_test_s, y_train, y_val, y_test, scaler


# ── Notebook cell 4: evaluate_model (sans plotting) ────────────────────────
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


# ── Notebook cell 5: RandomForest sweep ────────────────────────────────────
def sweep_random_forest(X, y):
    print("\n=== RandomForest sweep (5 splits × 2 × 2 = 20 configs) ===")
    best = {"f1": -1.0}
    for tr, vr, te in SPLIT_CONFIGS:
        X_train, X_val, _, y_train, y_val, _, scaler = prepare_splits(X, y, tr, vr, te)
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


# ── Notebook cell 6: LightGBM sweep ────────────────────────────────────────
def sweep_lightgbm(X, y):
    print("\n=== LightGBM sweep (5 splits × 2 × 2 × 2 = 40 configs) ===")
    best = {"f1": -1.0}
    for tr, vr, te in SPLIT_CONFIGS:
        X_train, X_val, _, y_train, y_val, _, scaler = prepare_splits(X, y, tr, vr, te)
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


# ── Notebook cell 7: XGBoost sweep ─────────────────────────────────────────
def sweep_xgboost(X, y):
    print("\n=== XGBoost sweep (5 splits × 2 × 2 × 2 = 40 configs) ===")
    best = {"f1": -1.0}
    for tr, vr, te in SPLIT_CONFIGS:
        X_train, X_val, _, y_train, y_val, _, scaler = prepare_splits(X, y, tr, vr, te)
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


# ── Notebook cell 8: LSTM-AE+CLS sweep ─────────────────────────────────────
def sweep_lstm_ae(X, y, num_classes: int):
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
        X_train, X_val, X_test, y_train, y_val, y_test, scaler = prepare_splits(X, y, tr, vr, te)
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
    # Final test report uses the canonical demo holdout (rows the model never
    # trained on) — gives an honest, model-comparable generalisation number
    # instead of resubstitution on the model's own split.
    X_holdout = pd.DataFrame(
        best["scaler"].transform(demo_holdout[FEATURES]), columns=FEATURES,
    )
    y_holdout = demo_holdout["fault_label"].astype(int)
    y_pred = best["model_obj"].predict(X_holdout)
    test_metrics = _final_report(y_holdout.values, y_pred, family)

    joblib.dump(best["model_obj"], out_dir / artifact_name)
    metadata = {
        "model_name": artifact_name,
        "model_family": family,
        "trained_on_dataset": "ziya07/industrial-iot-fault-detection-dataset",
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
            "val_auroc": (None if best["auroc"] is None else round(best["auroc"], 6)),
            **{k: round(v, 6) for k, v in test_metrics.items()},
        },
        "decision_type": "multiclass_classifier",
        "default_threshold": None,
        "supports_tree_xai": supports_tree_xai,
        "notes": "Trained via scripts/train_models.py — exact mirror of dtxai_model_training.ipynb cells 5/6/7.",
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
        "trained_on_dataset": "ziya07/industrial-iot-fault-detection-dataset",
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
            "Trained via scripts/train_models.py — exact mirror of "
            "dtxai_model_training.ipynb cell 8. Architecture is "
            "ai.lstm_classifier.LSTMAutoencoderClassifier."
        ),
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"[save] {pth_path}  +  metadata.json")


# ── Notebook cell 10: pick overall best non-LSTM, retrain on train+val ─────
def save_overall_best(best_rf, best_lgbm, best_xgb, X, y, demo_holdout: pd.DataFrame):
    candidates = {"RandomForest": best_rf, "LightGBM": best_lgbm, "XGBoost": best_xgb}
    overall_name = max(candidates, key=lambda k: candidates[k]["f1"])
    overall = candidates[overall_name]
    print(f"\n=== Overall best non-LSTM: {overall_name}  split={overall['split']}  "
          f"f1={overall['f1']:.4f} ===")

    tr, vr, te = overall["split_tuple"]
    X_train, X_val, X_test, y_train, y_val, y_test, scaler = prepare_splits(X, y, tr, vr, te)
    X_final = pd.concat([X_train, X_val])
    y_final = pd.concat([y_train, y_val])

    p = overall["param_dict"]
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
    else:
        final_model = xgb.XGBClassifier(
            n_estimators=p["n_estimators"], max_depth=p["max_depth"],
            learning_rate=p["learning_rate"],
            random_state=RANDOM_STATE, eval_metric="mlogloss", verbosity=0,
        )
    final_model.fit(X_final, y_final)

    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, SHARED_DIR / "model_best.pkl")
    joblib.dump(scaler, SHARED_DIR / "scaler.pkl")
    (SHARED_DIR / "feature_order.json").write_text(json.dumps(FEATURES, indent=2) + "\n")
    print(f"[save] {SHARED_DIR}/model_best.pkl  +  scaler.pkl  +  feature_order.json")

    # Final eval against the canonical demo holdout — same data the dashboard
    # demo will replay against, so this metric is what users actually see.
    X_holdout_scaled = pd.DataFrame(
        scaler.transform(demo_holdout[FEATURES]), columns=FEATURES,
    )
    y_holdout = demo_holdout["fault_label"].astype(int)
    y_holdout_pred = final_model.predict(X_holdout_scaled)
    _final_report(
        y_holdout.values, y_holdout_pred,
        f"model_best.pkl ({overall_name}, retrained on train+val, scored on demo holdout)",
    )
    return overall_name


# ── orchestration ──────────────────────────────────────────────────────────
def main():
    print(f"[env] python={sys.version.split()[0]} torch={torch.__version__} cuda={torch.cuda.is_available()}")
    print(f"[data] loading {AI_ROOT}/dtx_ai_master_dataset.csv")
    df = load_data(str(AI_ROOT / "dtx_ai_master_dataset.csv"))
    df = engineer_features(df)

    # Carve out the canonical 20% demo holdout (stratified, fixed seed). Every
    # sweep below sees only the 80% training pool — guarantees the demo replays
    # rows the models never trained on.
    training_pool, demo_holdout = split_training_pool_and_holdout(df)
    print(
        f"[data] training_pool={training_pool.shape}  demo_holdout={demo_holdout.shape}  "
        f"(holdout distribution: {demo_holdout['fault_label'].value_counts().sort_index().to_dict()})"
    )

    X = training_pool[FEATURES]
    y = training_pool["fault_label"].astype(int)
    num_classes = int(y.nunique())
    print(f"[data] using training pool {training_pool.shape}, {num_classes} classes, "
          f"distribution: {y.value_counts().sort_index().to_dict()}")

    # Cells 5/6/7 — independent per-model sweeps.
    best_rf = sweep_random_forest(X, y)
    best_lgbm = sweep_lightgbm(X, y)
    best_xgb = sweep_xgboost(X, y)

    save_tree_artifact(best_rf, demo_holdout, MODELS_ROOT / "random_forest", "best_rf.pkl",
                       "random_forest", supports_tree_xai=True)
    save_tree_artifact(best_lgbm, demo_holdout, MODELS_ROOT / "lightgbm", "best_lgbm.pkl",
                       "lightgbm", supports_tree_xai=True)
    save_tree_artifact(best_xgb, demo_holdout, MODELS_ROOT / "xgboost", "best_xgb.pkl",
                       "xgboost", supports_tree_xai=True)

    # Cell 8 — LSTM-AE+CLS sweep.
    best_lstm, device = sweep_lstm_ae(X, y, num_classes)
    save_lstm_artifact(best_lstm, device, num_classes, demo_holdout)

    # Cell 10 — overall best non-LSTM retrained on train+val + scaler.pkl save.
    save_overall_best(best_rf, best_lgbm, best_xgb, X, y, demo_holdout)

    print("\n[done] all artifacts retrained against current sklearn/lightgbm/xgboost/torch versions.")


if __name__ == "__main__":
    main()
