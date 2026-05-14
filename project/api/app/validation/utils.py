from __future__ import annotations

from datetime import datetime, timezone, timedelta


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_future(value: datetime, now: datetime | None = None) -> bool:
    reference = _ensure_aware(now or utc_now())
    return _ensure_aware(value) > reference


def is_older_than(value: datetime, delta: timedelta, now: datetime | None = None) -> bool:
    reference = _ensure_aware(now or utc_now())
    return _ensure_aware(value) < reference - delta
