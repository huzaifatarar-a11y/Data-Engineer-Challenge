from __future__ import annotations

from datetime import datetime
from typing import Iterable
from uuid import UUID

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from app.models.publication import Publication


class PublicationIndexer:
    def __init__(self, client: AsyncElasticsearch, index_name: str, alias: str | None = None) -> None:
        self.client = client
        self.index_name = index_name
        self.alias = alias

    async def index_publication(self, publication: Publication, *, refresh: bool = False) -> None:
        doc = publication_to_document(publication)
        await self.client.index(
            index=self.alias or self.index_name,
            id=str(publication.id),
            document=doc,
            refresh="wait_for" if refresh else False,
        )

    async def bulk_index(self, publications: Iterable[Publication], *, refresh: bool = False) -> None:
        actions = (
            {
                "_op_type": "index",
                "_index": self.alias or self.index_name,
                "_id": str(publication.id),
                "_source": publication_to_document(publication),
            }
            for publication in publications
        )
        await async_bulk(self.client, actions, refresh="wait_for" if refresh else False)


def publication_to_document(publication: Publication) -> dict:
    return {
        "id": str(publication.id),
        "publication_url": publication.publication_url,
        "author_id": publication.author_id,
        "author_name": publication.author_name,
        "title": publication.title,
        "description": publication.summary,
        "platform": getattr(publication, "platform", None),
        "published_at": _isoformat(publication.published_at),
        "created_at": _isoformat(publication.created_at),
        "updated_at": _isoformat(publication.updated_at),
        "deleted_at": _isoformat(publication.deleted_at),
        "metrics": publication.metrics or {},
    }


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
