from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_metrics(metrics: dict[str, Any] | None) -> dict[str, Any]:
    if not metrics:
        return {}
    return dict(metrics)


def calculate_engagement_rate(metrics: dict[str, Any]) -> float | None:
    """
    Engagement rate per publication:
        (likes + views + comments + shares) / follower_count_at_post

    Returns None if follower_count_at_post is 0 or missing (avoid division by zero).
    The result is a raw ratio (not multiplied by 100) — the challenge states the
    range is 0 to 100, which is enforced in the validation layer.
    """
    follower_count = _to_float(metrics.get("follower_count_at_post"))
    if follower_count is None or follower_count <= 0:
        return None

    likes = _to_float(metrics.get("likes")) or 0.0
    views = _to_float(metrics.get("views")) or 0.0
    comments = _to_float(metrics.get("comments")) or 0.0
    shares = _to_float(metrics.get("shares")) or 0.0

    rate = (likes + views + comments + shares) / follower_count
    return round(rate, 6)
