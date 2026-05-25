"""
build_t5_samples.py

Stage 1 of the T5 explainer dataset pipeline.

Runs the LSTM-AE classifier over every NaN-free row of the master dataset,
captures the native model output (the classifier head, taken before any
rule-based guardrail or fallback merge applied downstream), and writes a
confidence-stratified, class-balanced sample to `samples.csv`.

The signal contract matches ai/detector.py:_run_lstm_autoencoder:

    reconstructed, logits = model(tensor)              # tensor shape [N, 1, 19]
    probs       = softmax(logits)
    pred_class  = argmax(probs)
    confidence  = probs[pred_class]
    recon_mse   = mean((reconstructed - tensor) ** 2)  # global, per row

`build_input_text()` is the single source of truth for the T5 input format and
is also imported by t5_inference.py, so training and inference share one
identical input string.

Usage (run from the repo root):

    export DTX_ACTIVE_MODEL=lstm_ae
    python services/ai/build_t5_samples.py \
        --dataset services/ai/dtx_ai_master_dataset.csv \
        --out samples.csv \
        --per-class 500
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# This file lives in services/ai/, alongside preprocessing.py and the ai/
# package, so its own directory is the import root.
AI_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(AI_ROOT))

from preprocessing import FEATURES, CLASS_NAMES, INT_TO_LABEL, load_data  # noqa: E402
from ai.model_loader import load_runtime_model  # noqa: E402


# --------------------------------------------------------------------------
# T5 input format — shared by this builder and t5_inference.py.
# --------------------------------------------------------------------------
T5_PREFIX = "explain anomaly: "


def _fmt(value: float, decimals: int) -> str:
    """Fixed-decimal formatting, never scientific notation."""
    return f"{float(value):.{decimals}f}"


def build_input_text(
    predicted_class: str,
    confidence: float,
    reconstruction_mse: float,
    logits: dict[str, float],
    features: dict[str, float],
) -> str:
    """Build the canonical T5 input string used for both training and inference.

    logits   : {class_name -> raw logit}, covering all CLASS_NAMES
    features : {feature_name -> raw, un-scaled value}, covering all FEATURES
    """
    logit_str = ", ".join(f"{c}={_fmt(logits[c], 2)}" for c in CLASS_NAMES)
    feat_str = " | ".join(f"{f}={_fmt(features[f], 4)}" for f in FEATURES)
    return (
        f"{T5_PREFIX}"
        f"predicted_class: {predicted_class} | "
        f"confidence: {_fmt(confidence, 4)} | "
        f"reconstruction_mse: {_fmt(reconstruction_mse, 4)} | "
        f"logits: {logit_str} | "
        f"{feat_str}"
    )


# --------------------------------------------------------------------------
# Inference over the full clean dataset
# --------------------------------------------------------------------------
def run_inference(dataset_path: str, batch_size: int = 4096) -> pd.DataFrame:
    import torch
    import torch.nn.functional as F

    runtime = load_runtime_model(requested_model="lstm_ae", strict_selection=True)
    if not runtime.available or runtime.family != "lstm_autoencoder_pytorch":
        raise RuntimeError(
            f"lstm_ae not loadable as autoencoder runtime: "
            f"available={runtime.available} family={runtime.family} reason={runtime.reason}"
        )
    if runtime.scaler is None:
        raise RuntimeError("Shared scaler.pkl not found — required for inference.")

    model = runtime.model
    scaler = runtime.scaler

    df = load_data(dataset_path)
    before = len(df)
    df = df.dropna(subset=FEATURES).reset_index(drop=True)
    dropped = before - len(df)
    print(f"[inference] rows: {before} -> {len(df)} clean (dropped {dropped} NaN-feature rows)")

    X_scaled = scaler.transform(df[FEATURES])          # imputer + scaler pipeline

    rows: list[dict] = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(df), batch_size):
            end = min(start + batch_size, len(df))
            xb = torch.tensor(X_scaled[start:end], dtype=torch.float32).unsqueeze(1)  # [b,1,19]
            recon, logits = model(xb)
            probs = F.softmax(logits, dim=-1)
            conf, pred = probs.max(dim=-1)
            mse = ((recon - xb) ** 2).mean(dim=(1, 2))   # per-row global MSE

            logits_np = logits.cpu().numpy()
            for i in range(end - start):
                src = df.iloc[start + i]
                pred_idx = int(pred[i].item())
                rec: dict = {
                    "predicted_class": INT_TO_LABEL[pred_idx],
                    "predicted_idx": pred_idx,
                    "confidence": float(conf[i].item()),
                    "reconstruction_mse": float(mse[i].item()),
                    "true_label": src["fault_label_name"],
                    "is_correct": int(pred_idx == int(src["fault_label"])),
                }
                for j, cname in enumerate(CLASS_NAMES):
                    rec[f"logit_{cname}"] = float(logits_np[i, j])
                for f in FEATURES:
                    rec[f] = float(src[f])               # RAW, un-scaled value
                rows.append(rec)
            print(f"[inference] {end}/{len(df)}", end="\r")
    print()
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Confidence-stratified, class-balanced selection
# --------------------------------------------------------------------------
HIGH_T = 0.95
LOW_T = 0.70
# Target mix within each class quota (filled in this priority order).
TARGET_MIX = {"low": 0.10, "med": 0.30, "high": 0.60}
# Cap on how much of a class quota may be filled by misclassified rows. These
# rows are prioritised because they carry the most uncertainty, but the cap
# keeps a single noisy class from dominating the quota.
MAX_MISCLASSIFIED_FRAC = 0.20


def _conf_bin(c: float) -> str:
    if c >= HIGH_T:
        return "high"
    if c >= LOW_T:
        return "med"
    return "low"


def select_samples(infer_df: pd.DataFrame, per_class: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    infer_df = infer_df.copy()
    infer_df["conf_bin"] = infer_df["confidence"].map(_conf_bin)

    picked: list[pd.DataFrame] = []
    for cname in CLASS_NAMES:
        pool = infer_df[infer_df["predicted_class"] == cname]
        if pool.empty:
            print(f"[select] WARNING: no predicted rows for class '{cname}'")
            continue

        # Prioritise misclassified rows for their uncertainty, but cap their
        # share of the quota so a single noisy class cannot dominate the set.
        mis = pool[pool["is_correct"] == 0]
        mis_cap = int(per_class * MAX_MISCLASSIFIED_FRAC)
        if len(mis) > mis_cap:
            mis_idx = rng.choice(mis.index.values, size=mis_cap, replace=False)
            chosen_idx = set(mis_idx.tolist())
        else:
            chosen_idx = set(mis.index.tolist())

        # Fill the remaining quota by confidence bin (low, then med, then high),
        # following the target mix but taking whatever is available when a bin
        # is short.
        remaining = max(per_class - len(chosen_idx), 0)
        for b in ("low", "med", "high"):
            if remaining <= 0:
                break
            bin_pool = pool[(pool["conf_bin"] == b) & (~pool.index.isin(chosen_idx))]
            want = int(round(per_class * TARGET_MIX[b]))
            take = min(want, len(bin_pool), remaining)
            if take > 0:
                take_idx = rng.choice(bin_pool.index.values, size=take, replace=False)
                chosen_idx.update(take_idx.tolist())
                remaining -= take

        # Top up from any remaining rows if the mix targets undershot the quota.
        if remaining > 0:
            leftover = pool[~pool.index.isin(chosen_idx)]
            take = min(remaining, len(leftover))
            if take > 0:
                take_idx = rng.choice(leftover.index.values, size=take, replace=False)
                chosen_idx.update(take_idx.tolist())

        sub = pool.loc[sorted(chosen_idx)]
        picked.append(sub)
        mis_taken = int((sub["is_correct"] == 0).sum())
        print(
            f"[select] {cname:<14} picked {len(sub):>4}  "
            f"(mis={mis_taken}/{len(mis)}, "
            f"low={int((sub.conf_bin=='low').sum())}, "
            f"med={int((sub.conf_bin=='med').sum())}, "
            f"high={int((sub.conf_bin=='high').sum())})"
        )

    out = pd.concat(picked, ignore_index=True)
    out = out.sample(frac=1.0, random_state=seed).reset_index(drop=True)   # shuffle
    out.insert(0, "id", range(1, len(out) + 1))

    # Build the T5 input string for every selected row.
    out["input_text"] = out.apply(
        lambda r: build_input_text(
            predicted_class=r["predicted_class"],
            confidence=r["confidence"],
            reconstruction_mse=r["reconstruction_mse"],
            logits={c: r[f"logit_{c}"] for c in CLASS_NAMES},
            features={f: r[f] for f in FEATURES},
        ),
        axis=1,
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="services/ai/dtx_ai_master_dataset.csv")
    ap.add_argument("--out", default="samples.csv")
    ap.add_argument("--per-class", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    infer_df = run_inference(args.dataset)
    print(f"[inference] overall accuracy = {infer_df['is_correct'].mean():.4f} "
          f"({int((infer_df['is_correct']==0).sum())} misclassified)")
    print("[inference] confidence distribution:")
    print(infer_df["confidence"].map(_conf_bin).value_counts().to_string())

    samples = select_samples(infer_df, per_class=args.per_class, seed=args.seed)
    samples.to_csv(args.out, index=False)
    print(f"\n[done] wrote {len(samples)} rows -> {args.out}")
    print("[done] columns:", list(samples.columns))


if __name__ == "__main__":
    main()
