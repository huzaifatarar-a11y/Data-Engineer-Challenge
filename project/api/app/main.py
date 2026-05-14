from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import Settings
from app.core.logging import configure_logging
from app.dependencies import get_settings
from app.routers import api_router
from app.validation import IngestionValidationError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: run DB migrations and ensure ES index + alias exist.
    Shutdown: nothing extra needed (connections are per-request).
    """
    settings: Settings = get_settings()

    # ── 1. Ensure Elasticsearch index + alias exist ─────────────────────────
    try:
        from app.elastic.client import build_elasticsearch_client
        from app.elastic.index import IndexManager

        es_client = build_elasticsearch_client(settings)
        try:
            manager = IndexManager(
                es_client,
                index_name=settings.elasticsearch_index,
                alias=settings.elasticsearch_alias,
            )
            await manager.ensure_index()
            logger.info(
                "Elasticsearch index ready",
                extra={"index": settings.elasticsearch_index, "alias": settings.elasticsearch_alias},
            )
        finally:
            await es_client.close()
    except Exception:
        logger.exception("Failed to ensure Elasticsearch index — search may not work")

    yield
    # Shutdown (nothing to do — sessions and ES clients are request-scoped)


def create_app() -> FastAPI:
    settings: Settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "type": "http_error"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "details": exc.errors()},
        )

    @app.exception_handler(IngestionValidationError)
    async def ingestion_validation_handler(_: Request, exc: IngestionValidationError):
        return JSONResponse(
            status_code=422,
            content=exc.to_dict(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception):
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error"},
        )

    app.include_router(api_router)

    return app


app = create_app()
