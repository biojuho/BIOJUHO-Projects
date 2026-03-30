from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)


def _workspace_candidates() -> list[Path]:
    candidates: list[Path] = []
    for parent in Path(__file__).resolve().parents:
        if (parent / "shared" / "__init__.py").exists():
            candidates.append(parent)
    return candidates


@contextmanager
def _temporary_sys_path(path: Path | None) -> Iterator[None]:
    if path is None or str(path) in sys.path:
        yield
        return
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        try:
            sys.path.remove(str(path))
        except ValueError:
            pass


@lru_cache(maxsize=1)
def resolve_shared_fact_check() -> tuple[Any | None, Any | None, Exception | None]:
    fact_check_result = None
    verify_text_against_sources = None
    last_error: Exception | None = None

    for candidate in [None, *_workspace_candidates()]:
        with _temporary_sys_path(candidate):
            try:
                from shared.fact_check import FactCheckResult as imported_result
                from shared.fact_check import verify_text_against_sources as imported_verify
            except ImportError as exc:
                last_error = exc
                continue
            fact_check_result = imported_result
            verify_text_against_sources = imported_verify
            last_error = None
            break

    if verify_text_against_sources is None:
        logger.debug(
            "shared.fact_check unavailable. Fact-checking will be skipped unless the shared package is importable."
        )

    return fact_check_result, verify_text_against_sources, last_error
