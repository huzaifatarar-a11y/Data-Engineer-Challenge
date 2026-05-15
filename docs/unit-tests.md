# Unit Tests Overview

This document explains each unit test and what behavior it verifies. These tests run without external services or Docker.

## tests/test_validation.py

Focus: data-quality validation and engagement-rate computation logic in shared.validation.

- TestEngagementRate.test_normal
  - Verifies the engagement rate formula on a typical metrics payload.
- TestEngagementRate.test_zero_followers_zero_engagement
  - Ensures zero followers and zero engagement results in 0.0.
- TestEngagementRate.test_zero_followers_nonzero_engagement
  - Ensures zero followers does not cause division errors; returns 0.0 even with engagement.

- TestHardFails.test_null_publication_url
  - Missing publication_url must raise a hard ValidationError.
- TestHardFails.test_null_author_id
  - Missing author_id must raise a hard ValidationError.
- TestHardFails.test_null_published_at
  - Missing published_at must raise a hard ValidationError.
- TestHardFails.test_future_published_at
  - Future published_at must raise a hard ValidationError.
- TestHardFails.test_engagement_rate_over_100
  - Excessive engagement rate must raise a hard ValidationError.

- TestWarnings.test_old_published_at_warns
  - published_at older than 24 hours should return a warning (non-fatal).
- TestWarnings.test_recent_published_at_no_warning
  - Recent published_at should return no warnings.

- TestValid.test_valid_publication
  - Valid payload yields a computed engagement rate between 0 and 100.
- TestValid.test_engagement_rate_matches_formula
  - Valid payload computes the exact expected engagement rate.

## tests/test_stats.py

Focus: engagement-rate formula correctness independent of the database.

- TestStatsFormula.test_basic_engagement_rate
  - Verifies the standard formula for a normal payload.
- TestStatsFormula.test_high_engagement
  - Verifies a high-engagement case returns the expected value.
- TestStatsFormula.test_no_engagement
  - Ensures zero engagement yields 0.0 even with followers.
- TestStatsFormula.test_zero_followers
  - Ensures zero followers yields 0.0 without errors.
- TestStatsFormula.test_engagement_rate_all_metrics_contribute
  - Ensures likes, views, comments, and shares all contribute to the formula.