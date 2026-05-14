from fastapi import APIRouter

from app.routers.v1.authors import router as authors_router
from app.routers.v1.health import router as health_router
from app.routers.v1.publications import router as publications_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router, tags=["health"])
api_v1_router.include_router(publications_router, tags=["publications"])
api_v1_router.include_router(authors_router, tags=["authors"])
