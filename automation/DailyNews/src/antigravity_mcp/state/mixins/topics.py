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


class _TopicMixin(_DBProviderBase):
    """Persistent topic timeline for continuity tracking across briefs."""

    def upsert_topic(
        self,
        *,
        topic_id: str,
        topic_label: str,
        category: str,
        report_id: str,
        embedding: list[float] | None = None,
    ) -> None:
        """Insert a new topic or update an existing one with a new occurrence."""
        now = utc_now_iso()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT report_ids_json, occurrence_count FROM topic_timeline WHERE topic_id = ?",
                (topic_id,),
            ).fetchone()

            if existing:
                report_ids = json.loads(existing["report_ids_json"] or "[]")
                if report_id not in report_ids:
                    report_ids.append(report_id)
                conn.execute(
                    """
                    UPDATE topic_timeline
                    SET last_seen_at = ?, occurrence_count = occurrence_count + 1,
                        report_ids_json = ?
                    WHERE topic_id = ?
                    """,
                    (now, json.dumps(report_ids, ensure_ascii=False), topic_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO topic_timeline
                        (topic_id, topic_label, category, first_seen_at, last_seen_at,
                         occurrence_count, report_ids_json, embedding_json)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        topic_id,
                        topic_label,
                        category,
                        now,
                        now,
                        json.dumps([report_id], ensure_ascii=False),
                        json.dumps(embedding, ensure_ascii=False) if embedding else None,
                    ),
                )

    def get_recent_topics(self, category: str, *, days: int = 7, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent topics for a category, sorted by last_seen_at desc."""
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT topic_id, topic_label, category, first_seen_at, last_seen_at,
                       occurrence_count, report_ids_json
                FROM topic_timeline
                WHERE category = ? AND last_seen_at >= ?
                ORDER BY last_seen_at DESC
                LIMIT ?
                """,
                (category, cutoff, limit),
            ).fetchall()
        return [
            {
                "topic_id": row["topic_id"],
                "topic_label": row["topic_label"],
                "category": row["category"],
                "first_seen_at": row["first_seen_at"],
                "last_seen_at": row["last_seen_at"],
                "occurrence_count": row["occurrence_count"],
                "report_ids": json.loads(row["report_ids_json"] or "[]"),
            }
            for row in rows
        ]

    def find_continuing_topics(self, category: str, current_titles: list[str]) -> list[dict[str, Any]]:
        """Find topics from previous briefs that appear to continue in current content.

        Uses simple keyword overlap matching (embedding-based matching is done
        at the adapter level when available).
        """
        recent = self.get_recent_topics(category, days=3)
        continuing: list[dict[str, Any]] = []
        current_words = set()
        for title in current_titles:
            current_words.update(w.lower() for w in title.split() if len(w) > 2)

        for topic in recent:
            topic_words = set(w.lower() for w in topic["topic_label"].split() if len(w) > 2)
            overlap = current_words & topic_words
            if len(overlap) >= 2:
                topic["continuing_keywords"] = list(overlap)[:5]
                continuing.append(topic)
        return continuing
