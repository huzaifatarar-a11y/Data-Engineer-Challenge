from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from elasticsearch import AsyncElasticsearch


@dataclass(frozen=True)
class MetricFilter:
    field: str
    gte: float | None = None
    lte: float | None = None
    value: float | None = None


@dataclass(frozen=True)
class SearchFilters:
    author_id: str | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    metrics: list[MetricFilter] | None = None


class PublicationSearchService:
    def __init__(self, client: AsyncElasticsearch, index_name: str, alias: str | None = None) -> None:
        self.client = client
        self.index_name = index_name
        self.alias = alias

    async def search(
        self,
        *,
        query: str | None = None,
        filters: SearchFilters | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        body = {
            "query": build_search_query(query=query, filters=filters),
            "_source": [
                "id",
                "publication_url",
                "author_id",
                "author_name",
                "title",
                "description",
                "platform",
                "published_at",
                "created_at",
                "updated_at",
                "deleted_at",
                "metrics",
            ],
            "from": offset,
            "size": limit,
            "track_total_hits": True,
            "sort": [
                {"published_at": {"order": "desc", "missing": "_last"}},
                {"created_at": {"order": "desc", "missing": "_last"}},
            ],
        }

        result = await self.client.search(index=self.alias or self.index_name, body=body)
        hits = result.get("hits", {})
        total = hits.get("total", {}).get("value", 0)

        return {
            "items": [hit.get("_source", {}) for hit in hits.get("hits", [])],
            "total": total,
            "took_ms": result.get("took"),
        }


def build_search_query(query: str | None, filters: SearchFilters | None) -> dict[str, Any]:
    must: list[dict[str, Any]] = []
    filter_clauses: list[dict[str, Any]] = []
    must_not: list[dict[str, Any]] = [{"exists": {"field": "deleted_at"}}]

    if query:
        must.append(
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "description^2", "author_name^2"],
                    "type": "best_fields",
                    "operator": "and",
                }
            }
        )
    else:
        must.append({"match_all": {}})

    if filters:
        if filters.author_id:
            filter_clauses.append({"term": {"author_id": filters.author_id}})

        if filters.published_from or filters.published_to:
            filter_clauses.append(
                {
                    "range": {
                        "published_at": {
                            **({"gte": filters.published_from.isoformat()} if filters.published_from else {}),
                            **({"lte": filters.published_to.isoformat()} if filters.published_to else {}),
                        }
                    }
                }
            )

        if filters.created_from or filters.created_to:
            filter_clauses.append(
                {
                    "range": {
                        "created_at": {
                            **({"gte": filters.created_from.isoformat()} if filters.created_from else {}),
                            **({"lte": filters.created_to.isoformat()} if filters.created_to else {}),
                        }
                    }
                }
            )

        if filters.metrics:
            for metric in filters.metrics:
                field = f"metrics.{metric.field}"
                if metric.value is not None:
                    filter_clauses.append({"term": {field: metric.value}})
                else:
                    range_body: dict[str, Any] = {}
                    if metric.gte is not None:
                        range_body["gte"] = metric.gte
                    if metric.lte is not None:
                        range_body["lte"] = metric.lte
                    if range_body:
                        filter_clauses.append({"range": {field: range_body}})

    return {
        "bool": {
            "must": must,
            "filter": filter_clauses,
            "must_not": must_not,
        }
    }
