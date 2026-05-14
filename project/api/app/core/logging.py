from __future__ import annotations

import logging
from logging.config import dictConfig


class RequestIdFilter(logging.Filter):
	def filter(self, record: logging.LogRecord) -> bool:
		if not hasattr(record, "request_id"):
			record.request_id = "-"
		return True


def configure_logging(log_level: str) -> None:
	config = {
		"version": 1,
		"disable_existing_loggers": False,
		"filters": {
			"request_id": {"()": RequestIdFilter},
		},
		"formatters": {
			"default": {
				"format": "%(asctime)s %(levelname)s %(name)s %(message)s request_id=%(request_id)s",
			},
		},
		"handlers": {
			"console": {
				"class": "logging.StreamHandler",
				"formatter": "default",
				"filters": ["request_id"],
			}
		},
		"root": {
			"handlers": ["console"],
			"level": log_level.upper(),
		},
	}

	dictConfig(config)
