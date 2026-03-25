"""GET /metrics/live — lightweight in-memory replay validation metrics."""

from fastapi import APIRouter

from api.live_metrics import live_metrics

router = APIRouter()


@router.get("/live")
async def get_live_metrics():
    return live_metrics.snapshot()
