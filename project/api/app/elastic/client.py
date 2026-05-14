from __future__ import annotations

from contextlib import asynccontextmanager

from elasticsearch import AsyncElasticsearch

from app.core.config import Settings


def build_elasticsearch_client(settings: Settings) -> AsyncElasticsearch:
	basic_auth = None
	if settings.elasticsearch_username and settings.elasticsearch_password:
		basic_auth = (settings.elasticsearch_username, settings.elasticsearch_password)

	return AsyncElasticsearch(
		hosts=[settings.elasticsearch_url],
		basic_auth=basic_auth,
		request_timeout=settings.elasticsearch_request_timeout,
		max_retries=settings.elasticsearch_max_retries,
		retry_on_timeout=settings.elasticsearch_retry_on_timeout,
	)


@asynccontextmanager
async def get_elasticsearch_client(settings: Settings):
	client = build_elasticsearch_client(settings)
	try:
		yield client
	finally:
		await client.close()
