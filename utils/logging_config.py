"""
Logging configuration using structlog for structured logs.
Supports JSON and text formats with rotation.
"""
import logging
import sys
from pathlib import Path
from typing import Any, Dict

import structlog


def configure_logging(
    level: str = "INFO",
    format_type: str = "json",
    log_dir: Path = Path("./logs"),
    max_bytes: int = 10_485_760,  # 10MB
    backup_count: int = 5
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Output format ("json" or "text")
        log_dir: Directory for log files
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
    """
    # Ensure log directory exists
    log_dir.mkdir(parents=True, exist_ok=True)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.dev.ConsoleRenderer() if format_type == "text"
            else structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True
    )

    # Configure root logger for standard logging
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if format_type == "text":
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        formatter = None

    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    # Add file handlers for rotation
    file_handler = logging.FileHandler(
        log_dir / "email_agent.log",
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    # Create RotatingFileHandler
    from logging.handlers import RotatingFileHandler
    rotating_handler = RotatingFileHandler(
        log_dir / "email_agent.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    rotating_handler.setLevel(level)
    rotating_handler.setFormatter(formatter)

    root_logger.addHandler(rotating_handler)

    # Configure specific loggers
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("pyrogram").setLevel(logging.WARNING)

    logger = structlog.get_logger()
    logger.info("Logging configured", level=level, format=format_type)


def get_logger(name: str = __name__) -> Any:
    """
    Get a structlog logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Structlog bound logger
    """
    return structlog.get_logger(name)
