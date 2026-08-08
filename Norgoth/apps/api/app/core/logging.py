"""Application logging configuration."""

import logging.config
from typing import Any


def configure_logging(log_level: str) -> None:
    """Configure application logging using the Python standard library."""

    configuration: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": ("%(asctime)s %(levelname)s %(name)s %(process)d %(message)s"),
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": log_level,
            },
        },
        "root": {
            "handlers": ["default"],
            "level": log_level,
        },
    }

    logging.config.dictConfig(configuration)
