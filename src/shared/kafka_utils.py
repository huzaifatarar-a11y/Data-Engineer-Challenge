from __future__ import annotations

import json
import logging
from typing import Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from shared.config import settings

logger = logging.getLogger(__name__)


def _serializer(v: object) -> bytes:
    return json.dumps(v, default=str).encode("utf-8")


def _deserializer(v: bytes) -> dict:
    return json.loads(v.decode("utf-8"))


async def create_producer() -> AIOKafkaProducer:
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=_serializer,
        acks="all",
        max_batch_size=16384 * 4,
        linger_ms=50,
        retry_backoff_ms=100,
    )
    await producer.start()
    logger.info("Kafka producer connected to %s", settings.kafka_bootstrap_servers)
    return producer


async def create_consumer(group_id: Optional[str] = None) -> AIOKafkaConsumer:
    consumer = AIOKafkaConsumer(
        settings.kafka_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=group_id or settings.kafka_consumer_group,
        value_deserializer=_deserializer,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        max_poll_records=settings.batch_size,
    )
    await consumer.start()
    logger.info("Kafka consumer subscribed to %s", settings.kafka_topic)
    return consumer
