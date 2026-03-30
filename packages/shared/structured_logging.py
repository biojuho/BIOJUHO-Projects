"""
shared.structured_logging — JSON structured logging via structlog.

Configures structlog to emit JSON lines suitable for Loki/Promtail
ingestion.  Falls back to stdlib logging when structlog is not installed.

Usage::
    from shared.structured_logging import setup_logging, get_logger

    setup_logging(service_name="agriguard")
    log = get_logger()
    log.info("request_handled", path="/health", status=200, duration_ms=12)
"""

from __future__ import annotations

import logging
import sys

try:
    import structlog

    _STRUCTLOG_AVAILABLE = True
except ImportError:
    _STRUCTLOG_AVAILABLE = False


def setup_logging(
    *,
    service_name: str = "app",
    level: str = "INFO",
    json_output: bool = True,
) -> None:
    """Configure structlog with JSON rendering for Loki compatibility.

    Safe to call when structlog is not installed — falls back to stdlib.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    if not _STRUCTLOG_AVAILABLE:
        logging.basicConfig(
            level=log_level,
            format=f"%(asctime)s [{service_name}] %(levelname)s %(name)s: %(message)s",
            stream=sys.stderr,
        )
        return

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.EventRenamer("msg"),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Bind service name to all loggers
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str | None = None):
    """Return a structlog logger (or stdlib logger as fallback)."""
    if _STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name) if name else structlog.get_logger()
    return logging.getLogger(name or __name__)
