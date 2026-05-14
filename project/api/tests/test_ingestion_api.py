from __future__ import annotations

from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
@pytest.mark.postgres
@pytest.mark.integration
async def test_ingest_publication(api_client):
    payload = {
        "publication_url": "https://example.com/post-1",
        "author_id": "author-1",
        "title": "Test Post",
        "author_name": "Alice",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "summary": "Testing ingestion",
        "metrics": {"views": 100, "likes": 10, "shares": 5},
    }

    response = await api_client.post("/api/v1/publications", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["publication_url"] == payload["publication_url"]
    assert data["author_id"] == payload["author_id"]
    assert data["metrics"]["engagement_rate"] == pytest.approx(15.0)


@pytest.mark.asyncio
@pytest.mark.postgres
@pytest.mark.integration
async def test_duplicate_upsert(api_client):
    payload = {
        "publication_url": "https://example.com/post-2",
        "author_id": "author-2",
        "title": "Original",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {"views": 50, "likes": 5, "shares": 5},
    }

    first = await api_client.post("/api/v1/publications", json=payload)
    assert first.status_code == 201

    payload["title"] = "Updated"
    second = await api_client.post("/api/v1/publications", json=payload)

    assert second.status_code == 200
    assert second.json()["title"] == "Updated"


@pytest.mark.asyncio
@pytest.mark.postgres
@pytest.mark.integration
async def test_validation_failure(api_client):
    payload = {
        "publication_url": "https://example.com/post-3",
        "author_id": "author-3",
        "metrics": {"views": 10},
    }

    response = await api_client.post("/api/v1/publications", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_failed"
