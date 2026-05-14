from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.publication import Publication


@pytest.mark.asyncio
@pytest.mark.postgres
@pytest.mark.integration
async def test_author_stats(api_client, db_session):
    now = datetime.now(timezone.utc)
    author_id = "author-42"

    pub1 = Publication(
        publication_url="https://example.com/stats-1",
        author_id=author_id,
        published_at=now,
        metrics={
            "likes": 10,
            "views": 100,
            "comments": 5,
            "shares": 5,
            "follower_count_at_post": 1000,
        },
    )
    pub2 = Publication(
        publication_url="https://example.com/stats-2",
        author_id=author_id,
        published_at=now,
        metrics={
            "likes": 20,
            "views": 200,
            "comments": 10,
            "shares": 10,
            "follower_count_at_post": 2000,
        },
    )
    pub_deleted = Publication(
        publication_url="https://example.com/stats-3",
        author_id=author_id,
        published_at=now,
        deleted_at=now,
        metrics={
            "likes": 100,
            "views": 100,
            "comments": 100,
            "shares": 100,
            "follower_count_at_post": 100,
        },
    )

    db_session.add_all([pub1, pub2, pub_deleted])
    await db_session.commit()

    response = await api_client.get(f"/api/v1/authors/{author_id}/stats")

    assert response.status_code == 200
    data = response.json()

    expected_avg = ((10 + 100 + 5 + 5) / 1000 + (20 + 200 + 10 + 10) / 2000) / 2
    assert data["author_id"] == author_id
    assert data["total_posts"] == 2
    assert data["average_engagement_rate"] == pytest.approx(expected_avg)


@pytest.mark.asyncio
@pytest.mark.postgres
@pytest.mark.integration
async def test_author_stats_not_found(api_client):
    response = await api_client.get("/api/v1/authors/missing/stats")

    assert response.status_code == 404
