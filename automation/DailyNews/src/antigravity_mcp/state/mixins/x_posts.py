from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from antigravity_mcp.domain.models import ChannelDraft, ContentReport, PipelineRun
from antigravity_mcp.state.base import _DBProviderBase
from antigravity_mcp.state.events import utc_now_iso

try:
    from shared.llm.config import MODEL_COSTS as _SHARED_MODEL_COSTS
except ImportError:
    _SHARED_MODEL_COSTS: dict[str, tuple[float, float]] = {}

_DEFAULT_MODEL_COSTS: dict[str, tuple[float, float]] = {
    "claude-3-haiku-20240307": (0.25, 1.25),
    "claude-haiku-4-5-20251001": (0.8, 4.0),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "deepseek-chat": (0.14, 0.28),
    "gemini-2.5-flash": (0.0, 0.0),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash-preview-04-17": (0.0, 0.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "grok-3-mini-fast": (0.3, 0.5),
}
_MODEL_COSTS = {**_DEFAULT_MODEL_COSTS, **_SHARED_MODEL_COSTS}

def _estimate_cached_response_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    input_cost, output_cost = _MODEL_COSTS.get(model_name, (0.25, 1.25))
    return (input_tokens * input_cost + output_tokens * output_cost) / 1_000_000

def _json_default(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, set):
        return list(value)
    if hasattr(value, "__dict__"):
        return vars(value)
    return str(value)


class _XPostMixin(_DBProviderBase):
    """Persistent daily post counter for X (Twitter) publishing."""

    def get_x_post_count(self, post_date: str) -> int:
        """Return the number of posts made on the given date (YYYY-MM-DD)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT post_count FROM x_daily_posts WHERE post_date = ?",
                (post_date,),
            ).fetchone()
        return int(row["post_count"]) if row else 0

    def increment_x_post_count(self, post_date: str) -> int:
        """Increment and return the post count for the given date."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO x_daily_posts (post_date, post_count)
                VALUES (?, 1)
                ON CONFLICT(post_date) DO UPDATE SET post_count = post_count + 1
                """,
                (post_date,),
            )
            row = conn.execute(
                "SELECT post_count FROM x_daily_posts WHERE post_date = ?",
                (post_date,),
            ).fetchone()
        return int(row["post_count"]) if row else 1

    def prune_old_x_posts(self, keep_days: int = 7) -> int:
        """Remove post count entries older than *keep_days*."""
        cutoff = (datetime.now(UTC) - timedelta(days=keep_days)).strftime("%Y-%m-%d")
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM x_daily_posts WHERE post_date < ?", (cutoff,))
        return cursor.rowcount
