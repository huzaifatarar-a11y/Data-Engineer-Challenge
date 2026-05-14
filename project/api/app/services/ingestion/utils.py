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
    views = _to_float(metrics.get("views"))
    likes = _to_float(metrics.get("likes"))
    shares = _to_float(metrics.get("shares"))

    if views is None or views <= 0:
        return None

    total = (likes or 0.0) + (shares or 0.0)
    return round((total / views) * 100.0, 4)
