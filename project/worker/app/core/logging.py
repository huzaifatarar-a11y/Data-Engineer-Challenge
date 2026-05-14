from __future__ import annotations

import logging
from logging.config import dictConfig


def configure_logging(log_level: str) -> None:
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            }
        },
        "root": {
            "handlers": ["console"],
            "level": log_level.upper(),
        },
    }

    dictConfig(config)
