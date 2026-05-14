from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.validation.exceptions import IngestionValidationError
from app.validation.service import ValidationService
from app.validation.validators import run_validations


def test_validation_errors_and_warnings():
    now = datetime.now(timezone.utc)
    payload = {
        "publication_url": "https://example.com/valid",
        "author_id": "author-1",
        "published_at": now - timedelta(days=2),
        "metrics": {"engagement_rate": 200},
    }

    result = run_validations(payload, now=now, is_duplicate=True)

    assert result.errors
    assert result.warnings
    assert any(issue.code == "published_at_older_than_24h" for issue in result.warnings)
    assert any(issue.code == "publication_url_duplicate" for issue in result.warnings)
    assert any(issue.code == "engagement_rate_out_of_range" for issue in result.errors)


def test_validation_service_raises():
    payload = {
        "publication_url": "https://example.com/invalid",
        "author_id": "author-1",
    }

    service = ValidationService()

    with pytest.raises(IngestionValidationError):
        service.validate(payload, now=datetime.now(timezone.utc))
