"""
AI pipeline orchestration.

`run_pipeline` is the single entry point called by apps/api.
It is an async function so FastAPI can await it directly.
"""

from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../packages"))

from shared.schemas import EventIn, AnomalyResult, ExplanationResult

from ai.detector import detect
from ai.explainer import explain


async def run_pipeline(event: EventIn) -> tuple[AnomalyResult, ExplanationResult]:
    """
    Run the full anomaly detection and explanation pipeline.

    Returns:
        (AnomalyResult, ExplanationResult) tuple.
    """
    # Run CPU-bound detection in a thread pool to avoid blocking the event loop
    anomaly: AnomalyResult = await asyncio.to_thread(detect, event)
    explanation: ExplanationResult = await asyncio.to_thread(explain, event, anomaly)
    return anomaly, explanation


# ---------------------------------------------------------------------------
# Standalone smoke test — run with: python -m ai.pipeline
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    from shared.schemas import EventIn

    sample = EventIn(
        asset_id="conveyor-belt-01",
        zone_id="zone-A",
        vibration=14.2,
        temperature=82.0,
        humidity=40.0,
        pressure=1010.0,
    )

    anomaly, explanation = asyncio.run(run_pipeline(sample))
    print("=== AnomalyResult ===")
    print(json.dumps(anomaly.model_dump(mode="json"), indent=2))
    print("\n=== ExplanationResult ===")
    print(json.dumps(explanation.model_dump(mode="json"), indent=2))
