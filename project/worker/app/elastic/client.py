from __future__ import annotations

from elasticsearch import AsyncElasticsearch

from app.core.config import Settings


def build_elasticsearch_client(settings: Settings) -> AsyncElasticsearch:
    return AsyncElasticsearch(
        hosts=[settings.elasticsearch_url],
        request_timeout=settings.elasticsearch_request_timeout,
        max_retries=settings.elasticsearch_max_retries,
        retry_on_timeout=settings.elasticsearch_retry_on_timeout,
    )
