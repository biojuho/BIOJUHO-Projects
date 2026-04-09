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


class _CacheMixin(_DBProviderBase):
    """Methods for ``llm_cache``, ``feed_etag_cache``, and token usage stats."""

    def get_cached_llm_response(self, prompt_hash: str) -> str | None:
        """Return cached LLM response text or None if cache miss / expired."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT response_text
                FROM llm_cache
                WHERE prompt_hash = ? AND (expires_at IS NULL OR expires_at > ?)
                """,
                (prompt_hash, now),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE llm_cache SET cache_hits = COALESCE(cache_hits, 0) + 1 WHERE prompt_hash = ?",
                (prompt_hash,),
            )
        return row["response_text"]

    def increment_llm_cache_hits(self, prompt_hash: str) -> None:
        """Increment cache_hits counter for a prompt_hash (e.g. when L1 in-memory cache is hit)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE llm_cache SET cache_hits = COALESCE(cache_hits, 0) + 1 WHERE prompt_hash = ?",
                (prompt_hash,),
            )

    def put_llm_cache(
        self,
        prompt_hash: str,
        response_text: str,
        model_name: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        ttl_hours: int = 24,
    ) -> None:
        """Store an LLM response in cache with optional TTL."""
        now = datetime.now(UTC)
        expires = (now + timedelta(hours=ttl_hours)).isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO llm_cache
                   (prompt_hash, response_text, model_name, input_tokens, output_tokens, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (prompt_hash, response_text, model_name, input_tokens, output_tokens, now.isoformat(), expires),
            )

    def prune_llm_cache(self) -> int:
        """Remove expired cache entries. Returns count of deleted rows."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM llm_cache WHERE expires_at IS NOT NULL AND expires_at <= ?", (now,))
        return cursor.rowcount

    def get_feed_etag(self, url: str) -> tuple[str | None, str | None]:
        """Return (etag, last_modified) for a cached feed URL."""
        with self._connect() as conn:
            row = conn.execute("SELECT etag, last_modified FROM feed_etag_cache WHERE url = ?", (url,)).fetchone()
        if row:
            return row["etag"], row["last_modified"]
        return None, None

    def put_feed_etag(self, url: str, etag: str | None, last_modified: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO feed_etag_cache (url, etag, last_modified, last_fetched_at)
                   VALUES (?, ?, ?, ?)""",
                (url, etag, last_modified, utc_now_iso()),
            )

    def get_token_usage_stats(self, hours: int = 24) -> dict:
        """Aggregate token usage from LLM cache entries within the given time window."""
        cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT model_name, input_tokens, output_tokens, COALESCE(cache_hits, 0) AS cache_hits
                FROM llm_cache
                WHERE created_at >= ?
                """,
                (cutoff,),
            ).fetchall()
        total_input = sum(int(row["input_tokens"] or 0) for row in rows)
        total_output = sum(int(row["output_tokens"] or 0) for row in rows)
        cache_hits = sum(int(row["cache_hits"] or 0) for row in rows)
        estimated_cost = 0.0
        avoided_cost = 0.0
        cost_by_model: dict[str, float] = {}
        for row in rows:
            model_name = row["model_name"] or "unknown"
            row_cost = _estimate_cached_response_cost(
                model_name,
                int(row["input_tokens"] or 0),
                int(row["output_tokens"] or 0),
            )
            estimated_cost += row_cost
            avoided_cost += row_cost * int(row["cache_hits"] or 0)
            cost_by_model[model_name] = cost_by_model.get(model_name, 0.0) + row_cost
        return {
            "period_hours": hours,
            "call_count": len(rows),
            "cache_hit_count": cache_hits,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "estimated_cost_usd": round(estimated_cost, 6),
            "estimated_cost_avoided_usd": round(avoided_cost, 6),
            "cost_by_model": {model: round(cost, 6) for model, cost in sorted(cost_by_model.items())},
        }
