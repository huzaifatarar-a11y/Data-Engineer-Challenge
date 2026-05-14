from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class Metrics(BaseModel):
    model_config = ConfigDict(extra="allow")

    views: int | None = None
    likes: int | None = None
    shares: int | None = None
    comments: int | None = None
    follower_count_at_post: int | None = None
    engagement_rate: float | None = None


class PublicationCreate(BaseModel):
    """
    Accepts the full producer payload.
    The producer sends `description`; we store it as `summary`.
    Extra fields (media_url, created_at, updated_at, deleted_at) are silently ignored.
    """

    model_config = ConfigDict(extra="ignore")

    publication_url: HttpUrl
    author_id: str  # producer sends UUID string; keep as str for flexibility
    title: str | None = None
    author_name: str | None = None
    published_at: datetime | None = None
    # Producer sends "description"; API clients may send "summary"
    description: str | None = Field(default=None, exclude=True)
    summary: str | None = None
    platform: str | None = None
    metrics: Metrics = Field(default_factory=Metrics)

    @model_validator(mode="after")
    def map_description_to_summary(self) -> "PublicationCreate":
        """If summary is not provided, use description."""
        if self.summary is None and self.description is not None:
            self.summary = self.description
        return self


class PublicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    publication_url: str  # Return as plain string, not Pydantic HttpUrl
    author_id: str
    title: str | None = None
    author_name: str | None = None
    published_at: datetime | None = None
    summary: str | None = None
    platform: str | None = None
    metrics: Any  # dict or Metrics — keep flexible
    created_at: datetime
    updated_at: datetime | None = None
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
