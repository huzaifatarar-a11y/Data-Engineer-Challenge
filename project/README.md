# Primetag – Data Platform Engineer Challenge

## Quick Start

```bash
# 1. Enter the project directory
cd project/

# 2. Copy env template
cp .env.example .env

# 3. Start full stack (Postgres + Elasticsearch + Kibana + API + Worker)
docker compose up --build

# 4. API is ready at http://localhost:8000/api/v1/docs
#    Migrations run automatically on API startup.

# 5. Run the producer (from repo root) to flood the API with data
cd ../producer
pip install -r requirements.txt
python producer.py --url http://localhost:8000/api/v1/publications --workers 5
```

---

## Architecture

```
┌──────────────────┐        ┌──────────────────────────────────────┐
│  Producer(s)     │──POST──▶          FastAPI  (port 8000)         │
│  (HTTP webhook)  │        │  /api/v1/publications  (write)        │
└──────────────────┘        │  /api/v1/publications/search (ES)     │
                             │  /api/v1/publications/{id} (PG read)  │
                             │  /api/v1/authors/{id}/stats  (PG agg) │
                             └───────────┬──────────────┬────────────┘
                                         │ upsert       │ pg_notify
                                         ▼              ▼
                            ┌─────────────────┐  ┌──────────────────┐
                            │   PostgreSQL 16  │  │  Indexing Worker │
                            │  (source-of-     │◀─│  (async consumer)│
                            │   truth)         │  └────────┬─────────┘
                            └─────────────────┘           │ index doc
                                                           ▼
                                                ┌─────────────────────┐
                                                │  Elasticsearch 8.x  │
                                                │  (full-text search) │
                                                └─────────────────────┘
                                                          │
                                                ┌─────────▼─────────┐
                                                │  Kibana (port 5601)│
                                                └───────────────────┘
```

### Data Flow

1. Producer POSTs a publication to `POST /api/v1/publications`
2. Pydantic validates the shape; our `ValidationService` applies data-quality rules
3. Record is upserted into **PostgreSQL** (`publication_url` unique constraint)
4. A `pg_notify` event is fired within the same transaction
5. The **Indexing Worker** wakes up, fetches the full record from Postgres, and indexes it into **Elasticsearch**
6. Search queries hit Elasticsearch; stats/fetch-by-id queries hit Postgres directly

---

## Technology Choices & Trade-offs

| Concern | Choice | Rationale |
|---|---|---|
| Source of truth | **PostgreSQL 16** | ACID guarantees, JSONB for schema-flexible metrics, partial indexes for soft-delete, strong analytics support |
| Full-text search | **Elasticsearch 8** | Low-latency `multi_match` across description/title/author, rich filter DSL, near-real-time updates |
| Async event bus | **pg_notify** | Zero extra infrastructure locally; replaced by Kafka in production for durability |
| API framework | **FastAPI** | Async-native, OpenAPI auto-docs, Pydantic v2 integration |
| ORM | **SQLAlchemy 2 async** | Modern unit-of-work, works well with asyncpg |
| Migrations | **Alembic** | Auto-generate migrations from SQLAlchemy models; applied automatically on API startup |
| Observability | **Kibana** | Visualise the publications index without extra tooling |

### Why PostgreSQL + Elasticsearch (not one or the other)?

- **Client queries** (search by keyword, filter by author, fetch by ID) need low-latency and rich text scoring → Elasticsearch excels here.
- **R&D / batch analytics** (author engagement stats, full scans for AI training) need strong consistency, SQL joins, and aggregations → PostgreSQL excels here.
- Neither degrades the other: ES serves reads, PG serves writes and analytics, with an async worker bridging the two.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/publications` | Ingest a publication. Returns 201 (new) or 200 (updated). |
| `GET` | `/api/v1/publications/{id}` | Fetch a single publication from PostgreSQL by UUID |
| `GET` | `/api/v1/publications/search` | Full-text search via Elasticsearch |
| `GET` | `/api/v1/authors/{author_id}/stats` | Aggregate stats (total posts, avg engagement rate) |
| `GET` | `/api/v1/health` | Health check |

Interactive docs: **http://localhost:8000/api/v1/docs**

### Search query parameters

| Param | Type | Description |
|---|---|---|
| `q` | string | Full-text query (title, description, author_name) |
| `author_id` | string | Filter by author UUID |
| `published_from` / `published_to` | ISO datetime | Date range on `published_at` |
| `created_from` / `created_to` | ISO datetime | Date range on `created_at` |
| `metrics` | string (repeatable) | e.g. `views:gte:1000`, `engagement_rate:lte:5` |
| `limit` / `offset` | int | Pagination (default 20, max 100) |

---

## Data Quality Rules

### Hard fail (returns 422, publication not saved)

| Rule | Field |
|---|---|
| Must not be null | `publication_url`, `author_id`, `published_at` |
| Must be in range [0, 100] | `engagement_rate` (if provided) |
| Must not be in the future | `published_at` |

### Warning only (logs and continues)

| Rule | Field |
|---|---|
| Older than 24 hours | `published_at` |
| URL already exists (updates existing record) | `publication_url` |

---

## Engagement Rate Formula

```
engagement_rate = (likes + views + comments + shares) / follower_count_at_post
```

Computed automatically during ingestion and stored in the `metrics` JSONB blob.

---

## Schema Evolution – `platform` field migration plan

The challenge asks: *"Add an optional `platform` field (`instagram | tiktok | youtube | other`) to all future publications."*

### Why this is non-breaking

The `platform` column already exists in the database schema (`nullable`, `VARCHAR(100)`) and in the Elasticsearch mapping (`keyword`, no `null_value`). Older publications simply have `platform = null`.

### Zero-downtime rollout plan

1. **Database** – Already migrated (column exists as `nullable`). No action needed.
2. **Elasticsearch** – Mapping already includes `"platform": {"type": "keyword"}`. Existing docs without the field return no value on filter queries, which is the correct behaviour.
3. **API** – `PublicationCreate` already accepts `platform` as an optional field. Producers that don't send it get `null`.
4. **Backfill (optional)** – A one-off script can classify existing `publication_url` patterns (e.g. `instagram.com` → `instagram`) and update both Postgres and re-index to ES.
5. **New per-platform metrics** – Add keys inside the `metrics` JSONB. Because JSONB is schema-flexible and ES uses `dynamic: true` on the metrics object, no migration is needed for new metric keys.

---

## Running Locally (step-by-step)

```bash
# Prerequisites: Docker Desktop, Python 3.11+

cd project/

# Start data services only (faster iteration)
docker compose up -d postgres elasticsearch kibana

# Install deps for local API dev
pip install -r requirements.txt
pip install -r requirements-test.txt

# Run API locally (auto-applies migrations)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/publications \
ELASTICSEARCH_URL=http://localhost:9200 \
uvicorn app.main:app --reload --app-dir api

# Or run the full stack in Docker
docker compose up --build
```

---

## Running Tests

```bash
cd project/

# Unit tests (no external services needed)
pytest api/tests/test_validation.py api/tests/test_ingestion_service_unit.py api/tests/test_search_query_builder.py -v

# Integration tests (requires Postgres + Elasticsearch)
docker compose up -d postgres elasticsearch
pytest -v -m "integration"
```

---

## What I Would Do Differently With More Time

1. **Replace pg_notify with Kafka** – pg_notify is not durable (missed if worker is down); Kafka provides at-least-once delivery, replay, and consumer groups.
2. **Separate write and read models** – A dedicated ingestion service (write-only) and a search service (read-only) would scale independently.
3. **Bulk indexing** – Batch ES `_bulk` calls instead of per-event indexing for high-throughput scenarios.
4. **Backfill job** – A one-off script to sync historical Postgres data into ES after schema changes.
5. **Metrics & tracing** – Prometheus metrics (request latency, indexing lag) and OpenTelemetry tracing across API → Worker → ES.
6. **Auth & rate-limiting** – API key or JWT authentication; rate-limiting on the ingestion endpoint.
7. **Dead-letter queue** – Persist failed indexing events to a `failed_events` table for later replay.
8. **Kubernetes manifests** – HPA on the API deployment based on CPU/RPS; separate node pools for ES and the API.
