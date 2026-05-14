from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.publication import Publication
from app.repositories.publication import PublicationRepository
from app.schemas.publication import PublicationCreate
from app.services.ingestion.publisher import IndexingEventPublisher
from app.services.ingestion.utils import calculate_engagement_rate, normalize_metrics
from app.validation import ValidationService

logger = logging.getLogger(__name__)


class PublicationIngestionService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        repository: PublicationRepository,
        validator: ValidationService,
        publisher: IndexingEventPublisher,
    ) -> None:
        self.session = session
        self.repository = repository
        self.validator = validator
        self.publisher = publisher

    async def ingest(
        self,
        payload: PublicationCreate,
        *,
        now: datetime | None = None,
    ) -> tuple[Publication, bool]:
        # Serialize to dict; keep native python objects for asyncpg
        data = payload.model_dump(exclude={"description", "media_url"})
        data["publication_url"] = str(payload.publication_url)
        data["author_id"] = str(payload.author_id)

        # Compute and store engagement_rate inside the metrics blob
        metrics = normalize_metrics(data.get("metrics"))
        engagement_rate = calculate_engagement_rate(metrics)
        if engagement_rate is not None:
            metrics["engagement_rate"] = engagement_rate
        data["metrics"] = metrics

        # Check for duplicate BEFORE validation (so the duplicate-warn rule fires)
        is_duplicate = await self.repository.publication_exists_by_url(
            data["publication_url"]
        )

        self.validator.validate(data, now=now, is_duplicate=is_duplicate)

        publication = await self.repository.create_or_update_publication(data)
        await self.publisher.publish(publication)
        await self.session.commit()

        logger.info(
            "Publication upserted",
            extra={
                "publication_id": str(publication.id),
                "publication_url": publication.publication_url,
                "author_id": publication.author_id,
                "is_duplicate": is_duplicate,
            },
        )

        return publication, is_duplicate
