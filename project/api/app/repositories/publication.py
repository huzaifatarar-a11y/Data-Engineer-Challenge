from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import nulls_last

from app.models.publication import Publication


@dataclass(frozen=True)
class AuthorStatsRow:
    author_id: str
    total_posts: int
    average_engagement_rate: float


class PublicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base_query(self, *, include_deleted: bool = False) -> Select:
        stmt = select(Publication)
        if not include_deleted:
            stmt = stmt.where(Publication.deleted_at.is_(None))
        return stmt

    async def create_or_update_publication(self, payload: dict[str, Any]) -> Publication:
        insert_stmt = insert(Publication).values(**payload)

        update_values = {key: value for key, value in payload.items() if key != "id"}
        update_values["updated_at"] = func.now()
        update_values["deleted_at"] = None

        stmt = (
            insert_stmt.on_conflict_do_update(
                index_elements=[Publication.publication_url],
                set_=update_values,
            )
            .returning(Publication)
        )

        if self.session.in_transaction():
            result = await self.session.execute(stmt)
        else:
            async with self.session.begin():
                result = await self.session.execute(stmt)

        return result.scalar_one()

    async def publication_exists_by_url(self, publication_url: str) -> bool:
        stmt = (
            select(Publication.id)
            .where(Publication.publication_url == publication_url)
            .where(Publication.deleted_at.is_(None))
        )
        result = await self.session.scalar(stmt)
        return result is not None

    async def get_publication_by_id(
        self,
        publication_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> Publication | None:
        stmt = self._base_query(include_deleted=include_deleted).where(
            Publication.id == publication_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def search_publications(
        self,
        *,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> tuple[list[Publication], int]:
        stmt = self._base_query(include_deleted=include_deleted)

        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Publication.title.ilike(pattern),
                    Publication.summary.ilike(pattern),
                    Publication.author_name.ilike(pattern),
                    Publication.author_id.ilike(pattern),
                    Publication.publication_url.ilike(pattern),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.session.scalar(count_stmt)

        stmt = (
            stmt.order_by(nulls_last(Publication.published_at.desc()))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)

        return list(result.scalars().all()), int(total or 0)

    async def get_author_stats(self, author_id: str) -> AuthorStatsRow | None:
        stmt = text(
            """
            SELECT
                author_id,
                COUNT(*) AS total_posts,
                AVG(
                    (
                        COALESCE((metrics->>'likes')::numeric, 0) +
                        COALESCE((metrics->>'views')::numeric, 0) +
                        COALESCE((metrics->>'comments')::numeric, 0) +
                        COALESCE((metrics->>'shares')::numeric, 0)
                    ) / NULLIF((metrics->>'follower_count_at_post')::numeric, 0)
                ) AS average_engagement_rate
            FROM publications
            WHERE deleted_at IS NULL AND author_id = :author_id
            GROUP BY author_id
            """
        )

        result = await self.session.execute(stmt, {"author_id": author_id})
        row = result.mappings().one_or_none()
        if row is None:
            return None

        average = row["average_engagement_rate"]
        return AuthorStatsRow(
            author_id=row["author_id"],
            total_posts=int(row["total_posts"]),
            average_engagement_rate=float(average) if average is not None else 0.0,
        )
