"""
Isaac Sim adapter — public entry point.

`notify(update)` is called by apps/api whenever an anomaly is confirmed.

When ISAAC_SIM_ENABLED=false (default for local dev) or when Isaac Sim
is not installed, the function logs the update and returns immediately.
"""

from __future__ import annotations

import logging
import os
import sys

_logger = logging.getLogger(__name__)

# Runtime flag — set ISAAC_SIM_ENABLED=true in .env to activate
_ENABLED = os.getenv("ISAAC_SIM_ENABLED", "false").lower() == "true"

# Add Isaac Sim Python path if configured
_ISAAC_SIM_PATH = os.getenv("ISAAC_SIM_PATH", "")
if _ISAAC_SIM_PATH and _ISAAC_SIM_PATH not in sys.path:
    sys.path.insert(0, _ISAAC_SIM_PATH)


def notify(update) -> None:
    """
    Receive a TwinUpdate and apply it to the Isaac Sim digital-twin scene.

    Args:
        update: TwinUpdate schema object from packages/shared.
    """
    _logger.info(
        "TwinUpdate received | asset=%s zone=%s status=%s severity=%s",
        update.asset_id,
        update.zone_id,
        update.new_status.value,
        update.severity.value,
    )

    if not _ENABLED:
        _logger.debug("Isaac Sim disabled (ISAAC_SIM_ENABLED=false) — skipping scene update.")
        return

    try:
        from sim.scene import update_asset_status  # type: ignore[import]
        update_asset_status(
            asset_id=update.asset_id,
            zone_id=update.zone_id,
            status=update.new_status.value,
            severity=update.severity.value,
            label=update.label,
        )
    except ImportError:
        _logger.warning("Isaac Sim scene module unavailable — install Isaac Sim to enable.")
    except Exception as exc:
        _logger.error("Failed to update Isaac Sim scene: %s", exc)
