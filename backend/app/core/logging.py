import logging.config


def configure_logging(log_level: str) -> None:
    normalized_level = log_level.upper()

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                }
            },
            "root": {"level": normalized_level, "handlers": ["console"]},
            "loggers": {
                "uvicorn": {"level": normalized_level, "handlers": ["console"]},
                "uvicorn.error": {
                    "level": normalized_level,
                    "handlers": ["console"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": normalized_level,
                    "handlers": ["console"],
                    "propagate": False,
                },
            },
        }
    )
