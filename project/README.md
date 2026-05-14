# Data Platform Engineer Take-Home

This repository provides a local, production-style scaffold for ingesting publication events, storing them in PostgreSQL, indexing into Elasticsearch, and exposing a FastAPI API.

## What is done so far
- Docker Compose stack with Postgres, Elasticsearch, Kibana, FastAPI API, and a background worker.
- FastAPI app factory with versioned routing at `/api/v1` and a health endpoint.
- Async SQLAlchemy base, session management, and `Publication` model with soft deletes.
- Alembic configured for async migrations with an initial publications schema.
- Validation service with hard-fail and warning-only data quality rules.
- Repository layer with async CRUD, upsert, pagination, and author stats aggregation.
- Publication ingestion endpoint with data quality checks and indexing events.
- Elasticsearch integration with async client, index management, and search services.
- Background worker consuming indexing events and syncing PostgreSQL to Elasticsearch.
- Publications search endpoint backed by Elasticsearch with filters and pagination.
- Author stats endpoint with aggregated engagement metrics.

## Why these choices
- PostgreSQL is the source of truth; Elasticsearch is the read-optimized search layer.
- JSONB metrics on publications allow schema evolution without migrations for every metric change.
- Soft deletes keep historical data while allowing fast active-only queries via partial indexes.
- App factory pattern and DI make the API testable and composable for interview-grade architecture.

## How to use
1. Copy environment defaults:
	 - `cp .env.example .env`
2. Start services:
	 - `docker compose up --build`
3. Run migrations (local or inside container):
	 - `alembic -c api/alembic.ini upgrade head`

## Migrations
- Create a new revision:
	- `alembic -c api/alembic.ini revision --autogenerate -m "add field"`
- Apply migrations:
	- `alembic -c api/alembic.ini upgrade head`
- Roll back last revision:
	- `alembic -c api/alembic.ini downgrade -1`

## Service endpoints
- API health: `GET /api/v1/health`
- Postgres: `localhost:5432`
- Elasticsearch: `localhost:9200`
- Kibana: `localhost:5601`

## Testing
- Install test dependencies: `pip install -r requirements-test.txt`
- Start services: `docker compose up -d postgres elasticsearch`
- Run tests: `pytest`
- Use `TEST_DATABASE_URL` and `TEST_ELASTICSEARCH_URL` for isolated test resources
