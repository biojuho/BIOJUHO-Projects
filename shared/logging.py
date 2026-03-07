"""shared.logging - Unified structured logging configuration."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def setup_logger(
    name: str,
    *,
    level: int = logging.INFO,
    log_file: str | Path | None = None,
) -> logging.Logger:
    """Create a consistently formatted logger for any project.

    Args:
        name: Logger name (typically project name like 'agriguard' or 'news_bot')
        level: Logging level (default: INFO)
        log_file: Optional file path for file handler

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)-18s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # Optional file handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
