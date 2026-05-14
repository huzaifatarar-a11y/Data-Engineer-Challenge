from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

from elasticsearch import AsyncElasticsearch
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.queue.base import AsyncQueue, QueueMessage
from app.services.retry.policy import RetryPolicy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PublicationDocument:
    id: str
    publication_url: str
    author_id: str
    author_name: str | None
    title: str | None
    description: str | None
    platform: str | None
    published_at: str | None
    created_at: str | None
    updated_at: str | None
    deleted_at: str | None
    metrics: dict

    def to_document(self) -> dict:
        return {
            "id": self.id,
            "publication_url": self.publication_url,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "title": self.title,
            "description": self.description,
            "platform": self.platform,
            "published_at": self.published_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at,
            "metrics": self.metrics,
        }


class IndexingConsumer:
    def __init__(
        self,
        *,
        queue: AsyncQueue,
        session: AsyncSession,
        es_client: AsyncElasticsearch,
        index_name: str,
        retry_policy: RetryPolicy,
        max_in_flight: int = 1,
    ) -> None:
        self.queue = queue
        self.session = session
        self.es_client = es_client
        self.index_name = index_name
        self.retry_policy = retry_policy
        self.max_in_flight = max_in_flight

    async def run(self) -> None:
        semaphore = asyncio.Semaphore(self.max_in_flight)
        tasks: set[asyncio.Task[None]] = set()
        async for message in self.queue.listen():
            await semaphore.acquire()
            task = asyncio.create_task(self._process_message(message, semaphore))
            tasks.add(task)
            task.add_done_callback(tasks.discard)

    async def _process_message(self, message: QueueMessage, semaphore: asyncio.Semaphore) -> None:
        try:
            await self._handle_message(message)
        finally:
            semaphore.release()

    async def _handle_message(self, message: QueueMessage) -> None:
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                await self._index_from_message(message)
                await self.queue.ack(message)
                logger.info(
                    "Indexed publication",
                    extra={"publication_id": message.payload.get("publication_id")},
                )
                return
            except Exception as exc:
                logger.exception(
                    "Failed to process message",
                    extra={"attempt": attempt, "payload": message.payload},
                )
                if attempt >= self.retry_policy.max_attempts:
                    await self.queue.dead_letter(message, reason=str(exc))
                    return
                await self.retry_policy.wait(attempt)

    async def _index_from_message(self, message: QueueMessage) -> None:
        payload = message.payload
        publication_id = payload.get("publication_id")
        if not publication_id:
            raise ValueError("publication_id is missing")

        publication = await self._fetch_publication(publication_id)
        if publication is None:
            raise ValueError("publication not found")

        await self.es_client.index(
            index=self.index_name,
            id=publication.id,
            document=publication.to_document(),
            refresh=False,
        )

    async def _fetch_publication(self, publication_id: str) -> PublicationDocument | None:
        result = await self.session.execute(
            text(
                """
                SELECT
                    id,
                    publication_url,
                    author_id,
                    author_name,
                    title,
                    summary,
                    platform,
                    published_at,
                    created_at,
                    updated_at,
                    deleted_at,
                    metrics
                FROM publications
                WHERE id = :publication_id
                """
            ),
            {"publication_id": publication_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None

        return PublicationDocument(
            id=str(row["id"]),
            publication_url=row["publication_url"],
            author_id=row["author_id"],
            author_name=row["author_name"],
            title=row["title"],
            description=row["summary"],
            platform=row["platform"],
            published_at=_isoformat(row["published_at"]),
            created_at=_isoformat(row["created_at"]),
            updated_at=_isoformat(row["updated_at"]),
            deleted_at=_isoformat(row["deleted_at"]),
            metrics=row["metrics"] or {},
        )


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
