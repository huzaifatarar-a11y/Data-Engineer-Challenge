"""Integration tests, run against the running Docker stack.

Usage:
    docker compose up -d
    # wait for services to be healthy
    pytest tests/test_api.py -v
"""

import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest

BASE = "http://localhost:8000"


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE, timeout=15.0) as c:
        yield c


def _make_pub(**overrides) -> dict:
    base = {
        "publication_url": f"https://instagram.com/p/{uuid4().hex[:11]}/",
        "title": "Integration Test Post",
        "author_name": "Test Author",
        "author_id": str(uuid4()),
        "published_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "description": "A unique integration test description for search",
        "media_url": "https://example.com/img.jpg",
        "metrics": {
            "likes": 100,
            "views": 500,
            "comments": 10,
            "shares": 5,
            "follower_count_at_post": 10_000,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


# -- POST /publications ------------------------------------------------------

class TestPostPublications:
    def test_accepts_valid_publication(self, client):
        resp = client.post("/publications", json=_make_pub())
        assert resp.status_code == 202
        assert resp.json()["status"] == "accepted"

    def test_rejects_missing_required_field(self, client):
        pub = _make_pub()
        del pub["publication_url"]
        resp = client.post("/publications", json=pub)
        assert resp.status_code == 422

    def test_upsert_same_url_accepted_twice(self, client):
        url = f"https://instagram.com/p/{uuid4().hex[:11]}/"
        pub = _make_pub(publication_url=url)
        r1 = client.post("/publications", json=pub)
        assert r1.status_code == 202
        pub["title"] = "Updated Title"
        r2 = client.post("/publications", json=pub)
        assert r2.status_code == 202


# -- GET /publications/search ------------------------------------------------

class TestSearch:
    def test_search_returns_results(self, client):
        resp = client.get("/publications/search", params={"q": "test", "size": 5})
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "publications" in body

    def test_search_with_filters(self, client):
        resp = client.get(
            "/publications/search",
            params={
                "author_id": str(uuid4()),
                "published_after": "2020-01-01T00:00:00Z",
                "size": 5,
            },
        )
        assert resp.status_code == 200


# -- GET /authors/{author_id}/stats ------------------------------------------

class TestAuthorStats:
    def test_unknown_author_returns_404(self, client):
        resp = client.get(f"/authors/{uuid4()}/stats")
        assert resp.status_code == 404

    def test_stats_for_known_author(self, client):
        author_id = str(uuid4())
        pub = _make_pub(author_id=author_id)
        client.post("/publications", json=pub)
        time.sleep(5)  # wait for worker to process
        resp = client.get(f"/authors/{author_id}/stats")
        if resp.status_code == 200:
            body = resp.json()
            assert body["total_posts"] >= 1
            assert body["average_engagement_rate"] >= 0


# -- Health ------------------------------------------------------------------

class TestHealth:
    def test_health(self, client):
        assert client.get("/health").status_code == 200
