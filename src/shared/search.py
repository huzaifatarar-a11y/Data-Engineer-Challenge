from __future__ import annotations

import logging
from typing import Dict, List, Optional

from opensearchpy import AsyncOpenSearch

from shared.config import settings

logger = logging.getLogger(__name__)

INDEX_NAME = "publications"

INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 2,
        "number_of_replicas": 0,
        "analysis": {"analyzer": {"text_analyzer": {"type": "standard"}}},
    },
    "mappings": {
        "properties": {
            "publication_id": {"type": "keyword"},
            "publication_url": {"type": "keyword"},
            "title": {"type": "text", "analyzer": "standard"},
            "author_name": {
                "type": "text",
                "analyzer": "standard",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "author_id": {"type": "keyword"},
            "published_at": {"type": "date"},
            "description": {"type": "text", "analyzer": "standard"},
            "media_url": {"type": "keyword"},
            "metrics": {
                "type": "object",
                "properties": {
                    "likes": {"type": "integer"},
                    "views": {"type": "integer"},
                    "comments": {"type": "integer"},
                    "shares": {"type": "integer"},
                    "follower_count_at_post": {"type": "integer"},
                },
            },
            "engagement_rate": {"type": "float"},
            "platform": {"type": "keyword"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
            "deleted_at": {"type": "date"},
        }
    },
}


def get_opensearch_client() -> AsyncOpenSearch:
    return AsyncOpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        use_ssl=False,
        verify_certs=False,
    )


async def ensure_index(client: AsyncOpenSearch) -> None:
    if not await client.indices.exists(index=INDEX_NAME):
        await client.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)
        logger.info("Created OpenSearch index '%s'", INDEX_NAME)


async def index_publication(client: AsyncOpenSearch, doc_id: str, doc: dict) -> None:
    await client.index(index=INDEX_NAME, id=doc_id, body=doc, refresh="false")


async def bulk_index(client: AsyncOpenSearch, actions: list[dict]) -> None:
    if not actions:
        return
    body: list[dict] = []
    for action in actions:
        body.append({"index": {"_index": INDEX_NAME, "_id": action["_id"]}})
        body.append(action["_source"])
    await client.bulk(body=body, refresh="false")


async def delete_from_index(client: AsyncOpenSearch, doc_id: str) -> None:
    try:
        await client.delete(index=INDEX_NAME, id=doc_id, refresh="false")
    except Exception:
        logger.debug("Doc %s not in index (or already deleted)", doc_id)


async def search_publications(
    client: AsyncOpenSearch,
    *,
    query: Optional[str] = None,
    author_id: Optional[str] = None,
    published_after: Optional[str] = None,
    published_before: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    min_engagement_rate: Optional[float] = None,
    max_engagement_rate: Optional[float] = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    must: list[dict] = []
    filters: list[dict] = []

    must.append({"bool": {"must_not": {"exists": {"field": "deleted_at"}}}})

    if query:
        must.append(
            {
                "multi_match": {
                    "query": query,
                    "fields": ["description^3", "title^2", "author_name"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            }
        )

    if author_id:
        filters.append({"term": {"author_id": author_id}})

    pub_range: dict = {}
    if published_after:
        pub_range["gte"] = published_after
    if published_before:
        pub_range["lte"] = published_before
    if pub_range:
        filters.append({"range": {"published_at": pub_range}})

    created_range: dict = {}
    if created_after:
        created_range["gte"] = created_after
    if created_before:
        created_range["lte"] = created_before
    if created_range:
        filters.append({"range": {"created_at": created_range}})

    eng_range: dict = {}
    if min_engagement_rate is not None:
        eng_range["gte"] = min_engagement_rate
    if max_engagement_rate is not None:
        eng_range["lte"] = max_engagement_rate
    if eng_range:
        filters.append({"range": {"engagement_rate": eng_range}})

    body = {
        "query": {"bool": {"must": must, "filter": filters}},
        "from": (page - 1) * size,
        "size": size,
        "sort": [{"published_at": {"order": "desc"}}],
    }

    result = await client.search(index=INDEX_NAME, body=body)
    hits = result["hits"]
    return {
        "total": hits["total"]["value"],
        "publications": [hit["_source"] for hit in hits["hits"]],
    }
