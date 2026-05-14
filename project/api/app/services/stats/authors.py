from __future__ import annotations

from app.repositories.publication import AuthorStatsRow, PublicationRepository
from app.schemas.publication import AuthorStats


class AuthorStatsService:
    def __init__(self, repository: PublicationRepository) -> None:
        self.repository = repository

    async def get_stats(self, author_id: str) -> AuthorStats | None:
        row: AuthorStatsRow | None = await self.repository.get_author_stats(author_id)
        if row is None:
            return None

        return AuthorStats(
            author_id=row.author_id,
            total_posts=row.total_posts,
            average_engagement_rate=row.average_engagement_rate,
        )
