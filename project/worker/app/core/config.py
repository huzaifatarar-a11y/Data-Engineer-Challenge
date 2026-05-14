from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = Field(default="publications-worker", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@postgres:5432/publications",
        alias="DATABASE_URL",
    )

    elasticsearch_url: str = Field(
        default="http://elasticsearch:9200",
        alias="ELASTICSEARCH_URL",
    )
    elasticsearch_index: str = Field(default="publications", alias="ELASTICSEARCH_INDEX")
    elasticsearch_alias: str = Field(default="publications-read", alias="ELASTICSEARCH_ALIAS")
    elasticsearch_request_timeout: int = Field(
        default=10,
        alias="ELASTICSEARCH_REQUEST_TIMEOUT",
    )
    elasticsearch_max_retries: int = Field(default=3, alias="ELASTICSEARCH_MAX_RETRIES")
    elasticsearch_retry_on_timeout: bool = Field(
        default=True,
        alias="ELASTICSEARCH_RETRY_ON_TIMEOUT",
    )

    indexing_channel: str = Field(default="publication-indexing", alias="INDEXING_CHANNEL")

    worker_concurrency: int = Field(default=2, alias="WORKER_CONCURRENCY")
    worker_max_retries: int = Field(default=5, alias="WORKER_MAX_RETRIES")
    worker_retry_base_seconds: float = Field(default=1.0, alias="WORKER_RETRY_BASE_SECONDS")
