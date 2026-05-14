from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Metrics(BaseModel):
    model_config = ConfigDict(extra="allow")

    views: int | None = None
    likes: int | None = None
    shares: int | None = None
    comments: int | None = None
    follower_count_at_post: int | None = None
    engagement_rate: float | None = None


class PublicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publication_url: HttpUrl
    author_id: str
    title: str | None = None
    author_name: str | None = None
    published_at: datetime | None = None
    summary: str | None = None
    platform: str | None = None
    metrics: Metrics = Field(default_factory=Metrics)


class PublicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    publication_url: HttpUrl
    author_id: str
    title: str | None = None
    author_name: str | None = None
    published_at: datetime | None = None
    summary: str | None = None
    platform: str | None = None
    metrics: Metrics | dict[str, Any]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class SearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[PublicationResponse]
    took_ms: int | None = None


class AuthorStats(BaseModel):
    author_id: str
    total_posts: int
    average_engagement_rate: float
