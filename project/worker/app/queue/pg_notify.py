from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

import asyncpg

from app.core.config import Settings
from app.queue.base import AsyncQueue, QueueMessage

logger = logging.getLogger(__name__)


class PostgresNotifyQueue(AsyncQueue):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._queue: asyncio.Queue[QueueMessage] = asyncio.Queue()

    async def listen(self) -> AsyncIterator[QueueMessage]:
        connection = await asyncpg.connect(self._connection_dsn())
        await connection.add_listener(self.settings.indexing_channel, self._listener)

        try:
            while True:
                message = await self._queue.get()
                yield message
        finally:
            await connection.close()

    def _listener(self, connection, pid, channel, payload):
        try:
            data = json.loads(payload)
            asyncio.create_task(self._queue.put(QueueMessage(payload=data)))
        except json.JSONDecodeError:
            logger.warning("Failed to decode queue payload", extra={"payload": payload})

    async def ack(self, message: QueueMessage) -> None:
        return None

    async def dead_letter(self, message: QueueMessage, reason: str) -> None:
        logger.error("Dead-lettered message", extra={"reason": reason, "payload": message.payload})

    def _connection_dsn(self) -> str:
        return self.settings.database_url.replace("postgresql+asyncpg", "postgresql")
