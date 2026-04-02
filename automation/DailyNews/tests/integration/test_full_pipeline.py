"""End-to-end pipeline integration tests: collect → analyze → publish."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from antigravity_mcp.domain.models import ChannelDraft, ContentReport
from antigravity_mcp.integrations.notion_adapter import NotionAdapter
from antigravity_mcp.state.store import PipelineStateStore

# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def store(tmp_path):
    return PipelineStateStore(path=tmp_path / "test_e2e.db")


@pytest.fixture
def mock_feed_entries():
    return [
        SimpleNamespace(
            title="AI Model Released",
            link="https://techfeed.example.com/ai-model",
            summary="A new AI model has been released with improved performance.",
            published_parsed=None,
        ),
        SimpleNamespace(
            title="Crypto Market Update",
            link="https://cryptofeed.example.com/update",
            summary="Crypto markets saw significant activity this week.",
            published_parsed=None,
        ),
    ]


@pytest.fixture
def mock_llm_response():
    return (
        (
            ["AI Model Released signals new capabilities.", "Crypto markets remain volatile."],
            ["Strong signals from AI sector.", "Cross-market volatility expected."],
            [ChannelDraft(channel="x", status="draft", content="Tech & Crypto brief\n\n#AI #Crypto")],
        ),
        [],  # no warnings
    )


# ─── Full collect → analyze flow ─────────────────────────────────────────────


class TestCollectAnalyzePipeline:
    @pytest.mark.asyncio
    async def test_end_to_end_collect_then_analyze(self, store, mock_feed_entries, mock_llm_response):
        from antigravity_mcp.pipelines.analyze import generate_briefs
        from antigravity_mcp.pipelines.collect import collect_content_items

        mock_feed = MagicMock()
        mock_feed.fetch_entries = AsyncMock(return_value=mock_feed_entries)

        mock_llm = MagicMock()
        mock_llm.build_report_payload = AsyncMock(return_value=mock_llm_response)

        sources = {"Tech": [{"name": "TechFeed", "url": "https://techfeed.example.com/rss"}]}
        with patch("antigravity_mcp.pipelines.collect.load_sources", return_value=sources):
            items, collect_warnings = await collect_content_items(
                categories=["Tech"],
                window_name="manual",
                max_items=10,
                state_store=store,
                feed_adapter=mock_feed,
            )

        assert len(items) == 2
        assert collect_warnings == []

        run_id, reports, llm_warnings, status = await generate_briefs(
            items=items,
            window_name="manual",
            window_start="2026-03-04T00:00:00+00:00",
            window_end="2026-03-04T07:00:00+00:00",
            state_store=store,
            llm_adapter=mock_llm,
        )

        assert len(reports) == 1
        assert reports[0].category == "Tech"
        assert run_id.startswith("generate_brief-")
        assert status in ("ok", "partial")

        # Verify report persisted in store
        persisted = store.get_report(reports[0].report_id)
        assert persisted is not None
        assert persisted.category == "Tech"

    @pytest.mark.asyncio
    async def test_failed_feed_does_not_block_pipeline(self, store):
        from antigravity_mcp.pipelines.collect import collect_content_items

        mock_feed = MagicMock()
        mock_feed.fetch_entries = AsyncMock(side_effect=TimeoutError("feed timeout"))

        sources = {"Tech": [{"name": "BadFeed", "url": "https://broken.example.com/rss"}]}
        with patch("antigravity_mcp.pipelines.collect.load_sources", return_value=sources):
            items, warnings = await collect_content_items(
                categories=["Tech"],
                window_name="manual",
                max_items=10,
                state_store=store,
                feed_adapter=mock_feed,
            )

        assert items == []
        assert any("BadFeed" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_duplicate_articles_excluded(self, store, mock_feed_entries):
        from antigravity_mcp.pipelines.collect import collect_content_items

        # Pre-seed one article as already seen
        store.record_article(
            link="https://techfeed.example.com/ai-model",
            source="TechFeed",
            category="Tech",
            window_name="manual",
            notion_page_id=None,
            run_id="seed-run",
        )

        mock_feed = MagicMock()
        mock_feed.fetch_entries = AsyncMock(return_value=mock_feed_entries)

        sources = {"Tech": [{"name": "TechFeed", "url": "https://techfeed.example.com/rss"}]}
        with patch("antigravity_mcp.pipelines.collect.load_sources", return_value=sources):
            items, _ = await collect_content_items(
                categories=["Tech"],
                window_name="manual",
                max_items=10,
                state_store=store,
                feed_adapter=mock_feed,
            )

        # Only the second article should be collected
        assert len(items) == 1
        assert items[0].link == "https://cryptofeed.example.com/update"


# ─── Full publish flow ────────────────────────────────────────────────────────


class TestPublishPipeline:
    @pytest.fixture
    def saved_report(self, store):
        report = ContentReport(
            report_id="e2e-report-001",
            category="Tech",
            window_name="morning",
            window_start="2026-03-04T00:00:00+00:00",
            window_end="2026-03-04T07:00:00+00:00",
            summary_lines=["AI breakthrough today.", "Markets steady."],
            insights=["Strong AI signals.", "Monitor volatility."],
            channel_drafts=[ChannelDraft(channel="x", status="draft", content="Tech brief")],
            asset_status="draft",
            approval_state="manual",
            source_links=["https://example.com/ai"],
            status="draft",
            fingerprint="e2e-fp-001",
            created_at="2026-03-04T00:00:00+00:00",
            updated_at="2026-03-04T00:00:00+00:00",
        )
        store.save_report(report)
        return report

    @pytest.mark.asyncio
    async def test_publish_creates_notion_page(self, store, saved_report):
        from antigravity_mcp.pipelines.publish import publish_report

        mock_notion = MagicMock(spec=NotionAdapter)
        mock_notion.is_configured.return_value = True
        mock_notion.query_database.return_value = ([], "")
        mock_notion.create_record.return_value = {
            "id": "notion-page-123",
            "url": "https://notion.so/page-123",
        }
        mock_telegram = MagicMock()
        mock_telegram.send_message = AsyncMock(return_value=True)

        fake_settings = MagicMock(
            content_approval_mode="manual",
            notion_reports_database_id="db-123",
            auto_push_enabled=False,
        )
        with patch("antigravity_mcp.pipelines.publish.get_settings", return_value=fake_settings):
            run_id, publication, warnings, status = await publish_report(
                report_id=saved_report.report_id,
                channels=["x"],
                approval_mode="manual",
                state_store=store,
                notion_adapter=mock_notion,
                telegram_adapter=mock_telegram,
            )

        assert "notion_page_id" in publication
        assert publication["notion_page_id"] == "notion-page-123"
        mock_telegram.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_telegram_failure_is_non_fatal(self, store, saved_report):
        from antigravity_mcp.pipelines.publish import publish_report

        mock_notion = MagicMock()
        mock_notion.is_configured.return_value = False

        mock_telegram = MagicMock()
        mock_telegram.send_message = AsyncMock(side_effect=RuntimeError("Telegram down"))

        fake_settings = MagicMock(
            content_approval_mode="manual",
            notion_reports_database_id="",
            auto_push_enabled=False,
        )
        with patch("antigravity_mcp.pipelines.publish.get_settings", return_value=fake_settings):
            # Should NOT raise even if Telegram fails
            run_id, publication, warnings, status = await publish_report(
                report_id=saved_report.report_id,
                channels=["x"],
                approval_mode="manual",
                state_store=store,
                notion_adapter=mock_notion,
                telegram_adapter=mock_telegram,
            )

        assert status in ("ok", "partial")  # pipeline continues despite Telegram error


# ─── Ops tools ───────────────────────────────────────────────────────────────


class TestOpsTools:
    @pytest.mark.asyncio
    async def test_ops_cleanup_dry_run_returns_no_deletions(self, store):
        from antigravity_mcp.tooling.ops_tools import ops_cleanup_tool

        with patch("antigravity_mcp.tooling.ops_tools.PipelineStateStore", return_value=store):  # type: ignore[assignment]
            result = await ops_cleanup_tool(dry_run=True)

        assert result["status"] == "ok"
        assert result["data"]["dry_run"] is True

    @pytest.mark.asyncio
    async def test_ops_cleanup_prunes_expired_cache(self, store):
        # Insert an expired LLM cache entry (expires_at in the past)

        from antigravity_mcp.tooling.ops_tools import ops_cleanup_tool

        store._connect().execute(
            """INSERT OR REPLACE INTO llm_cache
               (prompt_hash, response_text, model_name, input_tokens, output_tokens, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "expired-hash",
                "old response",
                "gemini",
                100,
                50,
                "2024-01-01T00:00:00+00:00",
                "2024-01-02T00:00:00+00:00",
            ),
        )
        store._connect().commit()

        with patch("antigravity_mcp.tooling.ops_tools.PipelineStateStore", return_value=store):
            result = await ops_cleanup_tool(dry_run=False)

        assert result["data"]["llm_cache_entries_pruned"] >= 1

    @pytest.mark.asyncio
    async def test_ops_check_health_returns_healthy_on_empty_db(self, store):
        from antigravity_mcp.tooling.ops_tools import ops_check_health_tool

        with (
            patch("antigravity_mcp.tooling.ops_tools.PipelineStateStore", return_value=store),
            patch("antigravity_mcp.tooling.ops_tools.TelegramAdapter") as mock_tg_cls,
        ):
            mock_tg = MagicMock()
            mock_tg.send_message = AsyncMock(return_value=True)
            mock_tg_cls.return_value = mock_tg

            result = await ops_check_health_tool(error_rate_threshold=0.20, alert_on_silence_hours=24)

        # On an empty DB, there are no runs → "no runs" alert fires
        assert result["status"] == "ok"
        assert "health" in result["data"]
        # Alert for silence (no runs in 24h) should be present
        assert len(result["data"]["alerts"]) >= 1


# ─── Skill Integrator ─────────────────────────────────────────────────────────


class TestSkillAdapter:
    @pytest.mark.asyncio
    async def test_invoke_unknown_skill_returns_error(self):
        from antigravity_mcp.integrations.skill_adapter import SkillAdapter

        adapter = SkillAdapter()
        result = await adapter.invoke("nonexistent_skill", {})
        assert result["status"] == "error"
        assert "nonexistent_skill" in result["message"]

    @pytest.mark.asyncio
    async def test_list_skills_returns_all_builtins(self):
        from antigravity_mcp.integrations.skill_adapter import SkillAdapter

        adapter = SkillAdapter()
        skills = adapter.list_skills()
        expected = {"summarize_category", "market_snapshot", "proofread", "brain_analysis", "sentiment_classify"}
        assert expected.issubset(set(skills))

    @pytest.mark.asyncio
    async def test_invoke_summarize_category_requires_category(self):
        from antigravity_mcp.integrations.skill_adapter import SkillAdapter

        adapter = SkillAdapter()
        result = await adapter.invoke("summarize_category", {})  # missing 'category'
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_register_custom_skill(self):
        from antigravity_mcp.integrations.skill_adapter import SkillAdapter

        async def my_skill(params):
            return {"echo": params.get("value")}

        adapter = SkillAdapter()
        adapter.register("echo_test", my_skill)
        result = await adapter.invoke("echo_test", {"value": "hello"})
        assert result["status"] == "ok"
        assert result["result"]["echo"] == "hello"

    @pytest.mark.asyncio
    async def test_invoke_skill_error_is_caught(self):
        from antigravity_mcp.integrations.skill_adapter import SkillAdapter

        async def bad_skill(params):
            raise RuntimeError("internal skill error")

        adapter = SkillAdapter()
        adapter.register("bad_skill", bad_skill)
        result = await adapter.invoke("bad_skill", {})
        assert result["status"] == "error"
        assert "internal skill error" in result["message"]
