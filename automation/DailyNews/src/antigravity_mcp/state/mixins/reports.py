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


class _ReportMixin(_DBProviderBase):
    """Methods for the ``content_reports`` and ``channel_publications`` tables."""

    def find_report_by_fingerprint(self, fingerprint: str) -> ContentReport | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM content_reports WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        return self._row_to_report(row) if row else None  # type: ignore[attr-defined]

    def get_recent_drafts(
        self, category: str, *, days: int = 7, channel: str = "x",
    ) -> list[dict[str, Any]]:
        """Return draft texts published in the last *days* for a category+channel.

        Used by the semantic dedup layer to detect content overlap with
        previously published material.
        """
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT r.report_id, r.category, r.window_name,
                       r.drafts_json, r.insights_json, r.created_at
                FROM content_reports r
                WHERE r.category = ? AND r.created_at >= ?
                ORDER BY r.created_at DESC
                """,
                (category, cutoff),
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            drafts = json.loads(row["drafts_json"] or "[]")
            for draft in drafts:
                if draft.get("channel") == channel and draft.get("content"):
                    results.append({
                        "report_id": row["report_id"],
                        "window_name": row["window_name"],
                        "content": draft["content"],
                        "created_at": row["created_at"],
                    })
        return results

    def get_recent_insight_texts(
        self, category: str, *, days: int = 7, limit: int = 20,
    ) -> list[str]:
        """Return flat list of insight texts from the last *days* for a category.

        Used by insight generator to inject differentiation directives so that
        new insights avoid repeating previously published conclusions.
        """
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT insights_json
                FROM content_reports
                WHERE category = ? AND created_at >= ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (category, cutoff, limit),
            ).fetchall()
        texts: list[str] = []
        for row in rows:
            for insight in json.loads(row["insights_json"] or "[]"):
                if isinstance(insight, str) and insight.strip():
                    texts.append(insight.strip())
        return texts

    def get_category_quality_history(
        self, category: str, *, days: int = 7,
    ) -> dict[str, Any]:
        """Aggregate quality metrics for a category over the last *days*.

        Returns quality_state distribution, recurring warnings, average
        fact-check score, and improvement suggestions.  Used by the QA
        feedback loop to inject corrective context into the next LLM prompt.
        """
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT quality_state, fact_check_score, analysis_meta_json
                FROM content_reports
                WHERE category = ? AND created_at >= ?
                ORDER BY created_at DESC
                """,
                (category, cutoff),
            ).fetchall()
        if not rows:
            return {"total_reports": 0, "quality_distribution": {}, "recurring_warnings": []}

        quality_dist: dict[str, int] = {}
        fact_scores: list[float] = []
        warning_counts: dict[str, int] = {}

        for row in rows:
            qs = row["quality_state"] or "ok"
            quality_dist[qs] = quality_dist.get(qs, 0) + 1
            score = float(row["fact_check_score"] or 0.0)
            if score > 0:
                fact_scores.append(score)
            meta = json.loads(row["analysis_meta_json"] or "{}")
            for w in (meta.get("quality_review", {}).get("warnings", []) or []):
                warning_counts[w] = warning_counts.get(w, 0) + 1

        recurring = sorted(
            [w for w, cnt in warning_counts.items() if cnt >= 2],
            key=lambda w: warning_counts[w],
            reverse=True,
        )[:5]

        suggestions: list[str] = []
        fallback_rate = quality_dist.get("fallback", 0) / max(len(rows), 1)
        if fallback_rate > 0.3:
            suggestions.append(
                f"{category} Draft 생성 실패율 {fallback_rate:.0%} — 프롬프트 톤 조정 또는 소스 보강 필요"
            )
        needs_review_rate = quality_dist.get("needs_review", 0) / max(len(rows), 1)
        if needs_review_rate > 0.3:
            suggestions.append(
                f"{category} 리뷰 필요 비율 {needs_review_rate:.0%} — CTA/증거 품질 개선 필요"
            )

        return {
            "total_reports": len(rows),
            "quality_distribution": quality_dist,
            "recurring_warnings": recurring,
            "avg_fact_check_score": round(sum(fact_scores) / max(len(fact_scores), 1), 3) if fact_scores else 0.0,
            "improvement_suggestions": suggestions,
        }

    def save_report(self, report: ContentReport) -> None:
        now = utc_now_iso()
        created_at = report.created_at or now
        updated_at = now
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO content_reports(
                    report_id, category, window_name, window_start, window_end,
                    summary_json, insights_json, drafts_json, notion_page_id, asset_status,
                    approval_state, source_links_json, status, fingerprint, created_at, updated_at,
                    notebooklm_metadata_json, fact_check_score, quality_state, generation_mode, analysis_meta_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.report_id,
                    report.category,
                    report.window_name,
                    report.window_start,
                    report.window_end,
                    json.dumps(report.summary_lines, ensure_ascii=False, default=_json_default),
                    json.dumps(report.insights, ensure_ascii=False, default=_json_default),
                    json.dumps(
                        [draft.to_dict() for draft in report.channel_drafts], ensure_ascii=False, default=_json_default
                    ),
                    report.notion_page_id,
                    report.asset_status,
                    report.approval_state,
                    json.dumps(report.source_links, ensure_ascii=False, default=_json_default),
                    report.status,
                    report.fingerprint,
                    created_at,
                    updated_at,
                    json.dumps(report.notebooklm_metadata, ensure_ascii=False, default=_json_default),
                    float(report.fact_check_score),
                    report.quality_state,
                    report.generation_mode,
                    json.dumps(report.analysis_meta, ensure_ascii=False, default=_json_default),
                ),
            )

    def get_report(self, report_id: str) -> ContentReport | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM content_reports WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        return self._row_to_report(row) if row else None  # type: ignore[attr-defined]

    def list_reports(self, *, limit: int = 20, category: str | None = None) -> list[ContentReport]:
        query = "SELECT * FROM content_reports"
        params: list[Any] = []
        if category:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [report for report in (self._row_to_report(row) for row in rows) if report is not None]

    def get_report_governance_summary(self, *, limit: int = 100) -> dict[str, Any]:
        reports = self.list_reports(limit=limit)
        quality_counts: dict[str, int] = {}
        approval_counts: dict[str, int] = {}
        fallback_x_drafts = 0
        for report in reports:
            quality_counts[report.quality_state] = quality_counts.get(report.quality_state, 0) + 1
            approval_counts[report.approval_state] = approval_counts.get(report.approval_state, 0) + 1
            if any(draft.channel == "x" and draft.is_fallback for draft in report.channel_drafts):
                fallback_x_drafts += 1
        return {
            "reports_considered": len(reports),
            "quality_counts": quality_counts,
            "approval_counts": approval_counts,
            "fallback_x_drafts": fallback_x_drafts,
        }

    def set_report_publication(self, report_id: str, *, notion_page_id: str, status: str) -> None:
        report = self.get_report(report_id)
        if report is None:
            return
        report.notion_page_id = notion_page_id
        report.status = status
        self.save_report(report)

    def set_channel_publication(self, report_id: str, channel: str, status: str, external_url: str = "") -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO channel_publications(report_id, channel, status, external_url, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (report_id, channel, status, external_url, utc_now_iso()),
            )

    def report_counts(self) -> dict[str, int]:
        with self._connect() as connection:
            total_reports = connection.execute("SELECT COUNT(*) FROM content_reports").fetchone()[0]
            total_runs = connection.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0]
            total_cached = connection.execute("SELECT COUNT(*) FROM article_cache").fetchone()[0]
        return {
            "reports": int(total_reports),
            "runs": int(total_runs),
            "cached_articles": int(total_cached),
        }

    @staticmethod
    def _row_to_report(row: sqlite3.Row | None) -> ContentReport | None:
        if row is None:
            return None
        drafts = [
            ChannelDraft(
                channel=item.get("channel", ""),
                status=item.get("status", ""),
                content=item.get("content", ""),
                external_url=item.get("external_url", ""),
                source=item.get("source", "llm"),
                is_fallback=bool(item.get("is_fallback", False)),
            )
            for item in json.loads(row["drafts_json"] or "[]")
        ]
        return ContentReport(
            report_id=row["report_id"],
            category=row["category"],
            window_name=row["window_name"],
            window_start=row["window_start"],
            window_end=row["window_end"],
            summary_lines=json.loads(row["summary_json"] or "[]"),
            insights=json.loads(row["insights_json"] or "[]"),
            channel_drafts=drafts,
            notion_page_id=row["notion_page_id"] or "",
            asset_status=row["asset_status"],
            approval_state=row["approval_state"],
            source_links=json.loads(row["source_links_json"] or "[]"),
            status=row["status"],
            fingerprint=row["fingerprint"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            notebooklm_metadata=json.loads(row["notebooklm_metadata_json"] or "{}"),
            fact_check_score=float(row["fact_check_score"] or 0.0),
            quality_state=row["quality_state"] or "ok",
            generation_mode=row["generation_mode"] or "",
            analysis_meta=json.loads(row["analysis_meta_json"] or "{}"),
        )
