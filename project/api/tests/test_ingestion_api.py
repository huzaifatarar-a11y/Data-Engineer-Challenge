from __future__ import annotations

from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
@pytest.mark.postgres
@pytest.mark.integration
async def test_ingest_publication(api_client):
    """
    First POST → 201. Engagement rate = (likes+views+comments+shares)/follower_count.
    With likes=10, views=100, shares=5, comments=0, follower_count=1000:
    rate = (10+100+0+5)/1000 = 0.115
    """
    payload = {
        "publication_url": "https://www.instagram.com/p/testpost001/",
        "author_id": "11111111-1111-1111-1111-111111111111",
        "title": "Test Post",
        "author_name": "Alice",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "description": "Testing ingestion",
        "metrics": {
            "views": 100,
            "likes": 10,
            "shares": 5,
            "comments": 0,
            "follower_count_at_post": 1000,
        },
    }

    response = await api_client.post("/api/v1/publications", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["publication_url"] == payload["publication_url"]
    assert data["author_id"] == payload["author_id"]
    assert data["summary"] == "Testing ingestion"
    # engagement_rate = (10+100+0+5)/1000 = 0.115
    assert data["metrics"]["engagement_rate"] == pytest.approx(0.115, rel=1e-3)


@pytest.mark.asyncio
@pytest.mark.postgres
@pytest.mark.integration
async def test_duplicate_upsert(api_client):
    """Second POST to same URL → 200 and updated title."""
    payload = {
        "publication_url": "https://www.instagram.com/p/testpost002/",
        "author_id": "22222222-2222-2222-2222-222222222222",
        "title": "Original",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {"views": 50, "likes": 5, "shares": 5, "follower_count_at_post": 100},
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
async def test_get_publication_by_id(api_client):
    """POST then GET by ID → same record."""
    payload = {
        "publication_url": "https://www.instagram.com/p/testpost003/",
        "author_id": "33333333-3333-3333-3333-333333333333",
        "title": "Fetch Me",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {"views": 10, "follower_count_at_post": 100},
    }

    post_resp = await api_client.post("/api/v1/publications", json=payload)
    assert post_resp.status_code == 201
    pub_id = post_resp.json()["id"]

    get_resp = await api_client.get(f"/api/v1/publications/{pub_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == pub_id


@pytest.mark.asyncio
@pytest.mark.postgres
@pytest.mark.integration
async def test_get_publication_not_found(api_client):
    """GET with unknown UUID → 404."""
    response = await api_client.get(
        "/api/v1/publications/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.postgres
@pytest.mark.integration
async def test_validation_failure_missing_published_at(api_client):
    """Missing published_at → 422 with validation_failed error."""
    payload = {
        "publication_url": "https://www.instagram.com/p/testpost004/",
        "author_id": "44444444-4444-4444-4444-444444444444",
        "metrics": {"views": 10},
    }

    response = await api_client.post("/api/v1/publications", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_failed"
    assert any(i["code"] == "published_at_required" for i in body["issues"])
