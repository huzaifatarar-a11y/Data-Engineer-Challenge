from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_author_stats_service
from app.schemas.publication import AuthorStats
from app.services.stats import AuthorStatsService

router = APIRouter()


@router.get(
    "/authors/{author_id}/stats",
    response_model=AuthorStats,
    summary="Author statistics",
)
async def author_stats(
    author_id: str,
    service: AuthorStatsService = Depends(get_author_stats_service),
) -> AuthorStats:
    stats = await service.get_stats(author_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="Author not found")
    return stats
