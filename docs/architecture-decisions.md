# Architecture Decisions and Scaling

## My Goals

- Support billions of daily publications with two distinct workloads.
- Low-latency, high-frequency reads for client queries (search, filters, single item).
- Long-running, read-heavy internal analytics without degrading client reads.
- Provide a platform that is simple for downstream teams to use.
- Ensure data quality and schema evolution without downtime.

## High-Level Architecture

The system separates the ingestion path from the read paths, and separates search from the transactional database.

- Write path: Producer -> API -> Kafka (Redpanda) -> Worker(s) -> Postgres + OpenSearch + MinIO.
- Read path: API reads from Postgres for point lookups and stats, and from OpenSearch for search.
- Analytics path: R and D reads from MinIO data lake instead of the OLTP database.

This pattern avoids mixing search and analytics loads with transactional workloads.

## Component Decisions

### 1. Kafka (Redpanda) as the Streaming Buffer

Why it is needed:
- Decouples HTTP ingestion from storage writes, so the API can respond quickly.
- Smooths bursty traffic and provides backpressure safety.
- Enables horizontal scaling via consumer groups.
- Provides at-least-once delivery; combined with idempotent upserts, this yields exactly-once effects.

Why Redpanda specifically:
- Kafka-compatible, but runs as a single binary with lower resource usage.
- Better fit for local reproducibility while preserving a production-grade interface.

Why not write directly to Postgres and OpenSearch from the API:
- Ties ingestion latency to database and index latency.
- Makes the API fragile under spikes.
- Harder to scale independently.

### 2. Postgres as Source of Truth

Why it is needed:
- Strong consistency, constraints, and transactional integrity.
- Supports reliable updates and idempotent upserts by URL.
- Best fit for point lookups and deterministic aggregation (author stats).

Why not use only OpenSearch:
- OpenSearch is optimized for search, not transactional updates.
- Consistency and data integrity checks are weaker compared to Postgres.
- Complex queries for accurate stats are not its primary strength.

### 2.1 Author Stats Computed at Query Time

Why they are not stored:
- Ensures stats are always consistent with the source of truth (including deletions).
- Avoids extra tables, dual-writes, and reconciliation logic.
- Keeps ingestion simple while the stats query remains cheap at current scale.

When to materialize later:
- If author stats become a hot path, add a materialized table updated by workers or a scheduled job.
- For batch reporting, compute aggregates in the data lake and serve from there.

### 3. OpenSearch for Full-Text Search

Why it is needed:
- Full-text search with relevance scoring and fuzziness.
- Efficient filtering on author_id and time ranges while searching title or description.
- Keeps expensive search workloads out of the transactional database.

Why not use only Postgres:
- Full-text search is possible in Postgres, but at scale it competes with OLTP workloads.
- Search relevance and fuzzy matching are much stronger and cheaper in OpenSearch.

Data duplication concern:
- Data is duplicated intentionally, but each store serves a distinct workload.
- Postgres is the single source of truth. OpenSearch is a derived index used for search.

### 4. MinIO as Data Lake (S3-Compatible)

Why it is needed:
- Provides low-cost, scalable storage for batch analytics.
- Prevents long-running analytics from overloading Postgres or OpenSearch.
- Allows R and D to use Spark, DuckDB, or Polars directly.

Why not run analytics directly on Postgres or OpenSearch:
- Heavy scans can degrade latency for client-facing reads.
- Data lake storage is the standard pattern for large-scale batch workloads.

### 5. FastAPI for the Internal Data API

Why it is needed:
- Lightweight, async, and provides OpenAPI documentation out of the box.
- Integrates cleanly with Pydantic for schema validation.
- Enables strict validation for the ingestion endpoint.

### 6. Worker Service for Ingestion

Why it is needed:
- Centralizes validation, enrichment, and storage writes.
- Batches work for efficiency (fewer database calls, fewer OpenSearch requests).
- Isolates failures from the API and allows retries and DLQ logic.

### 7. Two Kafka Consumers (Two Worker Replicas)

Why there are two:
- Demonstrates horizontal scaling with Kafka consumer groups.
- Each worker is in the same group; Kafka partitions are shared between them.
- Raises throughput and reduces processing latency under load.

Why not a single worker:
- Single worker becomes a bottleneck at high throughput.
- Horizontal scalability is a core requirement of the challenge.

### 8. Dead Letter Queue (DLQ)

Why it is needed:
- Hard-fail records must not be lost.
- A DLQ allows inspection, alerting, and reprocessing later.
- Prevents malformed data from blocking the pipeline.

```docker compose exec redpanda rpk topic consume publications-dlq```
### 9. Prometheus Metrics

Why it is needed:
- Exposes ingestion and API performance data (rates, errors, latency).
- Provides observability needed for scaling and debugging.

### 10. Alembic Migrations

Why it is needed:
- Enables controlled, reproducible schema changes.
- Supports zero-downtime evolution by applying safe migrations.

### 11. Docker Compose

Why it is needed:
- Reproducible local environment with all dependencies.
- Mirrors a multi-service production layout while keeping setup simple.

## Scaling Strategy

### Ingestion Path (API -> Kafka -> Workers)

- Increase Kafka partitions to raise parallelism.
- Increase worker replicas to match the number of partitions.
- Tune batch sizes and poll intervals for throughput vs latency.
- Use backpressure on the API when Kafka is unavailable.
- Consider a schema registry to prevent breaking changes.

### Postgres Scaling

- Partition tables by time (published_at) for billions of rows.
- Add read replicas for reporting and stats queries.
- Use connection pooling (pgbouncer) to limit connections.
- Consider archiving old partitions to the data lake.
- Use partial and GIN indexes for selective queries if needed.

### OpenSearch Scaling

- Increase shards and replicas for search throughput and resiliency.
- Separate hot and cold tiers for older data.
- Use index lifecycle management to control segment and storage usage.
- Consider CDC from Postgres to reduce dual-write risk at scale.

### Data Lake Scaling (MinIO / S3)

- Move from JSONL to Parquet for analytics efficiency.
- Partition by date and platform to optimize queries.
- Use compaction jobs to reduce small-file overhead.

### API Scaling

- Run multiple stateless API replicas behind a load balancer.
- Use async IO and proper request timeouts.
- Add caching for hot lookups if needed.

### Reliability and Operations

- Monitor consumer lag, DLQ size, and ingestion throughput.
- Set alerts on error rates, latency percentiles, and backlog growth.
- Implement retry policies and circuit breakers for downstream services.

## Summary of Key Trade-offs

- Data duplication is deliberate to separate search from transactional workloads.
- Eventual consistency on writes is accepted to improve write throughput.
- OpenSearch provides advanced search features that Postgres cannot match at scale.
- The data lake isolates analytics from live client queries.

## Database Migration Guide

Goal: evolve schemas without downtime while ingestion and reads continue.

1. Make backward-compatible changes first
- Add nullable columns or new tables with defaults that do not rewrite large tables.
- Use additive changes; avoid destructive changes in the first rollout.

2. Run migrations safely
- Use Alembic to apply changes in order.
- Create indexes concurrently for large tables in production.

3. Deploy writers before readers
- Deploy workers that can write the new fields.
- Deploy API changes next so reads include new fields when present.
- Deploy producer changes last so new data flows in.

4. Backfill and validate
- Backfill new columns in batches if needed.
- Validate by comparing record counts and sampled results.

5. Enforce stricter constraints later
- After backfill, add constraints or change NULLability if required.
- Keep a rollback plan (migration downgrade or feature flag).

6. Rebuild derived indexes if needed
- If mappings change, reindex OpenSearch from Postgres or the data lake.