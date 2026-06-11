"""T5 natural-language explainer for the LSTM-AE runtime.

The LSTM autoencoder cannot be explained with SHAP (it is not a tree model), so
its predictions are turned into prose by a fine-tuned T5 model. This module
loads that model once, lazily, and converts the signals the detector already
recorded on ``event.metadata`` into a two-paragraph explanation.

The input string is built with ``build_input_text`` imported from
``build_t5_samples``, the single source of truth for the format, so the text
seen at inference is byte-for-byte the text the model was trained on.

Every entry point fails soft: if the model directory is absent (the weights are
distributed out-of-band, not committed to the repo), if PyTorch/transformers is
unavailable, or if anything raises, ``generate_explanation`` returns ``None`` and
the caller keeps its existing behaviour. Importing this module never has side
effects beyond defining functions.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from shared.schemas import AnomalyResult, EventIn

# build_input_text lives in services/ai/build_t5_samples.py — the same builder
# used to create the training data. Importing it here guarantees train/inference
# format parity.
_SERVICES_AI_ROOT = Path(__file__).resolve().parents[1]
if str(_SERVICES_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVICES_AI_ROOT))

try:
    from build_t5_samples import build_input_text  # noqa: E402
    from preprocessing import FEATURES, CLASS_NAMES, INT_TO_LABEL  # noqa: E402
    _IMPORTS_OK = True
except Exception:
    _IMPORTS_OK = False


# Model directory. The weights are large and live outside git; drop the
# fine-tuned model here (or point DTX_T5_MODEL_DIR elsewhere). When the
# directory is missing, this module stays dormant and the caller falls back.
_DEFAULT_MODEL_DIR = Path(__file__).resolve().parent / "models" / "t5_explainer"
MODEL_DIR = Path(os.getenv("DTX_T5_MODEL_DIR", str(_DEFAULT_MODEL_DIR)))

# Generation length cap — matches the training target length.
_MAX_NEW_TOKENS = 256

# Lazily-initialised singletons. None = not loaded yet; False = load failed.
_tokenizer: Any = None
_model: Any = None
_load_attempted = False
_load_ok = False


def _load() -> bool:
    """Load tokenizer + model once. Returns True if usable, False otherwise."""
    global _tokenizer, _model, _load_attempted, _load_ok
    if _load_attempted:
        return _load_ok
    _load_attempted = True

    if not _IMPORTS_OK or not MODEL_DIR.exists():
        _load_ok = False
        return False

    try:
        import torch  # noqa: F401
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

        _tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
        _model = AutoModelForSeq2SeqLM.from_pretrained(str(MODEL_DIR))
        _model.eval()
        _load_ok = True
    except Exception:
        _tokenizer = None
        _model = None
        _load_ok = False
    return _load_ok


def _signals_from_metadata(event: EventIn) -> dict[str, Any] | None:
    """Pull the LSTM-AE signals the detector recorded onto event.metadata.

    Returns a dict ready for build_input_text, or None if the expected signals
    are not present (e.g. a non-LSTM runtime produced this event).
    """
    md = event.metadata if isinstance(event.metadata, dict) else {}
    if "lstm_raw_logits" not in md or "lstm_predicted_class" not in md:
        return None

    raw = md["lstm_raw_logits"]  # {"0": .., ..., "5": ..} keyed by class index
    try:
        logits = {INT_TO_LABEL[int(i)]: float(v) for i, v in raw.items()}
    except Exception:
        return None
    if set(logits) != set(CLASS_NAMES):
        return None

    pred_idx = md["lstm_predicted_class"]
    predicted_class = (
        INT_TO_LABEL.get(int(pred_idx)) if isinstance(pred_idx, (int, float))
        else str(pred_idx)
    )
    if predicted_class not in CLASS_NAMES:
        return None

    features = {
        name: float(value) if (value := getattr(event, name, None)) is not None else 0.0
        for name in FEATURES
    }

    return {
        "predicted_class": predicted_class,
        "confidence": float(md.get("lstm_class_confidence", 0.0)),
        "reconstruction_mse": float(md.get("lstm_reconstruction_mse", 0.0)),
        "logits": logits,
        "features": features,
    }


def generate_explanation(event: EventIn, anomaly: AnomalyResult) -> str | None:
    """Return a T5 explanation string, or None if T5 is unavailable/unusable.

    Never raises: any failure yields None so the caller can fall back.
    """
    try:
        if not _load():
            return None
        sig = _signals_from_metadata(event)
        if sig is None:
            return None

        input_text = build_input_text(
            predicted_class=sig["predicted_class"],
            confidence=sig["confidence"],
            reconstruction_mse=sig["reconstruction_mse"],
            logits=sig["logits"],
            features=sig["features"],
        )

        import torch

        enc = _tokenizer(
            input_text, return_tensors="pt", truncation=True, max_length=512,
        )
        with torch.no_grad():
            out = _model.generate(**enc, max_new_tokens=_MAX_NEW_TOKENS, num_beams=4)
        text = _tokenizer.decode(out[0], skip_special_tokens=True).strip()
        return text or None
    except Exception:
        return None
