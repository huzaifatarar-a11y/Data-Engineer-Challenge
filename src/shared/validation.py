from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Hard-fail data quality error."""


class ValidationWarning:
    def __init__(self, message: str) -> None:
        self.message = message


def compute_engagement_rate(metrics: dict) -> float:
    total = metrics["likes"] + metrics["views"] + metrics["comments"] + metrics["shares"]
    follower_count = metrics["follower_count_at_post"]
    if follower_count == 0:
        return 0.0
    return total / follower_count


def validate_publication(data: dict) -> tuple[list[ValidationWarning], float]:
    """Run data-quality checks. Returns (warnings, engagement_rate).

    Raises ``ValidationError`` on hard failures.
    """
    warnings: list[ValidationWarning] = []

    for field in ("publication_url", "author_id", "published_at"):
        if data.get(field) is None:
            raise ValidationError(f"Required field '{field}' is null")

    metrics = data.get("metrics", {})
    engagement_rate = compute_engagement_rate(metrics)

    if not (0 <= engagement_rate <= 100):
        raise ValidationError(
            f"Engagement rate {engagement_rate:.4f} is outside [0, 100]"
        )

    published_at = data["published_at"]
    if isinstance(published_at, str):
        published_at = datetime.fromisoformat(published_at)

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    if published_at > datetime.now(timezone.utc):
        raise ValidationError(f"published_at {published_at} is in the future")

    age = datetime.now(timezone.utc) - published_at
    if age > timedelta(hours=24):
        w = ValidationWarning(f"published_at {published_at} is older than 24 h ({age})")
        warnings.append(w)
        logger.warning("Data-quality warning: %s", w.message)

    return warnings, engagement_rate
