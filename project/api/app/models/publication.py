from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from app.db.base import BaseModel


class Publication(BaseModel):
    __tablename__ = "publications"

    publication_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    author_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    __table_args__ = (
        UniqueConstraint("publication_url", name="uq_publications_publication_url"),
        Index("ix_publications_published_at", "published_at"),
        Index(
            "ix_publications_author_id",
            "author_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_publications_active",
            "deleted_at",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
