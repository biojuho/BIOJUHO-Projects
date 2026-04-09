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


class _ArticleMixin(_DBProviderBase):
    """Methods for the ``article_cache`` table."""

    def has_seen_article(self, *, link: str, category: str, window_name: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM article_cache
                WHERE link = ? AND category = ? AND window_name = ?
                LIMIT 1
                """,
                (link, category, window_name),
            ).fetchone()
        return row is not None

    def get_seen_links(self, *, links: list[str], category: str, window_name: str) -> set[str]:
        """Batch check which links have already been seen. Returns the set of known links."""
        if not links:
            return set()
        seen: set[str] = set()
        with self._connect() as connection:
            # SQLite variable limit is 999; process in chunks
            chunk_size = 900
            for i in range(0, len(links), chunk_size):
                chunk = links[i : i + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                rows = connection.execute(
                    f"""
                    SELECT link FROM article_cache
                    WHERE link IN ({placeholders}) AND category = ? AND window_name = ?
                    """,
                    (*chunk, category, window_name),
                ).fetchall()
                seen.update(row["link"] for row in rows)
        return seen

    def prune_old_articles(self, days: int = 30) -> int:
        """Delete article_cache entries older than *days*. Returns count of removed rows."""
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM article_cache WHERE first_seen_at < ?", (cutoff,))
        return cursor.rowcount

    def record_article(
        self,
        *,
        link: str,
        source: str,
        category: str,
        window_name: str,
        notion_page_id: str | None,
        run_id: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO article_cache(
                    link, category, window_name, source, first_seen_at, notion_page_id, last_run_id
                )
                VALUES(
                    ?, ?, ?, ?,
                    COALESCE((SELECT first_seen_at FROM article_cache WHERE link = ? AND category = ? AND window_name = ?), ?),
                    ?, ?
                )
                """,
                (
                    link,
                    category,
                    window_name,
                    source,
                    link,
                    category,
                    window_name,
                    utc_now_iso(),
                    notion_page_id,
                    run_id,
                ),
            )
