"""
Isaac Sim scene helpers.

This module is only imported when ISAAC_SIM_ENABLED=true and Isaac Sim
is installed.  Keep all Isaac Sim SDK imports inside functions so the
rest of the codebase can still import packages/shared and services/ai
without Isaac Sim present.

TODO: Replace the stub implementations below with real USD/Omniverse calls.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


def update_asset_status(
    asset_id: str,
    zone_id: str,
    status: str,
    severity: str,
    label: str = "",
) -> None:
    """
    Update the visual status of a warehouse asset in the Isaac Sim stage.

    MVP stub — logs the intended update.
    TODO: Open the USD stage, find the prim by asset_id/zone_id, and set
          a custom attribute or change the material to reflect the status.

    Example Isaac Sim calls (uncomment when Isaac Sim is available):

        from omni.isaac.core import World
        from pxr import Usd, UsdGeom

        world = World.instance()
        stage = world.stage
        prim_path = f"/World/{zone_id}/{asset_id}"
        prim = stage.GetPrimAtPath(prim_path)
        if prim.IsValid():
            attr = prim.CreateAttribute("dtxai:status", Sdf.ValueTypeNames.String)
            attr.Set(status)
    """
    _logger.info(
        "[STUB] update_asset_status | asset=%s zone=%s status=%s severity=%s label=%s",
        asset_id, zone_id, status, severity, label,
    )


def reset_scene() -> None:
    """
    Reset all asset statuses to NORMAL.
    Called at the start of a new demo session.
    TODO: Implement USD reset logic.
    """
    _logger.info("[STUB] reset_scene — all assets reset to NORMAL")
