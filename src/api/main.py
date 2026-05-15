"""Publications API accepts writes (via Kafka) and serves reads from Postgres / OpenSearch."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.database import get_session
from shared.kafka_utils import create_producer
from shared.models import (
    AuthorStats,
    Publication,
    PublicationIn,
    PublicationOut,
    SearchResult,
)
from shared.search import ensure_index, get_opensearch_client, search_publications

logger = logging.getLogger(__name__)

# -- Prometheus metrics -------------------------------------------------------
REQUEST_COUNT = Counter("api_requests_total", "Total requests", ["endpoint", "status"])
REQUEST_DURATION = Histogram("api_request_seconds", "Request latency", ["endpoint"])

# -- Globals set during lifespan ----------------------------------------------
kafka_producer = None
os_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global kafka_producer, os_client
    kafka_producer = await create_producer()
    os_client = get_opensearch_client()
    try:
        await ensure_index(os_client)
    except Exception:
        logger.warning("OpenSearch not ready yet, index will be created by worker")
    logger.info("API service started")
    yield
    await kafka_producer.stop()
    await os_client.close()
    logger.info("API service stopped")


app = FastAPI(
    title="Publications API",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# POST /publications  produce to Kafka (async ingestion)
# ---------------------------------------------------------------------------
@app.post("/publications", status_code=202)
async def create_publication(publication: PublicationIn):
    with REQUEST_DURATION.labels(endpoint="post_publications").time():
        try:
            payload = publication.model_dump(mode="json")
            await kafka_producer.send_and_wait(settings.kafka_topic, value=payload)
            REQUEST_COUNT.labels(endpoint="post_publications", status="accepted").inc()
            return {"status": "accepted"}
        except Exception as e:
            REQUEST_COUNT.labels(endpoint="post_publications", status="error").inc()
            logger.error("Failed to produce to Kafka: %s", e)
            raise HTTPException(status_code=503, detail="Ingestion unavailable")


# ---------------------------------------------------------------------------
# GET /publications/search  full-text search via OpenSearch
# ---------------------------------------------------------------------------
@app.get("/publications/search", response_model=SearchResult)
async def search(
    q: Optional[str] = Query(None, description="Full-text search query"),
    author_id: Optional[str] = Query(None),
    published_after: Optional[str] = Query(None, description="ISO-8601"),
    published_before: Optional[str] = Query(None, description="ISO-8601"),
    created_after: Optional[str] = Query(None, description="ISO-8601"),
    created_before: Optional[str] = Query(None, description="ISO-8601"),
    min_engagement_rate: Optional[float] = Query(None, ge=0),
    max_engagement_rate: Optional[float] = Query(None, le=100),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    with REQUEST_DURATION.labels(endpoint="search").time():
        try:
            result = await search_publications(
                os_client,
                query=q,
                author_id=author_id,
                published_after=published_after,
                published_before=published_before,
                created_after=created_after,
                created_before=created_before,
                min_engagement_rate=min_engagement_rate,
                max_engagement_rate=max_engagement_rate,
                page=page,
                size=size,
            )
            REQUEST_COUNT.labels(endpoint="search", status="ok").inc()
            return result
        except Exception as e:
            REQUEST_COUNT.labels(endpoint="search", status="error").inc()
            logger.exception("Search failed: %s", e)
            raise HTTPException(status_code=500, detail="Search unavailable")


# ---------------------------------------------------------------------------
# GET /publications/{publication_id}  single record from Postgres
# ---------------------------------------------------------------------------
@app.get("/publications/{publication_id}", response_model=PublicationOut)
async def get_publication(
    publication_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    with REQUEST_DURATION.labels(endpoint="get_publication").time():
        result = await session.execute(
            select(Publication).where(Publication.publication_id == publication_id)
        )
        pub = result.scalar_one_or_none()
        if pub is None:
            raise HTTPException(status_code=404, detail="Publication not found")
        REQUEST_COUNT.labels(endpoint="get_publication", status="ok").inc()
        return PublicationOut.model_validate(pub)


# ---------------------------------------------------------------------------
# GET /authors/{author_id}/stats
# ---------------------------------------------------------------------------
@app.get("/authors/{author_id}/stats", response_model=AuthorStats)
async def get_author_stats(
    author_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    with REQUEST_DURATION.labels(endpoint="author_stats").time():
        result = await session.execute(
            select(
                func.count(Publication.publication_id).label("total_posts"),
                func.avg(Publication.engagement_rate).label("avg_rate"),
            ).where(
                Publication.author_id == author_id,
                Publication.deleted_at.is_(None),
            )
        )
        row = result.one()
        total = row.total_posts or 0
        avg_rate = float(row.avg_rate) if row.avg_rate is not None else 0.0

        if total == 0:
            raise HTTPException(
                status_code=404,
                detail="Author not found or has no active publications",
            )

        REQUEST_COUNT.labels(endpoint="author_stats", status="ok").inc()
        return AuthorStats(
            author_id=author_id,
            total_posts=total,
            average_engagement_rate=round(avg_rate, 6),
        )


# ---------------------------------------------------------------------------
# Operational endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
