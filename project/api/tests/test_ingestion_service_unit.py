from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.schemas.publication import PublicationCreate
from app.services.ingestion.publications import PublicationIngestionService


class FakeSession:
    @asynccontextmanager
    async def begin(self):
        yield


@pytest.mark.asyncio
async def test_ingestion_service_with_mocks():
    """Unit-test the ingestion service with fully mocked dependencies."""
    session = FakeSession()
    repository = AsyncMock()
    publisher = AsyncMock()
    validator = MagicMock()

    pub_id = uuid4()
    publication = SimpleNamespace(
        id=pub_id,
        publication_url="https://www.instagram.com/p/unittest001/",
        author_id="11111111-1111-1111-1111-111111111111",
        title="Unit Test",
        author_name="Alice",
        published_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        deleted_at=None,
        metrics={"views": 100, "follower_count_at_post": 1000},
        summary=None,
        platform=None,
    )

    repository.publication_exists_by_url.return_value = False
    repository.create_or_update_publication.return_value = publication

    service = PublicationIngestionService(
        session=session,
        repository=repository,
        validator=validator,
        publisher=publisher,
    )

    payload = PublicationCreate(
        publication_url="https://www.instagram.com/p/unittest001/",
        author_id="11111111-1111-1111-1111-111111111111",
        published_at=datetime.now(timezone.utc),
        metrics={"views": 100, "follower_count_at_post": 1000},
    )

    result, is_duplicate = await service.ingest(payload)

    assert result == publication
    assert is_duplicate is False
    repository.publication_exists_by_url.assert_awaited_once()
    repository.create_or_update_publication.assert_awaited_once()
    publisher.publish.assert_awaited_once_with(publication)
    validator.validate.assert_called_once()


@pytest.mark.asyncio
async def test_ingestion_service_duplicate():
    """When the URL already exists, is_duplicate should be True."""
    session = FakeSession()
    repository = AsyncMock()
    publisher = AsyncMock()
    validator = MagicMock()

    pub_id = uuid4()
    publication = SimpleNamespace(
        id=pub_id,
        publication_url="https://www.instagram.com/p/unittest002/",
        author_id="22222222-2222-2222-2222-222222222222",
        title="Dup",
        author_name=None,
        published_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        deleted_at=None,
        metrics={},
        summary=None,
        platform=None,
    )

    repository.publication_exists_by_url.return_value = True
    repository.create_or_update_publication.return_value = publication

    service = PublicationIngestionService(
        session=session,
        repository=repository,
        validator=validator,
        publisher=publisher,
    )

    payload = PublicationCreate(
        publication_url="https://www.instagram.com/p/unittest002/",
        author_id="22222222-2222-2222-2222-222222222222",
        published_at=datetime.now(timezone.utc),
    )

    _, is_duplicate = await service.ingest(payload)
    assert is_duplicate is True
