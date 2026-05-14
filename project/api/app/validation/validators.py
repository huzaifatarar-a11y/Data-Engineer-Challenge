from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

from app.validation.utils import is_future, is_older_than


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    field: str
    severity: str

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class ValidationResult:
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "valid": self.is_valid,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


def _required_field(value: Any, field: str, code: str, message: str) -> Iterable[ValidationIssue]:
    if value is None:
        return [ValidationIssue(code=code, message=message, field=field, severity="error")]
    if isinstance(value, str) and not value.strip():
        return [ValidationIssue(code=code, message=message, field=field, severity="error")]
    return []


def validate_publication_url(payload: dict[str, Any]) -> Iterable[ValidationIssue]:
    return _required_field(
        payload.get("publication_url"),
        field="publication_url",
        code="publication_url_required",
        message="publication_url is required",
    )


def validate_author_id(payload: dict[str, Any]) -> Iterable[ValidationIssue]:
    return _required_field(
        payload.get("author_id"),
        field="author_id",
        code="author_id_required",
        message="author_id is required",
    )


def validate_published_at(payload: dict[str, Any], now: datetime | None = None) -> Iterable[ValidationIssue]:
    published_at = payload.get("published_at")
    issues: list[ValidationIssue] = []

    issues.extend(
        _required_field(
            published_at,
            field="published_at",
            code="published_at_required",
            message="published_at is required",
        )
    )

    if isinstance(published_at, datetime) and is_future(published_at, now=now):
        issues.append(
            ValidationIssue(
                code="published_at_in_future",
                message="published_at cannot be in the future",
                field="published_at",
                severity="error",
            )
        )

    if isinstance(published_at, datetime) and is_older_than(
        published_at,
        delta=timedelta(hours=24),
        now=now,
    ):
        issues.append(
            ValidationIssue(
                code="published_at_older_than_24h",
                message="published_at is older than 24h",
                field="published_at",
                severity="warning",
            )
        )

    return issues


def validate_engagement_rate(payload: dict[str, Any]) -> Iterable[ValidationIssue]:
    metrics = payload.get("metrics") or {}
    engagement_rate = None

    if isinstance(metrics, dict):
        engagement_rate = metrics.get("engagement_rate")

    if engagement_rate is None:
        return []

    try:
        value = float(engagement_rate)
    except (TypeError, ValueError):
        return [
            ValidationIssue(
                code="engagement_rate_invalid",
                message="engagement_rate must be a number between 0 and 100",
                field="metrics.engagement_rate",
                severity="error",
            )
        ]

    if value < 0 or value > 100:
        return [
            ValidationIssue(
                code="engagement_rate_out_of_range",
                message="engagement_rate must be between 0 and 100",
                field="metrics.engagement_rate",
                severity="error",
            )
        ]

    return []


def validate_duplicate_publication_url(is_duplicate: bool) -> Iterable[ValidationIssue]:
    if not is_duplicate:
        return []
    return [
        ValidationIssue(
            code="publication_url_duplicate",
            message="publication_url already exists",
            field="publication_url",
            severity="warning",
        )
    ]


def run_validations(
    payload: dict[str, Any],
    *,
    now: datetime | None = None,
    is_duplicate: bool = False,
) -> ValidationResult:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    for issue in validate_publication_url(payload):
        (warnings if issue.severity == "warning" else errors).append(issue)
    for issue in validate_author_id(payload):
        (warnings if issue.severity == "warning" else errors).append(issue)
    for issue in validate_published_at(payload, now=now):
        (warnings if issue.severity == "warning" else errors).append(issue)
    for issue in validate_engagement_rate(payload):
        (warnings if issue.severity == "warning" else errors).append(issue)
    for issue in validate_duplicate_publication_url(is_duplicate):
        (warnings if issue.severity == "warning" else errors).append(issue)

    return ValidationResult(errors=errors, warnings=warnings)
