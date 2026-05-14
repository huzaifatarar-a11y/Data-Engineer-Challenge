from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.validation.exceptions import IngestionValidationError
from app.validation.validators import ValidationResult, run_validations

logger = logging.getLogger(__name__)


class ValidationService:
    def validate(
        self,
        payload: dict[str, Any],
        *,
        now: datetime | None = None,
        is_duplicate: bool = False,
    ) -> ValidationResult:
        result = run_validations(payload, now=now, is_duplicate=is_duplicate)

        if result.warnings:
            for warning in result.warnings:
                logger.warning(
                    "Validation warning",
                    extra={
                        "code": warning.code,
                        "field": warning.field,
                        "details": warning.message,
                    },
                )

        if not result.is_valid:
            raise IngestionValidationError(result.errors)

        return result
