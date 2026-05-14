from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.dependencies import settings_dependency

router = APIRouter()


@router.get("/health", summary="Health check")
async def health_check(settings: Settings = Depends(settings_dependency)) -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "version": settings.app_version,
    }
