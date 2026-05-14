from __future__ import annotations

from typing import Iterable

from app.validation.validators import ValidationIssue


class IngestionValidationError(Exception):
    def __init__(self, issues: Iterable[ValidationIssue]):
        self.issues = list(issues)
        message = "Validation failed"
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "error": "validation_failed",
            "issues": [issue.to_dict() for issue in self.issues],
        }
