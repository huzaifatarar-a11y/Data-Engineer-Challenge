from __future__ import annotations

import asyncio
import logging

from elasticsearch import AsyncElasticsearch

from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.session import get_session
from app.elastic.client import build_elasticsearch_client
from app.queue.pg_notify import PostgresNotifyQueue
from app.services.indexing.consumer import IndexingConsumer
from app.services.retry.policy import RetryPolicy

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)

    queue = PostgresNotifyQueue(settings)
    es_client: AsyncElasticsearch = build_elasticsearch_client(settings)
    session = await get_session()

    retry_policy = RetryPolicy(
        max_attempts=settings.worker_max_retries,
        base_delay_seconds=settings.worker_retry_base_seconds,
    )

    consumer = IndexingConsumer(
        queue=queue,
        session=session,
        es_client=es_client,
        index_name=settings.elasticsearch_index,
        retry_policy=retry_policy,
        max_in_flight=settings.worker_concurrency,
    )

    try:
        await consumer.run()
    finally:
        await session.close()
        await es_client.close()


if __name__ == "__main__":
    asyncio.run(main())
