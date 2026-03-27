"""Pipeline unit tests for collect, analyze, publish, and dashboard pipelines."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from antigravity_mcp.domain.models import ChannelDraft, ContentItem, ContentReport
from antigravity_mcp.state.store import PipelineStateStore


# ─── Fixtures ────────────────────────────────────────────────────────────────

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


# ─── collect pipeline ────────────────────────────────────────────────────────

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
            title="Old Article", link="https://seen.example.com/old",
            summary="Already seen", published_parsed=None,
        )
        mock_adapter = MagicMock()
        mock_adapter.fetch_entries = AsyncMock(return_value=[entry])

        with patch("antigravity_mcp.pipelines.collect.load_sources", return_value={"Tech": [{"name": "TestSource", "url": "http://test.rss"}]}):
            items, warnings = await collect_content_items(
                categories=["Tech"], window_name="manual", max_items=5,
                state_store=state_store, feed_adapter=mock_adapter,
            )

        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_collect_handles_feed_failure_gracefully(self, state_store):
        from antigravity_mcp.pipelines.collect import collect_content_items

        mock_adapter = MagicMock()
        mock_adapter.fetch_entries = AsyncMock(side_effect=ConnectionError("timeout"))

        with patch("antigravity_mcp.pipelines.collect.load_sources", return_value={"Tech": [{"name": "FailSource", "url": "http://fail.rss"}]}):
            items, warnings = await collect_content_items(
                categories=["Tech"], window_name="manual", max_items=5,
                state_store=state_store, feed_adapter=mock_adapter,
            )

        assert len(items) == 0
        assert any("FailSource" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_collect_parallel_fetches_multiple_sources(self, state_store):
        from antigravity_mcp.pipelines.collect import collect_content_items

        entry_a = SimpleNamespace(title="A", link="https://a.example.com", summary="aa", published_parsed=None)
        entry_b = SimpleNamespace(title="B", link="https://b.example.com", summary="bb", published_parsed=None)

        call_order = []

        async def fake_fetch(url):
            call_order.append(url)
            if "source-a" in url:
                return [entry_a]
            return [entry_b]

        mock_adapter = MagicMock()
        mock_adapter.fetch_entries = fake_fetch

        sources = {"Tech": [
            {"name": "SourceA", "url": "http://source-a.rss"},
            {"name": "SourceB", "url": "http://source-b.rss"},
        ]}
        with patch("antigravity_mcp.pipelines.collect.load_sources", return_value=sources):
            items, warnings = await collect_content_items(
                categories=["Tech"], window_name="manual", max_items=10,
                state_store=state_store, feed_adapter=mock_adapter,
            )

        assert len(items) == 2
        assert len(warnings) == 0


# ─── analyze pipeline ────────────────────────────────────────────────────────

class TestAnalyzePipeline:
    @pytest.mark.asyncio
    async def test_generate_briefs_creates_reports(self, state_store, sample_items):
        from antigravity_mcp.pipelines.analyze import generate_briefs

        mock_llm = MagicMock()
        mock_llm.build_report_payload = AsyncMock(return_value=(
            (["Summary line 1"], ["Insight 1"], [ChannelDraft(channel="x", status="draft", content="Draft")]),
            [],
        ))

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

    @pytest.mark.asyncio
    async def test_generate_briefs_reuses_existing_fingerprint(self, state_store, sample_items):
        from antigravity_mcp.pipelines.analyze import generate_briefs

        mock_llm = MagicMock()
        mock_llm.build_report_payload = AsyncMock(return_value=(
            (["Summary"], ["Insight"], [ChannelDraft(channel="x", status="draft", content="Draft")]),
            [],
        ))

        # First call
        _, reports1, _, _ = await generate_briefs(
            items=sample_items, window_name="manual",
            window_start="2026-03-03T00:00:00+00:00", window_end="2026-03-04T00:00:00+00:00",
            state_store=state_store, llm_adapter=mock_llm,
        )

        # Second call with same items → should reuse
        _, reports2, warnings2, _ = await generate_briefs(
            items=sample_items, window_name="manual",
            window_start="2026-03-03T00:00:00+00:00", window_end="2026-03-04T00:00:00+00:00",
            state_store=state_store, llm_adapter=mock_llm,
        )

        assert reports1[0].report_id == reports2[0].report_id
        assert any("Reused" in w for w in warnings2)


# ─── publish pipeline ────────────────────────────────────────────────────────

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

        assert status == "error"
        assert any("Unknown" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_publish_without_notion_stores_locally(self, state_store, sample_report):
        from antigravity_mcp.pipelines.publish import publish_report

        state_store.save_report(sample_report)

        mock_notion = MagicMock()
        mock_notion.is_configured.return_value = False

        run_id, publication, warnings, status = await publish_report(
            report_id=sample_report.report_id,
            channels=["x"],
            approval_mode="manual",
            state_store=state_store,
            notion_adapter=mock_notion,
        )

        assert "report_id" in publication
        assert any("not configured" in w for w in warnings)


# ─── dashboard pipeline ──────────────────────────────────────────────────────

class TestDashboardPipeline:
    @pytest.mark.asyncio
    async def test_refresh_dashboard_without_notion(self, state_store):
        from antigravity_mcp.pipelines.dashboard import refresh_dashboard

        mock_notion = MagicMock()
        mock_notion.is_configured.return_value = False

        run_id, payload, warnings, status = await refresh_dashboard(
            state_store=state_store,
            notion_adapter=mock_notion,
        )

        assert "reports" in payload
        assert "runs" in payload
        assert any("not configured" in w for w in warnings)


# ─── state store ──────────────────────────────────────────────────────────────

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
        assert run.status == "success"
        assert run.processed_count == 5

    def test_report_fingerprint_dedup(self, state_store, sample_report):
        state_store.save_report(sample_report)
        found = state_store.find_report_by_fingerprint(sample_report.fingerprint)
        assert found is not None
        assert found.report_id == sample_report.report_id

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
        """Watchdog: runs stuck in 'running' > 30 min are auto-marked 'failed'."""
        state_store.record_job_start("stale-run", "test_job")
        conn = state_store._connect()
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
        conn.execute("UPDATE job_runs SET started_at = ? WHERE run_id = ?", (old_time, "stale-run"))
        conn.commit()

        cleaned = state_store.cleanup_stale_runs(max_age_minutes=30)
        assert cleaned == 1

        run = state_store.get_run("stale-run")
        assert run.status == "failed"
        assert "auto-cleaned" in run.error_text

    def test_cleanup_stale_runs_ignores_recent(self, state_store):
        """Watchdog should NOT clean runs that are still within timeout."""
        state_store.record_job_start("recent-run", "test_job")
        cleaned = state_store.cleanup_stale_runs(max_age_minutes=30)
        assert cleaned == 0

        run = state_store.get_run("recent-run")
        assert run.status == "running"


# ─── v2 prompt parser ────────────────────────────────────────────────────────

class TestV2PromptParser:
    def test_parse_v2_response_extracts_all_sections(self):
        from antigravity_mcp.integrations.llm_adapter import LLMAdapter
        adapter = LLMAdapter()
        v2_text = """### 📌 Signal
OpenAI's $40B raise at $340B valuation sets a new floor for frontier AI company valuations.

### 🔗 Pattern
This signal connects to rising GPU demand → because NVIDIA earnings beat estimates → which also explains the semiconductor supply crunch.

### 🌊 Ripple Effects
- 1st order: Competition for AI talent intensifies.
- 2nd order: Mid-tier AI startups face higher funding bar within 6 months.
- 3rd order: Regulatory pressure on AI monopoly risk increases by 2027.

### ⚡ Counterpoint
Despite the headline valuation, OpenAI's revenue-to-valuation ratio (2%) is historically low compared to tech IPOs of the 2010s.

### ✅ Action Items
- Startup founder: Begin building defensible data moats this week.
- Investor: Monitor secondary market pricing for frontier AI lab equity before Q2.
- Developer/Engineer: Evaluate open-weight alternatives (Llama 4, Mistral) within 30 days.

### 📰 Draft Post (X/Twitter)
OpenAI just raised $40B. But here's what nobody's talking about:
Their revenue-to-valuation ratio is 2%. That's 5x worse than Google's IPO.
If you're a developer, now is the time to bet on open-weight models.
"""
        items = [
            ContentItem(
                source_name="TechCrunch", category="Tech", title="OpenAI Raises $40B",
                link="https://example.com/openai", published_at="", summary="OpenAI fundraise."
            ),
        ]
        summary, insights, drafts = adapter._parse_v2_response(
            category="Tech", text=v2_text, items=items, window_name="morning"
        )
        assert len(summary) >= 1
        assert "OpenAI" in summary[0]
        assert len(insights) >= 4  # pattern + ripple + counterpoint + action
        assert any("Counterpoint" in i or "revenue-to-valuation" in i for i in insights)
        assert any(d.channel == "x" for d in drafts)
        assert any("$40B" in d.content for d in drafts)


class TestContentTools:
    @pytest.mark.asyncio
    async def test_generate_brief_normalizes_comma_separated_categories(self, monkeypatch):
        from antigravity_mcp.tooling import content_tools

        captured = {}

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
