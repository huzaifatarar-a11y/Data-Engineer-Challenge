"""Unit tests for data-quality validation — no external dependencies."""

import pytest
from datetime import datetime, timedelta, timezone

from shared.validation import (
    ValidationError,
    compute_engagement_rate,
    validate_publication,
)


def _pub(**overrides) -> dict:
    base = {
        "publication_url": "https://instagram.com/p/abc123/",
        "title": "Test Post",
        "author_name": "Test Author",
        "author_id": "12345678-1234-1234-1234-123456789012",
        "published_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "description": "A test description",
        "media_url": "https://example.com/image.jpg",
        "metrics": {
            "likes": 100,
            "views": 500,
            "comments": 10,
            "shares": 5,
            "follower_count_at_post": 10_000,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
        "deleted_at": None,
    }
    base.update(overrides)
    return base


# -- Engagement rate calculation ---------------------------------------------

class TestEngagementRate:
    def test_normal(self):
        m = {"likes": 100, "views": 500, "comments": 10, "shares": 5, "follower_count_at_post": 10_000}
        assert compute_engagement_rate(m) == pytest.approx(0.0615)

    def test_zero_followers_zero_engagement(self):
        m = {"likes": 0, "views": 0, "comments": 0, "shares": 0, "follower_count_at_post": 0}
        assert compute_engagement_rate(m) == 0.0

    def test_zero_followers_nonzero_engagement(self):
        m = {"likes": 100, "views": 0, "comments": 0, "shares": 0, "follower_count_at_post": 0}
        assert compute_engagement_rate(m) == 0.0


# -- Hard-fail checks -------------------------------------------------------

class TestHardFails:
    def test_null_publication_url(self):
        with pytest.raises(ValidationError, match="publication_url"):
            validate_publication(_pub(publication_url=None))

    def test_null_author_id(self):
        with pytest.raises(ValidationError, match="author_id"):
            validate_publication(_pub(author_id=None))

    def test_null_published_at(self):
        with pytest.raises(ValidationError, match="published_at"):
            validate_publication(_pub(published_at=None))

    def test_future_published_at(self):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        with pytest.raises(ValidationError, match="future"):
            validate_publication(_pub(published_at=future))

    def test_engagement_rate_over_100(self):
        metrics = {
            "likes": 10_000_000,
            "views": 10_000_000,
            "comments": 500_000,
            "shares": 100_000,
            "follower_count_at_post": 1,
        }
        with pytest.raises(ValidationError, match="[Ee]ngagement rate"):
            validate_publication(_pub(metrics=metrics))


# -- Warn-only checks -------------------------------------------------------

class TestWarnings:
    def test_old_published_at_warns(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        warnings, rate = validate_publication(_pub(published_at=old))
        assert len(warnings) == 1
        assert "older than 24" in warnings[0].message

    def test_recent_published_at_no_warning(self):
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        warnings, rate = validate_publication(_pub(published_at=recent))
        assert warnings == []


# -- Happy path --------------------------------------------------------------

class TestValid:
    def test_valid_publication(self):
        warnings, rate = validate_publication(_pub())
        assert 0 <= rate <= 100

    def test_engagement_rate_matches_formula(self):
        m = {"likes": 200, "views": 800, "comments": 50, "shares": 50, "follower_count_at_post": 1_000}
        _, rate = validate_publication(_pub(metrics=m))
        expected = (200 + 800 + 50 + 50) / 1_000
        assert rate == pytest.approx(expected)
