from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    base_delay_seconds: float

    async def wait(self, attempt: int) -> None:
        delay = self.base_delay_seconds * (2 ** (attempt - 1))
        await asyncio.sleep(delay)
