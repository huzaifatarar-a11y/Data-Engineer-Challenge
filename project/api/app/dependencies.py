from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import get_session
from app.elastic.client import build_elasticsearch_client
from app.repositories import PublicationRepository
from app.services.ingestion import IndexingEventPublisher, PublicationIngestionService
from app.services.search import PublicationSearchService
from app.services.stats import AuthorStatsService
from app.validation import ValidationService


@lru_cache
def get_settings() -> Settings:
    return Settings()


def settings_dependency(settings: Settings = Depends(get_settings)) -> Settings:
    return settings


async def session_dependency(session: AsyncSession = Depends(get_session)) -> AsyncSession:
    return session


def get_publication_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PublicationIngestionService:
    repository = PublicationRepository(session)
    validator = ValidationService()
    publisher = IndexingEventPublisher(session, channel=settings.indexing_channel)
    return PublicationIngestionService(
        session=session,
        repository=repository,
        validator=validator,
        publisher=publisher,
    )


def get_author_stats_service(
    session: AsyncSession = Depends(get_session),
) -> AuthorStatsService:
    repository = PublicationRepository(session)
    return AuthorStatsService(repository)


async def get_search_service(
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[PublicationSearchService]:
    client = build_elasticsearch_client(settings)
    try:
        yield PublicationSearchService(
            client,
            index_name=settings.elasticsearch_index,
            alias=settings.elasticsearch_alias,
        )
    finally:
        await client.close()
