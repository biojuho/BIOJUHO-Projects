"""
BioLinker - Structured Logging Configuration
JSON-formatted structured logging via structlog.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

try:
    import structlog
except ImportError:  # pragma: no cover - used in lean smoke environments
    structlog = None  # type: ignore[assignment]


class _FallbackBoundLogger:
    def __init__(self, logger: logging.Logger, context: dict[str, Any] | None = None) -> None:
        self._logger = logger
        self._context = context or {}

    def bind(self, **kwargs: Any) -> "_FallbackBoundLogger":
        return _FallbackBoundLogger(self._logger, {**self._context, **kwargs})

    def _format(self, event: str, *args: Any, **kwargs: Any) -> str:
        message = event
        if args:
            try:
                message = event % args
            except TypeError:
                message = " ".join([event, *(str(arg) for arg in args)])

        merged = {**self._context, **kwargs}
        if merged:
            fields = " ".join(f"{key}={value!r}" for key, value in sorted(merged.items()))
            message = f"{message} | {fields}"
        return message

    def debug(self, event: str, *args: Any, **kwargs: Any) -> None:
        exc_info = kwargs.pop("exc_info", False)
        self._logger.debug(self._format(event, *args, **kwargs), exc_info=exc_info)

    def info(self, event: str, *args: Any, **kwargs: Any) -> None:
        exc_info = kwargs.pop("exc_info", False)
        self._logger.info(self._format(event, *args, **kwargs), exc_info=exc_info)

    def warning(self, event: str, *args: Any, **kwargs: Any) -> None:
        exc_info = kwargs.pop("exc_info", False)
        self._logger.warning(self._format(event, *args, **kwargs), exc_info=exc_info)

    def error(self, event: str, *args: Any, **kwargs: Any) -> None:
        exc_info = kwargs.pop("exc_info", False)
        self._logger.error(self._format(event, *args, **kwargs), exc_info=exc_info)

    def exception(self, event: str, *args: Any, **kwargs: Any) -> None:
        self._logger.exception(self._format(event, *args, **kwargs))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._logger, name)


def setup_logging(*, json_output: bool = True, log_level: str = "INFO") -> None:
    """Configure structlog with JSON output for production or console for dev."""
    handler = logging.StreamHandler(sys.stdout)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if structlog is None:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    else:
        shared_processors: list[structlog.types.Processor] = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
        ]

        if json_output:
            renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
        else:
            renderer = structlog.dev.ConsoleRenderer()

        structlog.configure(
            processors=[
                *shared_processors,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    renderer,
                ],
            )
        )

    for noisy in ("chromadb", "httpcore", "httpx", "urllib3", "firebase_admin"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> Any:
    """Return a bound logger, falling back to stdlib logging when structlog is absent."""
    if structlog is None:
        return _FallbackBoundLogger(logging.getLogger(name))
    return structlog.get_logger(name)
