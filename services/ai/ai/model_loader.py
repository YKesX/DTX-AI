from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib


REPO_ROOT = Path(__file__).resolve().parents[3]
AI_PACKAGE_ROOT = Path(__file__).resolve().parent
MODELS_ROOT = AI_PACKAGE_ROOT / "models"
REGISTRY_PATH = MODELS_ROOT / "shared" / "model_registry.json"


@dataclass
class RuntimeModel:
    key: str
    family: str
    model: Any | None
    metadata: dict[str, Any]
    scaler: Any | None
    feature_order: list[str]
    supports_tree_xai: bool
    available: bool
    reason: str = ""


_CACHE: dict[str, RuntimeModel] = {}
DEFAULT_FEATURE_COUNT = 9


def _read_json(path: Path) -> dict[str, Any] | list[Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_path(raw_path: str | None) -> Path:
    if not raw_path:
        return REPO_ROOT / ".nonexistent_model_path"

    path = Path(raw_path)
    if path.is_absolute():
        return path

    rewritten = raw_path.replace("services/ai/models/", "services/ai/ai/models/")
    candidates = [
        REPO_ROOT / raw_path,
        REPO_ROOT / rewritten,
        AI_PACKAGE_ROOT / raw_path,
        MODELS_ROOT / Path(raw_path).name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return (REPO_ROOT / rewritten).resolve()


def load_registry() -> dict[str, Any]:
    return _read_json(REGISTRY_PATH)  # type: ignore[return-value]


def _load_shared_files(registry: dict[str, Any]) -> tuple[Any | None, list[str]]:
    shared = registry.get("shared", {})
    scaler_path = _resolve_path(shared.get("scaler_path"))
    feature_order_path = _resolve_path(shared.get("feature_order_path"))

    scaler = joblib.load(scaler_path) if scaler_path.exists() else None
    feature_order: list[str] = []
    if feature_order_path.exists():
        data = _read_json(feature_order_path)
        if isinstance(data, list):
            feature_order = [str(x) for x in data]
    return scaler, feature_order


def _build_unavailable(model_key: str, family: str, reason: str, feature_order: list[str]) -> RuntimeModel:
    return RuntimeModel(
        key=model_key,
        family=family,
        model=None,
        metadata={},
        scaler=None,
        feature_order=feature_order,
        supports_tree_xai=False,
        available=False,
        reason=reason,
    )


def _load_lstm_runtime_model(model_path: Path, metadata: dict[str, Any]) -> Any:
    try:
        import torch
        import torch.nn as nn
    except Exception as exc:  # pragma: no cover - dependency optional
        raise RuntimeError(f"PyTorch unavailable: {exc}") from exc

    feature_dim = int(metadata.get("feature_count", DEFAULT_FEATURE_COUNT))
    params = metadata.get("best_params", {})
    hidden = int(params.get("hidden", 64))
    latent = int(params.get("latent", 8))

    class LSTMAutoencoder(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = nn.LSTM(feature_dim, hidden, batch_first=True)
            self.encoder_latent = nn.Linear(hidden, latent)
            self.decoder_input = nn.Linear(latent, hidden)
            self.decoder = nn.LSTM(hidden, feature_dim, batch_first=True)

        def forward(self, x):
            encoded, _ = self.encoder(x)
            latent_vec = self.encoder_latent(encoded)
            decoded_in = self.decoder_input(latent_vec)
            reconstructed, _ = self.decoder(decoded_in)
            return reconstructed

    model = LSTMAutoencoder()
    state_dict = torch.load(model_path, map_location="cpu")
    model.load_state_dict(state_dict, strict=False)
    model.eval()
    return model


def load_runtime_model(
    requested_model: str | None = None,
    strict_selection: bool = False,
) -> RuntimeModel:
    """
    Load the active runtime model from registry artifacts with graceful fallback.

        Selection precedence:
      1) explicit `requested_model` argument
      2) `DTX_ACTIVE_MODEL` environment override
      3) `active_model` in model_registry.json

    If strict_selection is False and the selected model cannot be loaded,
    this function attempts other enabled models in registry order.
    When strict_selection is True, only the selected model is attempted.
    When no model is loadable, this returns an unavailable RuntimeModel.
    """
    registry = load_registry()
    models_cfg: dict[str, Any] = registry.get("models", {})
    selected = requested_model or os.getenv("DTX_ACTIVE_MODEL") or registry.get("active_model")
    cache_key = f"{requested_model or selected or 'none'}::strict={int(strict_selection)}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    scaler, feature_order = _load_shared_files(registry)

    # Selection precedence: requested arg > env override > registry active_model.
    if strict_selection:
        order = [selected]
    else:
        order = [selected] + [k for k in models_cfg.keys() if k != selected]
    selected_error = ""
    for model_key in order:
        if not model_key:
            continue
        cfg = models_cfg.get(model_key)
        if not cfg or not cfg.get("enabled", False):
            if model_key == selected:
                selected_error = f"Model '{model_key}' is disabled or missing in registry"
            continue

        family = str(cfg.get("family", model_key))
        try:
            model_path = _resolve_path(cfg.get("path"))
            metadata_path = _resolve_path(cfg.get("metadata_path"))
            if not model_path.exists():
                raise FileNotFoundError(f"model artifact not found: {model_path}")

            metadata: dict[str, Any] = {}
            if metadata_path.exists():
                loaded = _read_json(metadata_path)
                if isinstance(loaded, dict):
                    metadata = loaded

            if family == "lstm_autoencoder_pytorch":
                model = _load_lstm_runtime_model(model_path, metadata)
            else:
                model = joblib.load(model_path)

            runtime = RuntimeModel(
                key=model_key,
                family=family,
                model=model,
                metadata=metadata,
                scaler=scaler,
                feature_order=feature_order,
                supports_tree_xai=bool(cfg.get("supports_tree_xai", False)),
                available=True,
                reason="",
            )
            _CACHE[cache_key] = runtime
            return runtime
        except Exception as exc:
            if model_key == selected:
                selected_error = f"{type(exc).__name__}: {exc}"
            continue

    unavailable = _build_unavailable(
        model_key=str(selected or "unknown"),
        family="unknown",
        reason=(
            f"No enabled model could be loaded from registry artifacts. "
            f"selected_error={selected_error or 'n/a'}"
        ),
        feature_order=feature_order,
    )
    _CACHE[cache_key] = unavailable
    return unavailable
