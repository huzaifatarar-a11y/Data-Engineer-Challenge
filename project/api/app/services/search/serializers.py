from __future__ import annotations

from typing import Any

from app.schemas.publication import PublicationResponse, SearchResponse


def serialize_publication(doc: dict[str, Any]) -> PublicationResponse:
    payload = dict(doc)
    if "description" in payload and "summary" not in payload:
        payload["summary"] = payload.pop("description")
    return PublicationResponse.model_validate(payload)


def build_search_response(
    result: dict[str, Any],
    *,
    limit: int,
    offset: int,
) -> SearchResponse:
    items = [serialize_publication(item) for item in result.get("items", [])]
    return SearchResponse(
        total=int(result.get("total", 0)),
        limit=limit,
        offset=offset,
        items=items,
        took_ms=result.get("took_ms"),
    )
