"""Integration tests for search — requires running Docker stack.

Usage:
    docker compose up -d
    pytest tests/test_search.py -v
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
        "title": "Searchable Post Title",
        "author_name": "Searchable Author",
        "author_id": str(uuid4()),
        "published_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "description": "uniquesearchterm742 visible in full text search",
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


class TestSearchFilters:
    def test_deleted_publications_excluded(self, client):
        """POST a pub with deleted_at set; it should not appear in search."""
        pub = _make_pub(
            description="deletedmarker999 should not appear",
            deleted_at=datetime.now(timezone.utc).isoformat(),
        )
        client.post("/publications", json=pub)
        time.sleep(5)
        resp = client.get("/publications/search", params={"q": "deletedmarker999"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_search_by_author_id(self, client):
        author_id = str(uuid4())
        pub = _make_pub(author_id=author_id, description="authorfiltertest123")
        client.post("/publications", json=pub)
        time.sleep(5)
        resp = client.get("/publications/search", params={"author_id": author_id})
        assert resp.status_code == 200

    def test_search_date_range(self, client):
        resp = client.get(
            "/publications/search",
            params={
                "published_after": "2020-01-01T00:00:00Z",
                "published_before": "2099-12-31T23:59:59Z",
                "size": 5,
            },
        )
        assert resp.status_code == 200

    def test_search_engagement_rate_filter(self, client):
        resp = client.get(
            "/publications/search",
            params={"min_engagement_rate": 0, "max_engagement_rate": 1, "size": 5},
        )
        assert resp.status_code == 200
