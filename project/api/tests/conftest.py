from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest
from elasticsearch import AsyncElasticsearch
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db.base import Base
from app.db.session import get_session
from app.dependencies import get_search_service
from app.elastic.index import IndexManager
from app.main import create_app
from app.models import Publication
from app.services.search import PublicationSearchService


def _database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        url = "postgresql+asyncpg://postgres:postgres@localhost:5432/publications"
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _elasticsearch_url() -> str:
    return (
        os.getenv("TEST_ELASTICSEARCH_URL")
        or os.getenv("ELASTICSEARCH_URL")
        or "http://localhost:9200"
    )


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(_database_url(), pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        await engine.dispose()
        pytest.skip("PostgreSQL is not available for tests")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture()
async def db_session(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session
        await session.execute(text("TRUNCATE publications RESTART IDENTITY"))
        await session.commit()


async def _truncate_publications(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE publications RESTART IDENTITY"))


@pytest.fixture()
async def api_client(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    app = create_app()

    async def override_get_session():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await _truncate_publications(db_engine)


@pytest.fixture(scope="session")
async def es_client():
    client = AsyncElasticsearch(hosts=[_elasticsearch_url()])
    try:
        healthy = await client.ping()
    except Exception:
        await client.close()
        pytest.skip("Elasticsearch is not available for tests")

    if not healthy:
        await client.close()
        pytest.skip("Elasticsearch is not available for tests")

    yield client
    await client.close()


@pytest.fixture()
async def es_index(es_client):
    index_name = f"publications-test-{uuid.uuid4().hex}"
    alias = f"{index_name}-alias"

    manager = IndexManager(es_client, index_name, alias=alias)
    await manager.ensure_index()

    yield {"index": index_name, "alias": alias}

    await es_client.indices.delete(index=index_name, ignore_unavailable=True)


@pytest.fixture()
async def api_client_with_es(db_engine, es_client, es_index):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    app = create_app()

    async def override_get_session():
        async with session_maker() as session:
            yield session

    async def override_search_service():
        yield PublicationSearchService(
            es_client,
            index_name=es_index["index"],
            alias=es_index["alias"],
        )

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_search_service] = override_search_service

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await _truncate_publications(db_engine)
