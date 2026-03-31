"""Pipeline unit tests for collect, analyze, publish, and dashboard flows."""

from __future__ import annotations

import importlib
import sqlite3
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from antigravity_mcp.domain.models import ChannelDraft, ContentItem, ContentReport, GeneratedPayload
from antigravity_mcp.state.store import PipelineStateStore


@pytest.fixture
def state_store(tmp_path):
    return PipelineStateStore(path=tmp_path / "test_state.db")


@pytest.fixture
def sample_items():
    return [
        ContentItem(
            source_name="TechCrunch",
            category="Tech",
            title="AI Breakthrough in 2026",
            link="https://example.com/ai-breakthrough",
            published_at="",
            summary="Major AI breakthrough announced today with new architecture.",
        ),
        ContentItem(
            source_name="Reuters",
            category="Tech",
            title="Chip Market Outlook",
            link="https://example.com/chip-market",
            published_at="",
            summary="Semiconductor market shows strong growth trend.",
        ),
    ]


@pytest.fixture
def sample_report():
    return ContentReport(
        report_id="report-tech-20260304T000000Z",
        category="Tech",
        window_name="morning",
        window_start="2026-03-03T18:00:00+00:00",
        window_end="2026-03-04T07:00:00+00:00",
        summary_lines=["AI breakthrough covers 2 articles.", "Top signal: AI Breakthrough in 2026."],
        insights=["Tech coverage is clustering around AI.", "Review 2 candidates."],
        channel_drafts=[ChannelDraft(channel="x", status="draft", content="Tech brief")],
        asset_status="draft",
        approval_state="manual",
        source_links=["https://example.com/ai-breakthrough", "https://example.com/chip-market"],
        status="draft",
        fingerprint="abc123",
        created_at="2026-03-04T00:00:00+00:00",
        updated_at="2026-03-04T00:00:00+00:00",
    )


class TestCollectPipeline:
    @pytest.mark.asyncio
    async def test_collect_deduplicates_seen_articles(self, state_store):
        from antigravity_mcp.pipelines.collect import collect_content_items

        state_store.record_article(
            link="https://seen.example.com/old",
            source="TestSource",
            category="Tech",
            window_name="manual",
            notion_page_id=None,
            run_id="seed-run",
        )

        entry = SimpleNamespace(
            title="Old Article",
            link="https://seen.example.com/old",
            summary="Already seen",
            published_parsed=None,
        )
        mock_adapter = MagicMock()
        mock_adapter.fetch_entries = AsyncMock(return_value=[entry])

        with patch(
            "antigravity_mcp.pipelines.collect.load_sources",
            return_value={"Tech": [{"name": "TestSource", "url": "http://test.rss"}]},
        ):
            items, warnings = await collect_content_items(
                categories=["Tech"],
                window_name="manual",
                max_items=5,
                state_store=state_store,
                feed_adapter=mock_adapter,
            )

        assert len(items) == 0
        assert warnings == []

    @pytest.mark.asyncio
    async def test_collect_handles_feed_failure_gracefully(self, state_store):
        from antigravity_mcp.pipelines.collect import collect_content_items

        mock_adapter = MagicMock()
        mock_adapter.fetch_entries = AsyncMock(side_effect=ConnectionError("timeout"))

        with patch(
            "antigravity_mcp.pipelines.collect.load_sources",
            return_value={"Tech": [{"name": "FailSource", "url": "http://fail.rss"}]},
        ):
            items, warnings = await collect_content_items(
                categories=["Tech"],
                window_name="manual",
                max_items=5,
                state_store=state_store,
                feed_adapter=mock_adapter,
            )

        assert items == []
        assert any("FailSource" in warning for warning in warnings)

    @pytest.mark.asyncio
    async def test_collect_parallel_fetches_multiple_sources(self, state_store):
        from antigravity_mcp.pipelines.collect import collect_content_items

        entry_a = SimpleNamespace(title="A", link="https://a.example.com", summary="aa", published_parsed=None)
        entry_b = SimpleNamespace(title="B", link="https://b.example.com", summary="bb", published_parsed=None)

        call_order: list[str] = []

        async def fake_fetch(url: str):
            call_order.append(url)
            if "source-a" in url:
                return [entry_a]
            return [entry_b]

        mock_adapter = MagicMock()
        mock_adapter.fetch_entries = fake_fetch

        with patch(
            "antigravity_mcp.pipelines.collect.load_sources",
            return_value={
                "Tech": [
                    {"name": "SourceA", "url": "http://source-a.rss"},
                    {"name": "SourceB", "url": "http://source-b.rss"},
                ]
            },
        ):
            items, warnings = await collect_content_items(
                categories=["Tech"],
                window_name="manual",
                max_items=10,
                state_store=state_store,
                feed_adapter=mock_adapter,
            )

        assert len(items) == 2
        assert warnings == []
        assert len(call_order) == 2


class TestAnalyzePipeline:
    @pytest.mark.asyncio
    async def test_generate_briefs_creates_reports(self, state_store, sample_items):
        from antigravity_mcp.pipelines.analyze import generate_briefs

        mock_llm = MagicMock()
        mock_llm.build_report_payload = AsyncMock(
            return_value=(
                (["Summary line 1"], ["Insight 1"], [ChannelDraft(channel="x", status="draft", content="Draft")]),
                [],
            )
        )

        run_id, reports, warnings, status = await generate_briefs(
            items=sample_items,
            window_name="manual",
            window_start="2026-03-03T00:00:00+00:00",
            window_end="2026-03-04T00:00:00+00:00",
            state_store=state_store,
            llm_adapter=mock_llm,
        )

        assert len(reports) == 1
        assert reports[0].category == "Tech"
        assert status in ("ok", "partial")
        assert run_id.startswith("generate_brief-")
        assert isinstance(warnings, list)

    @pytest.mark.asyncio
    async def test_generate_briefs_reuses_existing_fingerprint(self, state_store, sample_items):
        from antigravity_mcp.pipelines.analyze import generate_briefs

        mock_llm = MagicMock()
        mock_llm.build_report_payload = AsyncMock(
            return_value=(
                (["Summary"], ["Insight"], [ChannelDraft(channel="x", status="draft", content="Draft")]),
                [],
            )
        )

        _, reports1, _, _ = await generate_briefs(
            items=sample_items,
            window_name="manual",
            window_start="2026-03-03T00:00:00+00:00",
            window_end="2026-03-04T00:00:00+00:00",
            state_store=state_store,
            llm_adapter=mock_llm,
        )

        _, reports2, warnings2, _ = await generate_briefs(
            items=sample_items,
            window_name="manual",
            window_start="2026-03-03T00:00:00+00:00",
            window_end="2026-03-04T00:00:00+00:00",
            state_store=state_store,
            llm_adapter=mock_llm,
        )

        assert reports1[0].report_id == reports2[0].report_id
        assert any("Reused" in warning for warning in warnings2)

    @pytest.mark.asyncio
    async def test_generate_briefs_persists_analysis_meta_without_override_in_concise_mode(
        self, state_store, sample_items
    ):
        from antigravity_mcp.pipelines.analyze import generate_briefs

        class FakeInsightAdapter:
            async def generate_insights(self, *, category, articles, window_name="morning", max_insights=4):
                return {
                    "insights": [
                        {
                            "title": "Non-obvious edge",
                            "content": "This week compare GPU rental vendors against internal latency targets.",
                            "validation_passed": True,
                        }
                    ],
                    "x_long_form": "Long-form X draft from insight generator",
                    "validation_summary": {"total_insights": 1, "passed": 1, "failed": 0},
                }

        mock_llm = MagicMock()
        mock_llm.build_report_payload = AsyncMock(
            return_value=(
                GeneratedPayload(
                    summary_lines=["Summary line 1"],
                    insights=["Insight 1"],
                    channel_drafts=[ChannelDraft(channel="x", status="draft", content="Base draft")],
                    generation_mode="v2-deep",
                    parse_meta={"used_fallback": False, "missing_sections": [], "sections_found": {"signal": 1}},
                    quality_state="ok",
                ),
                [],
            )
        )

        _, reports, _, _ = await generate_briefs(
            items=sample_items,
            window_name="manual",
            window_start="2026-03-03T00:00:00+00:00",
            window_end="2026-03-04T00:00:00+00:00",
            state_store=state_store,
            llm_adapter=mock_llm,
            insight_adapter=FakeInsightAdapter(),
        )

        saved = state_store.get_report(reports[0].report_id)
        assert saved is not None
        assert saved.generation_mode == "v2-deep"
        assert saved.analysis_meta["parser"]["used_fallback"] is False
        assert "validation_summary" in saved.analysis_meta["insight_generator"]
        assert saved.analysis_meta["insight_generator"]["x_long_form"] == "Long-form X draft from insight generator"
        assert "draft_overrides" not in saved.analysis_meta
        assert next(d for d in saved.channel_drafts if d.channel == "x").source == "llm"

    @pytest.mark.asyncio
    async def test_generate_briefs_normalizes_brief_body_before_persist(self, state_store, sample_items):
        from antigravity_mcp.pipelines.analyze import generate_briefs

        mock_llm = MagicMock()
        mock_llm.build_report_payload = AsyncMock(
            return_value=(
                GeneratedPayload(
                    summary_lines=["Summary line 1", "Summary line 2", "Summary line 3"],
                    insights=["Insight 1", "Insight 2"],
                    channel_drafts=[ChannelDraft(channel="x", status="draft", content="Short X draft")],
                    generation_mode="v1-brief",
                    parse_meta={
                        "used_fallback": False,
                        "missing_sections": [],
                        "sections_found": {"summary": 3, "insights": 2, "brief": 4, "draft": 1},
                        "brief_body": (
                            "오늘의 핫 이슈: Tech. 변화의 시작입니다.\n"
                            "핵심 사실: 첫 문장.\n"
                            "배경/디테일: 둘째 문장.\n"
                            "전망/의미: 셋째 문장."
                        ),
                    },
                    quality_state="ok",
                ),
                [],
            )
        )

        _, reports, _, _ = await generate_briefs(
            items=sample_items,
            window_name="manual",
            window_start="2026-03-03T00:00:00+00:00",
            window_end="2026-03-04T00:00:00+00:00",
            state_store=state_store,
            llm_adapter=mock_llm,
        )

        saved = state_store.get_report(reports[0].report_id)
        assert saved is not None
        assert saved.generation_mode == "v1-brief"
        assert saved.analysis_meta["brief_body"] == (
            "오늘의 핫 이슈: Tech. 변화의 시작입니다.\n" "첫 문장.\n" "둘째 문장.\n" "셋째 문장."
        )
        assert "핵심 사실:" not in saved.analysis_meta["brief_body"]
        assert "배경/디테일:" not in saved.analysis_meta["brief_body"]
        assert "전망/의미:" not in saved.analysis_meta["brief_body"]

    @pytest.mark.asyncio
    async def test_generate_briefs_marks_needs_review_when_evidence_tags_missing(self, state_store, sample_items):
        from antigravity_mcp.pipelines.analyze import generate_briefs

        mock_llm = MagicMock()
        mock_llm.build_report_payload = AsyncMock(
            return_value=(
                GeneratedPayload(
                    summary_lines=["Signal line without tag"],
                    insights=["Pattern line without tag"],
                    channel_drafts=[ChannelDraft(channel="x", status="draft", content="Base draft")],
                    generation_mode="v2-deep",
                    parse_meta={
                        "used_fallback": False,
                        "format": "v2",
                        "missing_sections": [],
                        "sections_found": {"signal": 1, "pattern": 1},
                        "evidence": {
                            "line_count": 2,
                            "tagged_line_count": 0,
                            "missing_line_count": 2,
                            "missing_lines_preview": ["Signal line without tag", "Pattern line without tag"],
                            "article_ref_count": 0,
                            "article_refs": [],
                            "inference_count": 0,
                            "background_line_count": 0,
                        },
                    },
                    quality_state="ok",
                ),
                [],
            )
        )

        _, reports, warnings, _ = await generate_briefs(
            items=sample_items,
            window_name="manual",
            window_start="2026-03-03T00:00:00+00:00",
            window_end="2026-03-04T00:00:00+00:00",
            state_store=state_store,
            llm_adapter=mock_llm,
        )

        assert reports[0].quality_state == "needs_review"
        assert any("Evidence tags missing" in warning for warning in warnings)


class TestReportStateSemantics:
    def test_content_report_delivery_state_distinguishes_notion_sync(self, sample_report):
        assert sample_report.has_notion_sync() is False
        assert sample_report.delivery_state == "draft"

        sample_report.status = "published"
        assert sample_report.delivery_state == "published"

        sample_report.notion_page_id = "notion-page-123"
        assert sample_report.has_notion_sync() is True
        assert sample_report.delivery_state == "notion_synced"


class TestPublishPipeline:
    @pytest.mark.asyncio
    async def test_publish_unknown_report_returns_error(self, state_store):
        from antigravity_mcp.pipelines.publish import publish_report

        run_id, publication, warnings, status = await publish_report(
            report_id="nonexistent-report",
            channels=["x"],
            approval_mode="manual",
            state_store=state_store,
        )

        assert run_id
        assert publication == {}
        assert status == "error"
        assert any("Unknown" in warning for warning in warnings)

    @pytest.mark.asyncio
    async def test_publish_without_notion_stores_locally(self, state_store, sample_report):
        from antigravity_mcp.pipelines.publish import publish_report

        state_store.save_report(sample_report)

        mock_notion = MagicMock()
        mock_notion.is_configured.return_value = False

        _, publication, warnings, _ = await publish_report(
            report_id=sample_report.report_id,
            channels=["x"],
            approval_mode="manual",
            state_store=state_store,
            notion_adapter=mock_notion,
        )

        assert "report_id" in publication
        assert publication["report_delivery_state"] == "draft"
        assert any("not configured" in warning for warning in warnings)

        saved = state_store.get_report(sample_report.report_id)
        assert saved is not None
        assert saved.delivery_state == "draft"

    @pytest.mark.asyncio
    async def test_publish_with_notion_marks_report_as_notion_synced(self, state_store, sample_report):
        from antigravity_mcp.pipelines.publish import publish_report

        state_store.save_report(sample_report)

        mock_notion = MagicMock()
        mock_notion.is_configured.return_value = True
        mock_notion.create_record = AsyncMock(return_value={"id": "notion-page-123", "url": "https://notion.so/page"})
        # [QA 수정] query_database must be AsyncMock for duplicate-prevention check
        mock_notion.query_database = AsyncMock(return_value=([], ""))

        mock_telegram = MagicMock()
        mock_telegram.send_message = AsyncMock(return_value=True)

        fake_settings = MagicMock(
            content_approval_mode="manual",
            notion_reports_database_id="db-123",
            auto_push_enabled=False,
        )
        with patch("antigravity_mcp.pipelines.publish.get_settings", return_value=fake_settings):
            _, publication, warnings, status = await publish_report(
                report_id=sample_report.report_id,
                channels=[],
                approval_mode="manual",
                state_store=state_store,
                notion_adapter=mock_notion,
                telegram_adapter=mock_telegram,
            )

        assert status in ("ok", "partial")
        assert publication["report_status"] == "published"
        assert publication["report_delivery_state"] == "notion_synced"
        # [QA 수정] Verify duplicate check was called
        mock_notion.query_database.assert_called_once()

        saved = state_store.get_report(sample_report.report_id)
        assert saved is not None
        assert saved.status == "published"
        assert saved.delivery_state == "notion_synced"
        assert saved.has_notion_sync() is True

    @pytest.mark.asyncio
    async def test_regression_duplicate_prevention_skips_creation_20260331(self, state_store, sample_report):
        """Regression: publish_report should skip create_record when a page already exists for same date+category."""
        from antigravity_mcp.pipelines.publish import publish_report

        state_store.save_report(sample_report)

        mock_notion = MagicMock()
        mock_notion.is_configured.return_value = True
        # [QA 수정] Simulate existing page found by duplicate check
        mock_notion.query_database = AsyncMock(
            return_value=([{"id": "existing-page-id", "url": "https://notion.so/existing"}], "")
        )
        mock_notion.create_record = AsyncMock()

        mock_telegram = MagicMock()
        mock_telegram.send_message = AsyncMock(return_value=True)

        fake_settings = MagicMock(
            content_approval_mode="manual",
            notion_reports_database_id="db-123",
            auto_push_enabled=False,
        )
        with patch("antigravity_mcp.pipelines.publish.get_settings", return_value=fake_settings):
            _, publication, warnings, _ = await publish_report(
                report_id=sample_report.report_id,
                channels=[],
                approval_mode="manual",
                state_store=state_store,
                notion_adapter=mock_notion,
                telegram_adapter=mock_telegram,
            )

        # create_record should NOT be called when duplicate exists
        mock_notion.create_record.assert_not_called()
        assert publication["notion_page_id"] == "existing-page-id"
        assert any("already exists" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_regression_properties_include_type_sentiment_entities_20260331(self, state_store, sample_report):
        """Regression: publish_report should set Type=News and map Sentiment/Entities from analysis_meta."""
        from antigravity_mcp.pipelines.publish import publish_report

        sample_report.analysis_meta = {
            "sentiment": {"overall": "BULLISH", "entities": ["AI", "Cloud"]},
        }
        state_store.save_report(sample_report)

        mock_notion = MagicMock()
        mock_notion.is_configured.return_value = True
        mock_notion.query_database = AsyncMock(return_value=([], ""))
        mock_notion.create_record = AsyncMock(return_value={"id": "new-page-id", "url": "https://notion.so/new"})

        mock_telegram = MagicMock()
        mock_telegram.send_message = AsyncMock(return_value=True)

        fake_settings = MagicMock(
            content_approval_mode="manual",
            notion_reports_database_id="db-123",
            auto_push_enabled=False,
        )
        with patch("antigravity_mcp.pipelines.publish.get_settings", return_value=fake_settings):
            await publish_report(
                report_id=sample_report.report_id,
                channels=[],
                approval_mode="manual",
                state_store=state_store,
                notion_adapter=mock_notion,
                telegram_adapter=mock_telegram,
            )

        # Verify create_record was called with the correct properties
        call_kwargs = mock_notion.create_record.call_args[1]
        props = call_kwargs["properties"]
        assert props["Type"] == {"select": {"name": "News"}}
        assert props["Sentiment"] == {"select": {"name": "BULLISH"}}
        assert props["Entities"] == {"multi_select": [{"name": "AI"}, {"name": "Cloud"}]}

    def test_regression_api_version_is_stable_20260331(self):
        """Regression: Notion API version must be 2022-06-28, not the non-existent 2025-09-03."""
        from antigravity_mcp.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()
        assert settings.notion_api_version == "2022-06-28", (
            f"API version reverted to invalid value: {settings.notion_api_version}"
        )
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_publish_downgrades_auto_when_quality_not_ok(self, state_store, sample_report, monkeypatch):
        from antigravity_mcp.config import get_settings
        from antigravity_mcp.pipelines.publish import publish_report

        monkeypatch.setenv("CONTENT_APPROVAL_MODE", "auto")
        get_settings.cache_clear()

        sample_report.quality_state = "needs_review"
        sample_report.channel_drafts = [
            ChannelDraft(channel="x", status="draft", content="Draft post", source="fallback", is_fallback=True),
        ]
        state_store.save_report(sample_report)

        class FakeNotion:
            def is_configured(self) -> bool:
                return False

        class FakeX:
            def __init__(self) -> None:
                self.approval_modes: list[str] = []

            async def publish(self, report, content: str, *, approval_mode: str):
                self.approval_modes.append(approval_mode)
                return {"status": "draft", "message": ""}

        fake_x = FakeX()

        _, _, warnings, _ = await publish_report(
            report_id=sample_report.report_id,
            channels=["x"],
            approval_mode="auto",
            state_store=state_store,
            notion_adapter=FakeNotion(),
            x_adapter=fake_x,
        )

        assert fake_x.approval_modes == ["manual"]
        assert any("Auto publishing downgraded to manual" in warning for warning in warnings)
        get_settings.cache_clear()

    def test_report_markdown_includes_analysis_meta(self, sample_report):
        from antigravity_mcp.pipelines.publish import _report_markdown

        sample_report.generation_mode = "v2-deep"
        sample_report.quality_state = "needs_review"
        sample_report.analysis_meta = {
            "parser": {
                "used_fallback": False,
                "missing_sections": ["draft"],
                "evidence": {"tagged_line_count": 3, "line_count": 4, "article_refs": ["[A1]", "[A2]"]},
            },
            "draft_overrides": {"x": "insight_generator"},
            "quality_review": {"warnings": ["Generic CTA detected without timeframe."]},
            "insight_generator": {"validation_summary": {"total_insights": 2, "passed": 1, "failed": 1}},
            "fact_check": {"passed": False, "fact_check_score": 0.31},
        }

        markdown = _report_markdown(sample_report)

        assert "## Analysis Meta" in markdown
        assert "Missing sections: draft" in markdown
        assert "Evidence tags: 3/4 analytic lines tagged" in markdown
        assert "Direct article refs: [A1], [A2]" in markdown
        assert "Draft overrides: x=insight_generator" in markdown
        assert "Insight validation: passed=1 / failed=1 / total=2" in markdown
        assert "score=0.31" in markdown


class TestDashboardPipeline:
    @pytest.mark.asyncio
    async def test_refresh_dashboard_without_notion(self, state_store):
        from antigravity_mcp.pipelines.dashboard import refresh_dashboard

        mock_notion = MagicMock()
        mock_notion.is_configured.return_value = False

        _, payload, warnings, _ = await refresh_dashboard(
            state_store=state_store,
            notion_adapter=mock_notion,
        )

        assert "reports" in payload
        assert "runs" in payload
        assert any("not configured" in warning for warning in warnings)

    @pytest.mark.asyncio
    async def test_refresh_dashboard_includes_governance_summary(self, state_store, sample_report):
        from antigravity_mcp.pipelines.dashboard import refresh_dashboard

        sample_report.quality_state = "fallback"
        sample_report.channel_drafts = [
            ChannelDraft(channel="x", status="draft", content="Draft", source="fallback", is_fallback=True),
        ]
        state_store.save_report(sample_report)

        mock_notion = MagicMock()
        mock_notion.is_configured.return_value = False

        _, payload, _, _ = await refresh_dashboard(
            state_store=state_store,
            notion_adapter=mock_notion,
        )

        governance = payload["governance"]
        assert governance["quality_counts"]["fallback"] == 1
        assert governance["fallback_x_drafts"] == 1
        assert payload["recent_reports"][0]["quality_state"] == "fallback"


class TestStateStore:
    def test_wal_mode_enabled(self, state_store):
        conn = state_store._connect()
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"

    def test_pipeline_health_empty_db(self, state_store):
        health = state_store.get_pipeline_health()
        assert health["last_run_at"] is None
        assert health["total_runs_24h"] == 0
        assert health["error_rate"] == 0.0

    def test_job_lifecycle(self, state_store):
        state_store.record_job_start("run-1", "test_job")
        run = state_store.get_run("run-1")
        assert run is not None
        assert run.status == "running"

        state_store.record_job_finish("run-1", status="success", processed_count=5)
        run = state_store.get_run("run-1")
        assert run is not None
        assert run.status == "success"
        assert run.processed_count == 5

    def test_report_fingerprint_dedup(self, state_store, sample_report):
        state_store.save_report(sample_report)
        found = state_store.find_report_by_fingerprint(sample_report.fingerprint)
        assert found is not None
        assert found.report_id == sample_report.report_id

    def test_schema_migrates_legacy_content_reports_to_v2(self, tmp_path):
        db_path = tmp_path / "legacy_state.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE content_reports (
                report_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                window_name TEXT NOT NULL,
                window_start TEXT NOT NULL,
                window_end TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                insights_json TEXT NOT NULL,
                drafts_json TEXT NOT NULL,
                notion_page_id TEXT,
                asset_status TEXT NOT NULL,
                approval_state TEXT NOT NULL,
                source_links_json TEXT NOT NULL,
                status TEXT NOT NULL,
                fingerprint TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO content_reports (
                report_id, category, window_name, window_start, window_end,
                summary_json, insights_json, drafts_json, notion_page_id, asset_status,
                approval_state, source_links_json, status, fingerprint, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-report",
                "Tech",
                "manual",
                "2026-03-03T00:00:00+00:00",
                "2026-03-04T00:00:00+00:00",
                '["summary"]',
                '["insight"]',
                '[{"channel":"x","status":"draft","content":"draft"}]',
                "",
                "draft",
                "manual",
                '["https://example.com/story"]',
                "draft",
                "legacy-fingerprint",
                "2026-03-03T00:00:00+00:00",
                "2026-03-03T00:00:00+00:00",
            ),
        )
        conn.commit()
        conn.close()

        store = PipelineStateStore(path=db_path)
        report = store.get_report("legacy-report")
        schema_version = store._connect().execute("SELECT version FROM schema_version").fetchone()[0]

        assert schema_version == 2
        assert report is not None
        assert report.quality_state == "ok"
        assert report.generation_mode == ""
        assert report.analysis_meta == {}

    def test_article_dedup(self, state_store):
        state_store.record_article(
            link="https://test.com/article",
            source="TestSource",
            category="Tech",
            window_name="manual",
            notion_page_id=None,
            run_id="run-1",
        )
        assert state_store.has_seen_article(link="https://test.com/article", category="Tech", window_name="manual")
        assert not state_store.has_seen_article(link="https://test.com/other", category="Tech", window_name="manual")

    def test_cleanup_stale_runs(self, state_store):
        state_store.record_job_start("stale-run", "test_job")
        conn = state_store._connect()
        old_time = (datetime.now(UTC) - timedelta(minutes=31)).isoformat()
        conn.execute("UPDATE job_runs SET started_at = ? WHERE run_id = ?", (old_time, "stale-run"))
        conn.commit()

        cleaned = state_store.cleanup_stale_runs(max_age_minutes=30)
        assert cleaned == 1

        run = state_store.get_run("stale-run")
        assert run is not None
        assert run.status == "failed"
        assert "auto-cleaned" in run.error_text

    def test_cleanup_stale_runs_ignores_recent(self, state_store):
        state_store.record_job_start("recent-run", "test_job")
        cleaned = state_store.cleanup_stale_runs(max_age_minutes=30)
        assert cleaned == 0

        run = state_store.get_run("recent-run")
        assert run is not None
        assert run.status == "running"


class TestV2PromptParser:
    def test_parse_v2_response_extracts_all_sections(self):
        from antigravity_mcp.integrations.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        v2_text = """### Signal
OpenAI's $40B raise at $340B valuation sets a new floor for frontier AI company valuations.

### Pattern
This signal connects to rising GPU demand because NVIDIA earnings beat estimates.

### Ripple Effects
- 1st order: Competition for AI talent intensifies.
- 2nd order: Mid-tier AI startups face a higher funding bar within 6 months.
- 3rd order: Regulatory pressure on AI monopoly risk increases by 2027.

### Counterpoint
Despite the headline valuation, OpenAI's revenue-to-valuation ratio is historically low.

### Action Items
- Startup founder: Build a defensible data moat this week.
- Investor: Compare secondary market pricing before Q2.

### Draft Post
OpenAI just raised $40B. But the real signal is what that does to the funding bar for everyone else.
"""
        items = [
            ContentItem(
                source_name="TechCrunch",
                category="Tech",
                title="OpenAI Raises $40B",
                link="https://example.com/openai",
                published_at="",
                summary="OpenAI fundraise.",
            ),
        ]

        summary, insights, drafts = adapter._parse_v2_response(
            category="Tech",
            text=v2_text,
            items=items,
            window_name="morning",
        )

        assert len(summary) >= 1
        assert "OpenAI" in summary[0]
        assert len(insights) >= 4
        assert any("revenue-to-valuation" in insight for insight in insights)
        assert any(draft.channel == "x" for draft in drafts)
        assert any("$40B" in draft.content for draft in drafts)

    def test_parse_response_marks_parse_fallback_metadata(self):
        from antigravity_mcp.integrations.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        payload, warnings = adapter._parse_response(
            category="Tech",
            text="### Signal\nOnly one section",
            items=[
                ContentItem(
                    source_name="Feed",
                    category="Tech",
                    title="Story A",
                    link="https://example.com/story-a",
                    summary="Summary A",
                )
            ],
            window_name="morning",
            generation_mode="v2-deep",
        )

        assert payload.parse_meta["used_fallback"] is True
        assert "parse_fallback:Tech:morning" in warnings

    def test_parse_v2_response_collects_evidence_metadata(self):
        from antigravity_mcp.integrations.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        items = [
            ContentItem(
                source_name="Feed",
                category="Tech",
                title="GPU demand story",
                link="https://example.com/gpu",
                summary="GPU demand remains sticky.",
            ),
            ContentItem(
                source_name="Feed",
                category="Tech",
                title="Cloud pricing story",
                link="https://example.com/cloud",
                summary="Cloud pricing pressure is broadening.",
            ),
        ]
        payload, warnings = adapter._parse_response(
            category="Tech",
            text="""### Signal
GPU demand remains sticky through Q3. [A1]

### Pattern
Cloud pricing pressure is broadening beyond training clusters. [Inference:A1+A2]

### Ripple Effects
- 1st order: Mid-market teams delay larger experiments. [A2]

### Counterpoint
Some buyers can still absorb the cost with premium enterprise budgets. [Background]

### Action Items
- Founder/PM: compare inference vendors this week. [Inference:A1+A2]

### Draft Post
GPU demand is staying tighter for longer than many teams expected.
""",
            items=items,
            window_name="morning",
            generation_mode="v2-deep",
        )

        evidence = payload.parse_meta["evidence"]
        assert warnings == []
        assert evidence["line_count"] == 5
        assert evidence["tagged_line_count"] == 5
        assert evidence["missing_line_count"] == 0
        assert evidence["article_ref_count"] == 2

    def test_parse_v1_brief_response_extracts_brief_body_and_limits_insights(self):
        from antigravity_mcp.integrations.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        payload, warnings = adapter._parse_response(
            category="Tech",
            text="""Summary
- 첫 번째 요약
- 두 번째 요약
- 세 번째 요약
Insights
- 첫 번째 인사이트
- 두 번째 인사이트
- 세 번째 인사이트
Brief
오늘의 핫 이슈: Tech. 변화의 시작입니다.
## 🤖 로봇 전력 강화
중국이 무인 전투체계 고도화에 속도를 내고 있습니다.
배경과 함의도 함께 커지고 있습니다.
Draft
짧은 X 초안
""",
            items=[
                ContentItem(
                    source_name="Feed",
                    category="Tech",
                    title="Story A",
                    link="https://example.com/story-a",
                    summary="Summary A",
                )
            ],
            window_name="morning",
            generation_mode="v1-brief",
        )

        assert warnings == []
        assert payload.summary_lines == ["첫 번째 요약", "두 번째 요약", "세 번째 요약"]
        assert payload.insights == ["첫 번째 인사이트", "두 번째 인사이트"]
        assert payload.parse_meta["brief_body"].startswith("오늘의 핫 이슈: Tech.")
        assert payload.parse_meta["sections_found"]["brief"] == 4

    def test_report_markdown_prefers_styled_brief_for_v1_brief(self, sample_report):
        from antigravity_mcp.pipelines.publish import _report_markdown

        sample_report.generation_mode = "v1-brief"
        sample_report.analysis_meta = {
            "brief_body": "오늘의 핫 이슈: Tech. 변화의 시작입니다.\n## 🤖 로봇 전력 강화\n짧은 본문"
        }

        markdown = _report_markdown(sample_report)

        assert markdown.startswith("# Tech Morning Brief")
        assert "오늘의 핫 이슈: Tech. 변화의 시작입니다." in markdown
        assert "## X Draft" in markdown
        assert "## Summary" not in markdown


class TestPromptContracts:
    def test_resolve_prompt_mode_defaults_to_concise_brief(self):
        from antigravity_mcp.integrations.llm_prompts import resolve_prompt_mode

        assert resolve_prompt_mode("evening", 1) == "v1-brief"
        assert resolve_prompt_mode("evening", 2) == "v1-brief"
        assert resolve_prompt_mode("evening", 3) == "v1-brief"

    def test_resolve_prompt_mode_uses_detailed_mode_when_env_requests_it(self, monkeypatch):
        import antigravity_mcp.integrations.llm_prompts as prompts_module

        monkeypatch.setenv("BRIEF_STYLE", "detailed")
        reloaded = importlib.reload(prompts_module)
        try:
            assert reloaded.resolve_prompt_mode("evening", 1) == "v2-deep"
            assert reloaded.resolve_prompt_mode("evening", 3) == "v2-multi"
        finally:
            monkeypatch.delenv("BRIEF_STYLE", raising=False)
            importlib.reload(prompts_module)

    def test_report_fingerprint_changes_with_generation_mode(self, sample_items):
        from antigravity_mcp.pipelines.analyze import build_report_fingerprint

        fp_deep = build_report_fingerprint("Tech", "manual", "v2-deep", sample_items)
        fp_multi = build_report_fingerprint("Tech", "manual", "v2-multi", sample_items)

        assert fp_deep != fp_multi


class TestContentTools:
    @pytest.mark.asyncio
    async def test_generate_brief_normalizes_comma_separated_categories(self, monkeypatch):
        from antigravity_mcp.tooling import content_tools

        captured: dict[str, object] = {}

        async def fake_collect_content_items(*, categories, window_name, max_items, state_store):
            captured["categories"] = categories
            return [], []

        monkeypatch.setattr(content_tools, "collect_content_items", fake_collect_content_items)

        result = await content_tools.content_generate_brief_tool(
            categories=["Tech,Economy_KR", "AI_Deep", "Tech"],
            window="manual",
            max_items=3,
        )

        assert captured["categories"] == ["Tech", "Economy_KR", "AI_Deep"]
        assert result["status"] == "ok"
