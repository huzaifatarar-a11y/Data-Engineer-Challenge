# Data Platform Engineer Assignment

## 1. Project overview
This project ingests continuous publication events via a FastAPI webhook, validates and stores them in PostgreSQL (source of truth), and powers low-latency full-text search with Elasticsearch. A background worker consumes indexing events and keeps Elasticsearch in sync with Postgres. The design favors clear separation of concerns, testability, and production-style reliability while remaining simple enough to run locally with Docker Compose.

## 2. Architecture explanation
High-level flow:

+-------------+        +----------------+        +--------------------+
| Producer(s) | -----> | FastAPI API    | -----> | PostgreSQL (source) |
+-------------+        +----------------+        +--------------------+
                              |                             |
                              | pg_notify                   |
                              v                             |
                       +----------------+                    |
                       | Indexing Worker| -------------------+
                       +----------------+
                              |
                              v
                      +--------------------+
                      | Elasticsearch (read)|
                      +--------------------+

Detailed ingestion sequence:

1) API receives publication payload
2) Pydantic + data quality validations
3) Upsert into PostgreSQL (publication_url unique)
4) Emit pg_notify event
5) Worker fetches record from Postgres
6) Worker indexes into Elasticsearch

## 3. Technology choices
- FastAPI: async-first, fast iteration, OpenAPI support
- PostgreSQL: reliable transactional source of truth with JSONB for metrics
- Elasticsearch 8.x: low-latency full-text search and filtering
- SQLAlchemy 2.0 async: modern ORM with clear unit-of-work semantics
- Pydantic v2: fast validation and strict schema contracts
- Alembic: schema migration tooling
- Docker Compose: local dev parity with production services

## 4. Tradeoffs
- pg_notify is lightweight but not durable; good for local/dev and small-scale, but not a full queue.
- Elasticsearch offers fast search but adds operational complexity and eventual consistency.
- JSONB allows schema evolution, but limits strict constraints on metrics fields.

## 5. System design decisions
- PostgreSQL is the canonical system of record; Elasticsearch is read-optimized only.
- Upsert by publication_url ensures idempotent ingestion and supports duplicate events.
- Soft deletes via deleted_at preserve historical data while hiding it from reads.
- Ingestion is synchronous to Postgres, indexing is async for latency isolation.

## 6. Why PostgreSQL + Elasticsearch
- PostgreSQL provides strong consistency, constraints, and analytics queries.
- Elasticsearch provides near real-time full-text search and flexible scoring.
- Combined, they separate write integrity from read performance.

## 7. How workload separation works
- Write path: API -> Postgres only (fast, transactional)
- Read/search path: API -> Elasticsearch for search queries
- Analytics path: API -> Postgres for author stats and aggregates
- Indexing path: Worker -> Postgres -> Elasticsearch

## 8. Folder structure
- api/: FastAPI app, schemas, repositories, services, validation, migrations
- worker/: Background indexing worker (queue abstraction + retry)
- infra/: Elasticsearch and Postgres configuration artifacts
- tests/: Shared or project-level tests

## 9. Local setup instructions
1) Copy environment defaults:
   - cp .env.example .env
2) Start services:
   - docker compose up --build
3) Run migrations:
   - alembic -c api/alembic.ini upgrade head
4) Run API:
   - docker compose up api

## 10. Docker Compose instructions
- Start full stack:
  - docker compose up --build
- Start only data services:
  - docker compose up -d postgres elasticsearch kibana
- Stop services:
  - docker compose down

## 11. API documentation
- Health: GET /api/v1/health
- Ingest publication: POST /api/v1/publications
- Search publications: GET /api/v1/publications/search
- Author stats: GET /api/v1/authors/{author_id}/stats

Example ingestion payload:
{
  "publication_url": "https://example.com/post-1",
  "author_id": "author-1",
  "author_name": "Alice",
  "published_at": "2026-05-14T10:00:00Z",
  "summary": "Example description",
  "metrics": {"views": 100, "likes": 10, "shares": 5}
}

## 12. Validation rules
Hard fail:
- publication_url not null
- author_id not null
- published_at not null
- engagement_rate between 0 and 100
- published_at cannot be in the future

Warning only:
- published_at older than 24h
- duplicate publication_url

## 13. Data quality strategy
- Centralized validation service with structured issues and severities.
- Warnings are logged with structured context for observability.
- Hard failures return consistent 422 responses.

## 14. Schema evolution strategy
- Publication metrics stored in JSONB for flexible additions.
- Elasticsearch mappings use dynamic object for metrics.
- Schema changes that affect core fields are migrated via Alembic.

## 15. Migration plan for optional platform field
- Add nullable platform column via Alembic migration.
- Backfill where data exists (optional).
- Update Elasticsearch mapping (already supports platform as keyword).
- Reindex if platform used in search/filtering.

## 16. Scaling considerations
- Scale API horizontally; keep Postgres as the single write authority.
- Scale worker via multiple consumers; later move to Kafka for partitioning.
- Elasticsearch can scale shards and replicas as query volume grows.

## 17. Future improvements
- Kafka or RabbitMQ as durable event bus
- Batched indexing and backfill jobs
- Partial updates with optimistic concurrency on ES
- Streaming data quality and anomaly detection

## 18. Observability ideas
- Structured logs with request_id and publication_id
- Metrics: ingestion latency, indexing lag, search latency
- Tracing: API -> DB -> worker -> ES

## 19. Reliability considerations
- Upsert semantics ensure idempotency
- Dead-letter handling in worker for failed events
- Soft deletes avoid permanent data loss
- Health checks for all services

## 20. Security considerations
- Validate input at the edge using Pydantic
- Limit payload sizes and enforce request timeouts
- Use least-privilege DB roles in production
- Secure Elasticsearch with auth and TLS in non-local environments
