"""Ingestion worker: consumes Kafka, validates, writes to Postgres + OpenSearch + data lake."""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg
import boto3
from botocore.exceptions import ClientError
from aiokafka import AIOKafkaProducer
from prometheus_client import Counter, start_http_server
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.database import AsyncSessionLocal
from shared.kafka_utils import create_consumer, _serializer
from shared.models import Publication
from shared.search import (
    bulk_index,
    delete_from_index,
    ensure_index,
    get_opensearch_client,
)
from shared.validation import ValidationError, validate_publication

logger = logging.getLogger(__name__)


def _parse_dt(val):
    """Parse a datetime value, passthrough if already datetime, parse if string."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    dt = datetime.fromisoformat(val)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

PROCESSED = Counter("worker_processed_total", "Processed messages", ["result"])
DLQ_SENT = Counter("worker_dlq_total", "Messages sent to DLQ")
BATCHES = Counter("worker_batches_total", "Batches processed")


# ---------------------------------------------------------------------------
# Postgres upsert
# ---------------------------------------------------------------------------

async def upsert_batch(session: AsyncSession, records: list[dict]) -> dict[str, str]:
    """Upsert records. Returns {publication_url: publication_id}."""
    url_to_id: dict[str, str] = {}
    for rec in records:
        stmt = pg_insert(Publication).values(**rec)
        stmt = stmt.on_conflict_do_update(
            index_elements=["publication_url"],
            set_={
                "title": stmt.excluded.title,
                "author_name": stmt.excluded.author_name,
                "author_id": stmt.excluded.author_id,
                "published_at": stmt.excluded.published_at,
                "description": stmt.excluded.description,
                "media_url": stmt.excluded.media_url,
                "metrics": stmt.excluded.metrics,
                "engagement_rate": stmt.excluded.engagement_rate,
                "platform": stmt.excluded.platform,
                "created_at": stmt.excluded.created_at,
                "updated_at": stmt.excluded.updated_at,
                "deleted_at": stmt.excluded.deleted_at,
            },
        ).returning(Publication.publication_id, Publication.publication_url)
        result = await session.execute(stmt)
        row = result.fetchone()
        if row:
            url_to_id[str(row.publication_url)] = str(row.publication_id)
    await session.commit()
    return url_to_id


# ---------------------------------------------------------------------------
# Data lake export (MinIO / S3-compatible)
# ---------------------------------------------------------------------------

def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=f"http://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        region_name="us-east-1",
    )


def _ensure_bucket(s3) -> None:
    try:
        s3.head_bucket(Bucket=settings.minio_bucket)
    except ClientError:
        s3.create_bucket(Bucket=settings.minio_bucket)
        logger.info("Created MinIO bucket '%s'", settings.minio_bucket)


def _export_to_lake_sync(records: list[dict]) -> None:
    s3 = _get_s3_client()
    _ensure_bucket(s3)
    now = datetime.now(timezone.utc)
    key = (
        f"publications/year={now.year}/month={now.month:02d}/"
        f"day={now.day:02d}/batch_{int(now.timestamp() * 1000)}.jsonl.gz"
    )
    body = "\n".join(json.dumps(r, default=str) for r in records)
    compressed = gzip.compress(body.encode("utf-8"))
    s3.put_object(Bucket=settings.minio_bucket, Key=key, Body=compressed)
    logger.info("Exported %d records to lake: %s", len(records), key)


async def export_to_lake(records: list[dict]) -> None:
    if not settings.lake_export_enabled:
        return
    try:
        await asyncio.to_thread(_export_to_lake_sync, records)
    except Exception:
        logger.exception("Lake export failed (non-fatal)")


# ---------------------------------------------------------------------------
# Core batch processing
# ---------------------------------------------------------------------------

async def process_batch(
    messages: list[dict],
    os_client,
    dlq_producer: AIOKafkaProducer,
) -> None:
    valid_records: list[dict] = []

    for msg in messages:
        try:
            warnings, engagement_rate = validate_publication(msg)
            for w in warnings:
                if "older than 24" not in w.message:
                    logger.warning("Validation warning: %s", w.message)

            record = {
                "publication_id": uuid4(),
                "publication_url": str(msg["publication_url"]),
                "title": msg["title"],
                "author_name": msg["author_name"],
                "author_id": msg["author_id"],
                "published_at": _parse_dt(msg["published_at"]),
                "description": msg["description"],
                "media_url": str(msg["media_url"]),
                "metrics": msg["metrics"],
                "engagement_rate": engagement_rate,
                "platform": msg.get("platform"),
                "created_at": _parse_dt(msg["created_at"]),
                "updated_at": _parse_dt(msg.get("updated_at")),
                "deleted_at": _parse_dt(msg.get("deleted_at")),
            }
            valid_records.append(record)
            PROCESSED.labels(result="valid").inc()

        except ValidationError as e:
            PROCESSED.labels(result="hard_fail").inc()
            logger.error(
                "Hard-fail: %s | url=%s", e, msg.get("publication_url", "?")
            )
            try:
                await dlq_producer.send_and_wait(
                    settings.kafka_dlq_topic,
                    value={"error": str(e), "data": msg},
                )
                DLQ_SENT.inc()
            except Exception:
                logger.exception("Failed to send to DLQ")

        except Exception:
            PROCESSED.labels(result="error").inc()
            logger.exception("Unexpected error validating message")

    if not valid_records:
        return

    # -- Postgres upsert with retries ----------------------------------------
    url_to_id: dict[str, str] = {}
    for attempt in range(settings.max_retries):
        try:
            async with AsyncSessionLocal() as session:
                url_to_id = await upsert_batch(session, valid_records)
            break
        except Exception as e:
            if attempt < settings.max_retries - 1:
                logger.warning("Postgres upsert attempt %d failed: %s", attempt + 1, e)
                await asyncio.sleep(2**attempt)
            else:
                logger.error("Postgres upsert failed after %d retries", settings.max_retries)
                raise

    # -- OpenSearch indexing ---------------------------------------------------
    os_actions: list[dict] = []
    for rec in valid_records:
        pub_url = rec["publication_url"]
        pub_id = url_to_id.get(pub_url, str(rec["publication_id"]))

        if rec.get("deleted_at"):
            await delete_from_index(os_client, pub_id)
        else:
            doc = {k: v for k, v in rec.items() if v is not None}
            doc["publication_id"] = pub_id
            os_actions.append({"_id": pub_id, "_source": doc})

    try:
        await bulk_index(os_client, os_actions)
    except Exception:
        logger.exception("OpenSearch bulk index failed (non-fatal)")

    # -- Data lake export -----------------------------------------------------
    lake_records = [
        {**rec, "publication_id": url_to_id.get(rec["publication_url"], str(rec["publication_id"]))}
        for rec in valid_records
    ]
    await export_to_lake(lake_records)


# ---------------------------------------------------------------------------
# Startup helpers
# ---------------------------------------------------------------------------

async def wait_for_postgres() -> None:
    for i in range(30):
        try:
            conn = await asyncpg.connect(
                host=settings.postgres_host,
                port=settings.postgres_port,
                user=settings.postgres_user,
                password=settings.postgres_password,
                database=settings.postgres_db,
            )
            await conn.close()
            logger.info("Postgres ready")
            return
        except Exception:
            logger.info("Waiting for Postgres (%d/30)…", i + 1)
            await asyncio.sleep(2)
    raise RuntimeError("Postgres not available after 60 s")


async def wait_for_opensearch(os_client) -> None:
    for i in range(30):
        try:
            await os_client.info()
            logger.info("OpenSearch ready")
            return
        except Exception:
            logger.info("Waiting for OpenSearch (%d/30)…", i + 1)
            await asyncio.sleep(2)
    raise RuntimeError("OpenSearch not available after 60 s")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    logger.info("Starting ingestion worker …")

    start_http_server(9090)

    await wait_for_postgres()

    os_client = get_opensearch_client()
    await wait_for_opensearch(os_client)
    await ensure_index(os_client)

    consumer = await create_consumer()
    dlq_producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=_serializer,
    )
    await dlq_producer.start()

    logger.info("Worker ready, consuming '%s'", settings.kafka_topic)

    try:
        while True:
            batch = await consumer.getmany(
                timeout_ms=int(settings.batch_timeout_seconds * 1000),
                max_records=settings.batch_size,
            )
            messages: list[dict] = []
            for _tp, records in batch.items():
                for record in records:
                    messages.append(record.value)

            if messages:
                logger.info("Processing batch of %d messages", len(messages))
                try:
                    await process_batch(messages, os_client, dlq_producer)
                except Exception:
                    logger.exception("Batch processing failed, skipping commit")
                    continue
                await consumer.commit()
                BATCHES.inc()
    except asyncio.CancelledError:
        pass
    finally:
        await consumer.stop()
        await dlq_producer.stop()
        await os_client.close()
        logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(run())
