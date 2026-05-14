from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.publication import Publication


class IndexingEventPublisher:
    def __init__(self, session: AsyncSession, channel: str) -> None:
        self.session = session
        self.channel = channel

    async def publish(self, publication: Publication) -> None:
        payload = {
            "event": "publication.upserted",
            "publication_id": str(publication.id),
            "publication_url": publication.publication_url,
            "author_id": publication.author_id,
            "published_at": _isoformat(publication.published_at),
            "updated_at": _isoformat(publication.updated_at),
        }
        await self.session.execute(
            text("select pg_notify(:channel, :payload)"),
            {"channel": self.channel, "payload": json.dumps(payload)},
        )


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
