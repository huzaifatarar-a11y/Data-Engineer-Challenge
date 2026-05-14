from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings


def _build_engine():
	settings = Settings()
	return create_async_engine(
		settings.database_url,
		pool_pre_ping=True,
		pool_size=5,
		max_overflow=10,
	)


engine = _build_engine()
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
	async with SessionLocal() as session:
		yield session
