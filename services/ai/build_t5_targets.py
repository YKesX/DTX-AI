"""
build_t5_targets.py

Stage 2 of the T5 explainer dataset pipeline.

Reads `samples.csv` (from build_t5_samples.py) and adds a `target_text` column:
a two-paragraph, hedged, English explanation of the model output for each row.
Writes `t5_dataset.csv` with the input_text / target_text pair the fine-tune
consumes, plus the raw signal columns for inspection.

Design
------
Explanations are generated deterministically from sentence templates filled
with the captured signals, so output is reproducible and cannot drift from what
the model produced.

The explanations are grounded in model signals — predicted_class, confidence,
the logit spread, and reconstruction_mse — and treat sensor features as neutral
measured context rather than as the stated cause of a prediction. This keeps
the text faithful to what the classifier actually exposes and avoids asserting
feature-to-class causation that the model does not make explicit. The operator
recommendations mirror ai/explainer.py:_RECOMMENDATIONS.

The CONFIG block below controls which feature channels may be quoted and the
reconstruction-error threshold used to describe a reading as typical or not.
These are sensible defaults; adjust them if a future model or dataset warrants
it, but no edit is required for the pipeline to run.

Usage:
    python scripts/build_t5_targets.py --in samples.csv --out t5_dataset.csv
"""

from __future__ import annotations

import argparse
import random

import pandas as pd

CLASS_NAMES = [
    "nominal", "bearing_wear", "overheat", "overload", "pressure_fault", "wheel_slip",
]

# Human-readable gloss for each class, used in prose.
CLASS_GLOSS = {
    "nominal": "normal operating behaviour",
    "bearing_wear": "a bearing-wear signature",
    "overheat": "an overheating signature",
    "overload": "an overload condition",
    "pressure_fault": "a pressure-system fault",
    "wheel_slip": "a wheel-slip condition",
}

# Operator recommendation per class. Mirrors ai/explainer.py:_RECOMMENDATIONS.
RECOMMENDATION = {
    "nominal": "No operator action is required; the asset remains within its normal envelope.",
    "bearing_wear": "A bearing inspection should be scheduled to confirm the indication.",
    "overheat": "Operators may wish to reduce load and verify the cooling path.",
    "overload": "Payload weight and drive-joint effort should be checked against rated capacity.",
    "pressure_fault": "The hydraulic / pneumatic line should be inspected for an out-of-range condition.",
    "wheel_slip": "Roller traction and surface conditions should be reviewed.",
}

# --------------------------------------------------------------------------
# CONFIG — sensible defaults; adjust if a future model or dataset warrants it.
# --------------------------------------------------------------------------

# Channels that may be quoted as a neutral observation, with their display
# format and label. Channels not listed here are still part of the model input
# but are not surfaced in prose. Each entry: (column, value_format, label).
OBSERVABLE = [
    ("temperature_c", "{v:.1f} degrees C", "temperature"),
    ("power_dissipated_w", "{v:.1f} W", "dissipated power"),
    ("pseudo_pressure_pa", "{v:.0f} Pa", "line pseudo-pressure"),
    ("drive_joint_effort", "{v:.0f}", "drive-joint effort"),
    ("vibration_magnitude", "{v:.2f}", "vibration magnitude"),
]

# Reconstruction-error cut-off: at or above this value a reading is described
# as less typical of the learned distribution; below it, as well reconstructed.
RECON_HIGH_THRESHOLD = 1.0


# --------------------------------------------------------------------------
# Sentence templates. {slots} are filled from the captured signals.
# --------------------------------------------------------------------------

# Confidence band -> hedging verb. Drives the whole tone of the explanation.
HEDGE = {
    "high": ["indicates", "points to", "is consistent with"],
    "med":  ["may indicate", "appears consistent with", "is suggestive of"],
    "low":  ["could tentatively indicate", "weakly suggests", "may — with low confidence — point to"],
}

# Paragraph 1, opening sentence: states the model's call.
# {conf} is shown to 4 decimals so near-1.0 values are not flattened to "1.00".
P1_OPEN = [
    "The LSTM autoencoder classifies this reading as {cls} with a confidence of {conf:.4f}, which {hedge} {gloss}.",
    "For this single-snapshot reading the model returns {cls} at a confidence of {conf:.4f}; the output {hedge} {gloss}.",
    "The model's predicted class is {cls} (confidence {conf:.4f}), a result that {hedge} {gloss}.",
    "Running this reading through the autoencoder yields a prediction of {cls} at {conf:.4f} confidence, an output that {hedge} {gloss}.",
]

# Paragraph 1, logit-spread sentence: characterises how decisive the call is.
# `runner` is the second-ranked class name; never quotes the raw logit value
# (small T5 cannot reliably reason over the float, and the spread is what matters).
P1_SPREAD_DECISIVE = [
    "The raw logits separate cleanly, with {cls} dominating and the remaining classes well below it.",
    "Among the six class logits, {cls} stands clearly apart from the rest, leaving little ambiguity in the decision.",
    "The logit for {cls} sits markedly above the others, so the classification is decisive.",
]
P1_SPREAD_CLOSE = [
    "The logits are closer together, with {runner} as the nearest alternative, so the decision carries some residual uncertainty.",
    "{cls} leads the logits only narrowly over {runner}, which tempers how firmly the call should be read.",
    "The margin between {cls} and {runner} in the logit vector is small, indicating a less clear-cut decision.",
]

# Paragraph 2, reconstruction sentence: ties recon_mse to "how typical".
P2_RECON_LOW = [
    "The reconstruction error is low ({mse:.3f}), meaning the autoencoder reproduced this reading well and treats it as a familiar pattern.",
    "A reconstruction MSE of {mse:.3f} is small, so the input falls comfortably within the distribution the model learned.",
    "With a reconstruction error of just {mse:.3f}, the reading is well represented by the model's learned manifold.",
]
P2_RECON_HIGH = [
    "The reconstruction error is comparatively high ({mse:.3f}), indicating the reading deviates from the patterns the autoencoder learned and warrants closer review.",
    "A reconstruction MSE of {mse:.3f} is on the larger side, suggesting this snapshot is less typical of the training distribution.",
    "The elevated reconstruction error ({mse:.3f}) shows the input reconstructs poorly, a sign the snapshot is unusual.",
]

# Paragraph 2, observation sentence: quotes 1-2 readings as NEUTRAL context.
P2_OBS = [
    "Recorded values for this snapshot include {obs}.",
    "The associated sensor readings show {obs}.",
    "Context for the reading: {obs}.",
    "Measured channels at this instant include {obs}.",
]

# Paragraph 2, closing caveat: reminds this is one snapshot (seq_len = 1).
P2_CAVEAT = [
    "As this assessment rests on a single time step rather than a trend, it should be read as a point-in-time indication.",
    "Because the model sees one snapshot at a time, the result reflects this instant only and not a temporal pattern.",
    "This is a per-snapshot judgement, so it describes the current reading rather than behaviour over time.",
]


def _band(conf: float) -> str:
    if conf >= 0.95:
        return "high"
    if conf >= 0.70:
        return "med"
    return "low"


def _runner_up(row: pd.Series) -> str:
    logits = {c: float(row[f"logit_{c}"]) for c in CLASS_NAMES}
    ordered = sorted(logits, key=lambda c: logits[c], reverse=True)
    return ordered[1] if ordered[0] == row["predicted_class"] else ordered[0]


def _margin(row: pd.Series) -> float:
    logits = sorted((float(row[f"logit_{c}"]) for c in CLASS_NAMES), reverse=True)
    return logits[0] - logits[1]


def _observations(row: pd.Series, rng: random.Random, k: int = 2) -> str:
    picks = rng.sample(OBSERVABLE, k=min(k, len(OBSERVABLE)))
    parts = [f"{label} at {fmt.format(v=float(row[col]))}" for col, fmt, label in picks]
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def make_target(row: pd.Series, rng: random.Random) -> str:
    cls = row["predicted_class"]
    conf = float(row["confidence"])
    mse = float(row["reconstruction_mse"])
    band = _band(conf)
    hedge = rng.choice(HEDGE[band])
    gloss = CLASS_GLOSS[cls]

    # Paragraph 1 — the model's decision and how decisive it is.
    p1a = rng.choice(P1_OPEN).format(cls=cls, conf=conf, hedge=hedge, gloss=gloss)
    if _margin(row) >= 4.0:
        p1b = rng.choice(P1_SPREAD_DECISIVE).format(cls=cls)
    else:
        p1b = rng.choice(P1_SPREAD_CLOSE).format(cls=cls, runner=_runner_up(row))
    para1 = f"{p1a} {p1b}"

    # Paragraph 2 — reconstruction quality, neutral observations, snapshot
    # caveat, and the operator recommendation.
    p2a = rng.choice(P2_RECON_HIGH if mse >= RECON_HIGH_THRESHOLD else P2_RECON_LOW).format(mse=mse)
    p2b = rng.choice(P2_OBS).format(obs=_observations(row, rng))
    p2c = rng.choice(P2_CAVEAT)
    p2d = RECOMMENDATION[cls]
    para2 = f"{p2a} {p2b} {p2c} {p2d}"

    return f"{para1}\n\n{para2}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="samples.csv")
    ap.add_argument("--out", default="t5_dataset.csv")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = pd.read_csv(args.inp)
    rng = random.Random(args.seed)
    df["target_text"] = df.apply(lambda r: make_target(r, rng), axis=1)

    cols = ["input_text", "target_text", "predicted_class", "true_label",
            "is_correct", "confidence", "reconstruction_mse"]
    cols = [c for c in cols if c in df.columns]
    df[cols].to_csv(args.out, index=False)
    print(f"[done] wrote {len(df)} rows -> {args.out}")
    print("\n[sample target_text]\n")
    print(df["target_text"].iloc[0])


if __name__ == "__main__":
    main()
