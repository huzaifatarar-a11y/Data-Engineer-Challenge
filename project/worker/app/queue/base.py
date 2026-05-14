from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol


@dataclass(frozen=True)
class QueueMessage:
    payload: dict


class AsyncQueue(Protocol):
    async def listen(self) -> AsyncIterator[QueueMessage]:
        ...

    async def ack(self, message: QueueMessage) -> None:
        ...

    async def dead_letter(self, message: QueueMessage, reason: str) -> None:
        ...
