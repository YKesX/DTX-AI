"""Asset drilldown history routes."""

from fastapi import APIRouter, Query

from shared.schemas import AssetTimelineResponse

from api.database import fetch_asset_timeline

router = APIRouter()


@router.get("/{asset_id}/timeline", response_model=AssetTimelineResponse)
async def get_asset_timeline(asset_id: str, limit: int = Query(default=50, ge=1, le=200)):
    """Return recent timeline points for one asset ordered oldest to newest."""
    points = await fetch_asset_timeline(asset_id=asset_id, limit=limit)
    return AssetTimelineResponse(asset_id=asset_id, points=points)
