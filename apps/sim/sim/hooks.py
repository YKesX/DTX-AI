"""
Isaac Sim simulation lifecycle hooks.

Register these callbacks with the Omniverse SimulationApp or
an Isaac Sim Extension to drive the digital-twin during a simulation run.

TODO: Wire these into an actual Isaac Sim Extension when Isaac Sim is installed.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


def on_simulation_start() -> None:
    """Called once when the Isaac Sim simulation starts."""
    _logger.info("[SIM HOOK] Simulation started — DTX-AI digital twin active.")
    # TODO: Load warehouse USD scene
    # TODO: Subscribe to physics callbacks


def on_simulation_step(dt: float) -> None:
    """
    Called every physics step.

    Args:
        dt: Time delta since the last step in seconds.
    """
    # TODO: Poll for pending TwinUpdate messages from a queue and apply them
    pass


def on_simulation_stop() -> None:
    """Called when the simulation stops."""
    _logger.info("[SIM HOOK] Simulation stopped.")
    # TODO: Persist final asset states
