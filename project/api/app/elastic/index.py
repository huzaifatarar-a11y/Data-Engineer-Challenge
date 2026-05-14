from __future__ import annotations

from typing import Any

from elasticsearch import AsyncElasticsearch


PUBLICATIONS_INDEX_SETTINGS = {
	"number_of_shards": 1,
	"number_of_replicas": 0,
	"refresh_interval": "1s",
}

PUBLICATIONS_INDEX_MAPPINGS = {
	"dynamic": True,
	"properties": {
		"id": {"type": "keyword"},
		"publication_url": {"type": "keyword"},
		"author_id": {"type": "keyword"},
		"author_name": {
			"type": "text",
			"fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
		},
		"title": {
			"type": "text",
			"fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
		},
		"description": {"type": "text"},
		"platform": {"type": "keyword"},
		"published_at": {"type": "date"},
		"created_at": {"type": "date"},
		"updated_at": {"type": "date"},
		"deleted_at": {"type": "date"},
		"metrics": {"type": "object", "dynamic": True},
	},
}


def build_publications_index_body(alias: str | None = None) -> dict[str, Any]:
	body: dict[str, Any] = {
		"settings": PUBLICATIONS_INDEX_SETTINGS,
		"mappings": PUBLICATIONS_INDEX_MAPPINGS,
	}
	if alias:
		body["aliases"] = {alias: {}}
	return body


class IndexManager:
	def __init__(self, client: AsyncElasticsearch, index_name: str, alias: str | None = None) -> None:
		self.client = client
		self.index_name = index_name
		self.alias = alias

	async def ensure_index(self) -> None:
		exists = await self.client.indices.exists(index=self.index_name)
		if not exists:
			body = build_publications_index_body(alias=self.alias)
			await self.client.indices.create(index=self.index_name, body=body)
			return

		if self.alias:
			alias_exists = await self.client.indices.exists_alias(name=self.alias)
			if not alias_exists:
				await self.client.indices.put_alias(index=self.index_name, name=self.alias)

	async def refresh(self) -> None:
		await self.client.indices.refresh(index=self.alias or self.index_name)
