from __future__ import annotations

import logging
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _workspace_candidates() -> list[Path]:
    candidates: list[Path] = []
    for parent in Path(__file__).resolve().parents:
        if (parent / "shared" / "__init__.py").exists():
            candidates.append(parent)
    return candidates


@lru_cache(maxsize=1)
def resolve_shared_llm() -> tuple[Any | None, Any | None, Any | None, Exception | None]:
    task_tier = None
    llm_policy = None
    get_client = None
    last_error: Exception | None = None

    for candidate in [None, *_workspace_candidates()]:
        added_path = False
        if candidate is not None and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
            added_path = True
        try:
            from shared.llm import LLMPolicy as imported_policy
            from shared.llm import TaskTier as imported_task_tier
            from shared.llm import get_client as imported_get_client
        except ImportError as exc:
            last_error = exc
            if added_path:
                try:
                    sys.path.remove(str(candidate))
                except ValueError:
                    pass
            continue
        task_tier = imported_task_tier
        llm_policy = imported_policy
        get_client = imported_get_client
        last_error = None
        break

    if task_tier is None or get_client is None:
        logger.error(
            "shared.llm unavailable. Install/configure the shared package or expose the workspace root on PYTHONPATH. "
            "LLM analysis will NOT run — only fallback summaries will be generated."
        )

    return task_tier, llm_policy, get_client, last_error
