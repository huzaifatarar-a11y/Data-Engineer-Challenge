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
    session = FakeSession()
    repository = AsyncMock()
    publisher = AsyncMock()
    validator = MagicMock()

    publication = SimpleNamespace(
        id=uuid4(),
        publication_url="https://example.com/unit",
        author_id="author-1",
        published_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        deleted_at=None,
        metrics={},
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
        publication_url="https://example.com/unit",
        author_id="author-1",
        published_at=datetime.now(timezone.utc),
        metrics={"views": 10},
    )

    result, is_duplicate = await service.ingest(payload)

    assert result == publication
    assert is_duplicate is False
    repository.publication_exists_by_url.assert_awaited_once()
    repository.create_or_update_publication.assert_awaited_once()
    publisher.publish.assert_awaited_once_with(publication)
    validator.validate.assert_called_once()
