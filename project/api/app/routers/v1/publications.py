from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_publication_service, get_search_service
from app.repositories.publication import PublicationRepository
from app.schemas.publication import PublicationCreate, PublicationResponse, SearchResponse
from app.services.ingestion import PublicationIngestionService
from app.services.search import PublicationSearchService, build_search_response
from app.services.search.publications import MetricFilter, SearchFilters

router = APIRouter()


@router.post(
    "/publications",
    response_model=PublicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a publication",
    description=(
        "Insert a publication. If the URL already exists, update the existing one "
        "and return 200. Returns 201 on first insert."
    ),
)
async def ingest_publication(
    payload: PublicationCreate,
    response: Response,
    service: PublicationIngestionService = Depends(get_publication_service),
) -> PublicationResponse:
    publication, is_duplicate = await service.ingest(payload)
    response.status_code = (
        status.HTTP_200_OK if is_duplicate else status.HTTP_201_CREATED
    )
    return publication


@router.get(
    "/publications/search",
    response_model=SearchResponse,
    summary="Search publications",
    description=(
        "Full-text search on title, description and author_name. "
        "Supports filters on author_id, published_at, created_at, and metric values. "
        "Deleted publications are excluded."
    ),
)
async def search_publications(
    q: str | None = Query(default=None, min_length=1, description="Full-text search query"),
    author_id: str | None = Query(default=None),
    published_from: datetime | None = Query(default=None),
    published_to: datetime | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    metrics: list[str] | None = Query(
        default=None,
        description="Metric filters, e.g. views:gte:100 or engagement_rate:lte:75",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: PublicationSearchService = Depends(get_search_service),
) -> SearchResponse:
    metric_filters = _parse_metric_filters(metrics)
    filters = SearchFilters(
        author_id=author_id,
        published_from=published_from,
        published_to=published_to,
        created_from=created_from,
        created_to=created_to,
        metrics=metric_filters,
    )
    result = await service.search(query=q, filters=filters, limit=limit, offset=offset)
    return build_search_response(result, limit=limit, offset=offset)


@router.get(
    "/publications/{publication_id}",
    response_model=PublicationResponse,
    summary="Fetch a single publication by ID",
    description="Fetch a publication from the source-of-truth (PostgreSQL) by its UUID.",
)
async def get_publication(
    publication_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> PublicationResponse:
    repository = PublicationRepository(session)
    publication = await repository.get_publication_by_id(publication_id)
    if publication is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    return publication


def _parse_metric_filters(raw: list[str] | None) -> list[MetricFilter] | None:
    if not raw:
        return None

    filters: list[MetricFilter] = []
    for item in raw:
        parts = [part.strip() for part in item.split(":")]
        if len(parts) != 3 or not parts[0] or not parts[1] or not parts[2]:
            raise HTTPException(
                status_code=400,
                detail="Invalid metric filter. Use field:op:value with op in {eq,gte,lte}.",
            )

        field, op, raw_value = parts
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Metric filter value must be numeric.",
            ) from exc

        if op == "eq":
            filters.append(MetricFilter(field=field, value=value))
        elif op == "gte":
            filters.append(MetricFilter(field=field, gte=value))
        elif op == "lte":
            filters.append(MetricFilter(field=field, lte=value))
        else:
            raise HTTPException(
                status_code=400,
                detail="Metric filter op must be one of: eq, gte, lte.",
            )

    return filters
