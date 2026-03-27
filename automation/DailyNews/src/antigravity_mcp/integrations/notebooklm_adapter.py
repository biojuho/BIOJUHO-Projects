"""NotebookLM adapter — deep research enrichment via Google NotebookLM API.

v2.0: Thin wrapper around notebooklm_automation.adapters.dailynews.
All logic now lives in the unified package; this module re-exports for
backward compatibility.

Provides two main capabilities:
B) Per-category deep research: create notebook from article URLs, ask analytical questions
C) Weekly digest: aggregate a week's reports into a single comprehensive notebook
"""
from __future__ import annotations

import logging
from typing import Any

from notebooklm_automation.adapters.dailynews import (
    CATEGORY_RESEARCH_PROMPTS,
    DailyNewsAdapter,
    get_dailynews_adapter,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────
#  Re-export aliases for backward compatibility
# ──────────────────────────────────────────────────

# The class is now `DailyNewsAdapter` but existed as `NotebookLMAdapter`
NotebookLMAdapter = DailyNewsAdapter

# Singleton getter
def get_notebooklm_adapter() -> DailyNewsAdapter:
    """Legacy alias for get_dailynews_adapter()."""
    return get_dailynews_adapter()


__all__ = [
    "NotebookLMAdapter",
    "DailyNewsAdapter",
    "get_notebooklm_adapter",
    "get_dailynews_adapter",
    "CATEGORY_RESEARCH_PROMPTS",
]
