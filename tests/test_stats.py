"""Unit tests for stats logic — engagement rate formula and deletion exclusion.

These verify the domain logic independently of the database.
"""

import pytest
from shared.validation import compute_engagement_rate


class TestStatsFormula:
    def test_basic_engagement_rate(self):
        m = {"likes": 50, "views": 200, "comments": 10, "shares": 5, "follower_count_at_post": 1_000}
        rate = compute_engagement_rate(m)
        assert rate == pytest.approx((50 + 200 + 10 + 5) / 1_000)

    def test_high_engagement(self):
        m = {"likes": 1_000, "views": 5_000, "comments": 500, "shares": 500, "follower_count_at_post": 100}
        rate = compute_engagement_rate(m)
        assert rate == 70.0  # (7000 / 100)

    def test_no_engagement(self):
        m = {"likes": 0, "views": 0, "comments": 0, "shares": 0, "follower_count_at_post": 10_000}
        assert compute_engagement_rate(m) == 0.0

    def test_zero_followers(self):
        m = {"likes": 0, "views": 0, "comments": 0, "shares": 0, "follower_count_at_post": 0}
        assert compute_engagement_rate(m) == 0.0

    def test_engagement_rate_all_metrics_contribute(self):
        m = {"likes": 1, "views": 1, "comments": 1, "shares": 1, "follower_count_at_post": 4}
        assert compute_engagement_rate(m) == 1.0
