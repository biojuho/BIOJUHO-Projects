from __future__ import annotations

import asyncio

from antigravity_mcp.domain.models import ChannelDraft, ContentItem, ContentReport
from antigravity_mcp.integrations.embedding_adapter import EmbeddingAdapter
from antigravity_mcp.pipelines.analyze import generate_briefs
from antigravity_mcp.pipelines.publish import publish_report
from antigravity_mcp.state.store import PipelineStateStore


class FakeLLM:
    async def build_report_payload(self, *, category, items, window_name, **kwargs):
        return (
            [
                f"{category} summary",
                "Second line",
                "Third line",
            ],
            [
                "Insight one",
                "Insight two",
            ],
            [
                ChannelDraft(channel="x", status="draft", content="Draft post"),
            ],
        ), []


def test_generate_briefs_saves_report_and_records_articles(tmp_path):
    store = PipelineStateStore(tmp_path / "pipeline_state.db")
    try:
        items = [
            ContentItem(
                source_name="Feed",
                category="Tech",
                title="Story A",
                link="https://example.com/story-a",
                summary="Summary A",
            ),
            ContentItem(
                source_name="Feed",
                category="Tech",
                title="Story B",
                link="https://example.com/story-b",
                summary="Summary B",
            ),
        ]

        disabled_embedder = EmbeddingAdapter()
        disabled_embedder._api_key = ""

        run_id, reports, warnings, status = asyncio.run(
            generate_briefs(
                items=items,
                window_name="manual",
                window_start="2026-03-02T00:00:00",
                window_end="2026-03-02T23:59:59",
                state_store=store,
                llm_adapter=FakeLLM(),
                embedding_adapter=disabled_embedder,
            )
        )

        assert status in ("ok", "partial"), f"Unexpected status: {status}, warnings: {warnings}"
        critical_warnings = [
            w for w in warnings if not any(skip in w for skip in ("Embedding", "FactCheck", "Skill", "Clustering", "Quality"))
        ]
        assert critical_warnings == [], f"Unexpected critical warnings: {critical_warnings}"
        assert len(reports) == 1
        assert store.get_run(run_id) is not None
        assert store.get_report(reports[0].report_id) is not None
        assert store.has_seen_article(link="https://example.com/story-a", category="Tech", window_name="manual")
    finally:
        store.close()


def test_publish_report_returns_partial_when_notion_not_configured(tmp_path, monkeypatch):
    store = PipelineStateStore(tmp_path / "pipeline_state.db")
    try:
        report = ContentReport(
            report_id="report-1",
            category="Tech",
            window_name="manual",
            window_start="2026-03-02T00:00:00",
            window_end="2026-03-02T23:59:59",
            summary_lines=["line1"],
            insights=["insight"],
            channel_drafts=[ChannelDraft(channel="x", status="draft", content="Draft post")],
            source_links=["https://example.com/story-a"],
            fingerprint="fingerprint-1",
        )
        store.save_report(report)
        monkeypatch.delenv("NOTION_API_KEY", raising=False)
        monkeypatch.delenv("NOTION_REPORTS_DATABASE_ID", raising=False)

        run_id, publication, warnings, status = asyncio.run(
            publish_report(
                report_id="report-1",
                channels=["x"],
                approval_mode="manual",
                state_store=store,
            )
        )

        assert run_id
        assert publication["report_id"] == "report-1"
        assert status == "partial"
        assert any(
            "manual approval" in warning.lower() or "notion reports database" in warning.lower() for warning in warnings
        )
    finally:
        store.close()
