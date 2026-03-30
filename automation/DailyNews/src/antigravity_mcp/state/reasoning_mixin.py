"""Mixin for inductive reasoning data — facts, hypotheses, and patterns.

Follows the same pattern as existing mixins in :pymod:`antigravity_mcp.state.mixins`.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from antigravity_mcp.domain.models import FactFragment, Hypothesis
from antigravity_mcp.state.events import utc_now_iso


class _ReasoningMixin:
    """CRUD for ``fact_fragments``, ``hypotheses``, and ``reasoning_patterns`` tables."""

    def _connect(self) -> sqlite3.Connection:  # type: ignore[override]
        raise NotImplementedError  # provided by PipelineStateStore

    # ── Fact Fragments ────────────────────────────────────────────────────

    def save_fact_fragments(self, facts: list[FactFragment]) -> None:
        """Bulk-insert fact fragments extracted in Step 1."""
        now = utc_now_iso()
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO fact_fragments
                    (fact_id, report_id, fact_text, why_question, category, source_title, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        f.fact_id,
                        f.report_id,
                        f.fact_text,
                        f.why_question,
                        f.category,
                        f.source_title,
                        f.created_at or now,
                    )
                    for f in facts
                ],
            )

    def get_facts_by_report(self, report_id: str) -> list[FactFragment]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM fact_fragments WHERE report_id = ? ORDER BY created_at",
                (report_id,),
            ).fetchall()
        return [
            FactFragment(
                fact_id=r["fact_id"],
                report_id=r["report_id"],
                fact_text=r["fact_text"],
                why_question=r["why_question"],
                category=r["category"],
                source_title=r["source_title"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def get_recent_facts(self, category: str, *, days: int = 7, limit: int = 50) -> list[FactFragment]:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM fact_fragments
                WHERE category = ? AND created_at >= ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (category, cutoff, limit),
            ).fetchall()
        return [
            FactFragment(
                fact_id=r["fact_id"],
                report_id=r["report_id"],
                fact_text=r["fact_text"],
                why_question=r["why_question"],
                category=r["category"],
                source_title=r["source_title"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # ── Hypotheses ────────────────────────────────────────────────────────

    def save_hypotheses(self, hypotheses: list[Hypothesis]) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO hypotheses
                    (hypothesis_id, hypothesis_text, based_on_facts_json,
                     related_pattern, status, counter_evidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        h.hypothesis_id,
                        h.hypothesis_text,
                        json.dumps(h.based_on_facts, ensure_ascii=False),
                        h.related_pattern,
                        h.status,
                        h.counter_evidence,
                        h.created_at or now,
                    )
                    for h in hypotheses
                ],
            )

    def update_hypothesis_status(self, hypothesis_id: str, *, status: str, counter_evidence: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE hypotheses
                SET status = ?, counter_evidence = ?
                WHERE hypothesis_id = ?
                """,
                (status, counter_evidence, hypothesis_id),
            )

    def get_hypotheses(self, *, status: str | None = None, limit: int = 50) -> list[Hypothesis]:
        query = "SELECT * FROM hypotheses"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            Hypothesis(
                hypothesis_id=r["hypothesis_id"],
                hypothesis_text=r["hypothesis_text"],
                based_on_facts=json.loads(r["based_on_facts_json"] or "[]"),
                related_pattern=r["related_pattern"],
                status=r["status"],
                counter_evidence=r["counter_evidence"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # ── Reasoning Patterns ────────────────────────────────────────────────

    def upsert_pattern(
        self,
        *,
        pattern_id: str,
        pattern_text: str,
        category: str,
        evidence_facts: list[str],
        strength: str = "emerging",
    ) -> None:
        """Insert a new pattern or strengthen an existing one."""
        now = utc_now_iso()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT survival_count, evidence_facts_json FROM reasoning_patterns WHERE pattern_id = ?",
                (pattern_id,),
            ).fetchone()

            if existing:
                old_facts = json.loads(existing["evidence_facts_json"] or "[]")
                merged = list(set(old_facts + evidence_facts))
                new_count = existing["survival_count"] + 1
                new_strength = "strong" if new_count >= 3 else "emerging"
                conn.execute(
                    """
                    UPDATE reasoning_patterns
                    SET survival_count = ?, evidence_facts_json = ?,
                        strength = ?, updated_at = ?
                    WHERE pattern_id = ?
                    """,
                    (new_count, json.dumps(merged, ensure_ascii=False), new_strength, now, pattern_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO reasoning_patterns
                        (pattern_id, pattern_text, category, evidence_facts_json,
                         survival_count, strength, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        pattern_id,
                        pattern_text,
                        category,
                        json.dumps(evidence_facts, ensure_ascii=False),
                        strength,
                        now,
                        now,
                    ),
                )

    def get_active_patterns(self, category: str, *, min_survival: int = 1, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM reasoning_patterns
                WHERE category = ? AND survival_count >= ?
                ORDER BY survival_count DESC, updated_at DESC
                LIMIT ?
                """,
                (category, min_survival, limit),
            ).fetchall()
        return [
            {
                "pattern_id": r["pattern_id"],
                "pattern_text": r["pattern_text"],
                "category": r["category"],
                "evidence_facts": json.loads(r["evidence_facts_json"] or "[]"),
                "survival_count": r["survival_count"],
                "strength": r["strength"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
