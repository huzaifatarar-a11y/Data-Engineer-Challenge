from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest


@pytest.mark.asyncio
@pytest.mark.elasticsearch
@pytest.mark.integration
async def test_search_publications(api_client_with_es, es_client, es_index):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "publication_url": "https://example.com/search-1",
        "author_id": "author-1",
        "author_name": "Alice",
        "title": "Fast API Guide",
        "description": "fast api search indexing",
        "platform": "blog",
        "published_at": now,
        "created_at": now,
        "updated_at": now,
        "metrics": {"views": 100},
    }
    deleted_doc = {
        "id": str(uuid.uuid4()),
        "publication_url": "https://example.com/search-2",
        "author_id": "author-1",
        "author_name": "Alice",
        "title": "Deleted",
        "description": "fast api search indexing",
        "platform": "blog",
        "published_at": now,
        "created_at": now,
        "updated_at": now,
        "deleted_at": now,
        "metrics": {"views": 100},
    }

    await es_client.index(
        index=es_index["alias"],
        id=doc["id"],
        document=doc,
        refresh="wait_for",
    )
    await es_client.index(
        index=es_index["alias"],
        id=deleted_doc["id"],
        document=deleted_doc,
        refresh="wait_for",
    )

    response = await api_client_with_es.get(
        "/api/v1/publications/search",
        params={"q": "search", "limit": 10},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["publication_url"] == doc["publication_url"]
    assert data["items"][0]["summary"] == doc["description"]


@pytest.mark.asyncio
@pytest.mark.elasticsearch
@pytest.mark.integration
async def test_search_filters_metrics(api_client_with_es, es_client, es_index):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "publication_url": "https://example.com/search-3",
        "author_id": "author-2",
        "author_name": "Bob",
        "title": "Metrics",
        "description": "metrics filtering",
        "published_at": now,
        "created_at": now,
        "updated_at": now,
        "metrics": {"views": 75},
    }

    await es_client.index(
        index=es_index["alias"],
        id=doc["id"],
        document=doc,
        refresh="wait_for",
    )

    response = await api_client_with_es.get(
        "/api/v1/publications/search",
        params=[("metrics", "views:gte:50")],
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["publication_url"] == doc["publication_url"]
