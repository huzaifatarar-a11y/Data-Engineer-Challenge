from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "publications"
    postgres_user: str = "platform"
    postgres_password: str = "platform"

    kafka_bootstrap_servers: str = "redpanda:9092"
    kafka_topic: str = "publications"
    kafka_consumer_group: str = "ingestion-workers"
    kafka_dlq_topic: str = "publications-dlq"

    opensearch_host: str = "opensearch"
    opensearch_port: int = 9200

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "publications-lake"
    lake_export_enabled: bool = True

    batch_size: int = 100
    batch_timeout_seconds: float = 2.0
    max_retries: int = 3

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
