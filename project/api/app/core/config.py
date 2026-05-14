from __future__ import annotations

from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		case_sensitive=False,
	)

	app_name: str = Field(default="publications-api", alias="APP_NAME")
	app_env: str = Field(default="local", alias="APP_ENV")
	app_version: str = Field(default="0.1.0", alias="APP_VERSION")
	log_level: str = Field(default="INFO", alias="LOG_LEVEL")

	api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")

	cors_origins: List[str] = Field(default_factory=list, alias="CORS_ORIGINS")

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
	elasticsearch_username: str | None = Field(default=None, alias="ELASTICSEARCH_USERNAME")
	elasticsearch_password: str | None = Field(default=None, alias="ELASTICSEARCH_PASSWORD")
	elasticsearch_request_timeout: int = Field(
		default=10,
		alias="ELASTICSEARCH_REQUEST_TIMEOUT",
	)
	elasticsearch_max_retries: int = Field(default=3, alias="ELASTICSEARCH_MAX_RETRIES")
	elasticsearch_retry_on_timeout: bool = Field(
		default=True,
		alias="ELASTICSEARCH_RETRY_ON_TIMEOUT",
	)
	indexing_channel: str = Field(
		default="publication-indexing",
		alias="INDEXING_CHANNEL",
	)

	@field_validator("cors_origins", mode="before")
	@classmethod
	def split_cors_origins(cls, value: str | List[str]) -> List[str]:
		if isinstance(value, list):
			return value
		if not value:
			return []
		return [item.strip() for item in value.split(",") if item.strip()]
