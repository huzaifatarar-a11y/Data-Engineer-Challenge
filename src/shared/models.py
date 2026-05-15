from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, HttpUrl
from sqlalchemy import DateTime, Float, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ---------------------------------------------------------------------------
# Pydantic schemas (wire format)
# ---------------------------------------------------------------------------

class MetricsSchema(BaseModel):
    likes: int
    views: int
    comments: int
    shares: int
    follower_count_at_post: int


class PublicationIn(BaseModel):
    publication_url: HttpUrl
    title: str
    author_name: str
    author_id: uuid.UUID
    published_at: datetime
    description: str
    media_url: HttpUrl
    metrics: MetricsSchema
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    platform: Optional[str] = None


class PublicationOut(BaseModel):
    publication_id: uuid.UUID
    publication_url: str
    title: str
    author_name: str
    author_id: uuid.UUID
    published_at: datetime
    description: str
    media_url: str
    metrics: Dict
    engagement_rate: float
    platform: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AuthorStats(BaseModel):
    author_id: uuid.UUID
    total_posts: int
    average_engagement_rate: float


class SearchResult(BaseModel):
    total: int
    publications: List[PublicationOut]


# ---------------------------------------------------------------------------
# SQLAlchemy ORM
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class Publication(Base):
    __tablename__ = "publications"
    __table_args__ = (
        Index("ix_publications_author_id", "author_id"),
        Index("ix_publications_published_at", "published_at"),
        Index("ix_publications_created_at", "created_at"),
    )

    publication_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    publication_url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    author_name: Mapped[str] = mapped_column(String, nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    media_url: Mapped[str] = mapped_column(String, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    engagement_rate: Mapped[float] = mapped_column(Float, nullable=False)
    platform: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
