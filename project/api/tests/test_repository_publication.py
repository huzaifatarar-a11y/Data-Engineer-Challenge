from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import update

from app.models.publication import Publication
from app.repositories.publication import PublicationRepository


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_repository_upsert(db_session):
    repository = PublicationRepository(db_session)
    now = datetime.now(timezone.utc)

    payload = {
        "publication_url": "https://example.com/repo-1",
        "author_id": "author-1",
        "title": "Original",
        "published_at": now,
        "metrics": {},
    }

    created = await repository.create_or_update_publication(payload)
    assert created.title == "Original"

    payload["title"] = "Updated"
    updated = await repository.create_or_update_publication(payload)

    assert updated.title == "Updated"


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_repository_search_excludes_deleted(db_session):
    repository = PublicationRepository(db_session)
    now = datetime.now(timezone.utc)

    payload = {
        "publication_url": "https://example.com/repo-2",
        "author_id": "author-2",
        "title": "Active",
        "published_at": now,
        "metrics": {},
    }

    publication = await repository.create_or_update_publication(payload)

    await db_session.execute(
        update(Publication)
        .where(Publication.id == publication.id)
        .values(deleted_at=now)
    )
    await db_session.commit()

    items, total = await repository.search_publications()
    assert total == 0
    assert items == []
