from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from antigravity_mcp.domain.models import ChannelDraft, ContentReport


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


class TestDashboardFormatting:
    def test_health_cost_metrics_and_recent_reports_markdown(self):
        from antigravity_mcp.pipelines.dashboard import (
            _cost_markdown,
            _health_markdown,
            _metrics_markdown,
            _recent_reports_markdown,
        )

        health = _health_markdown(
            {
                "last_run_at": "2026-04-01T01:00:00+00:00",
                "last_run_status": "success",
                "success_count_24h": 4,
                "failure_count_24h": 1,
                "total_runs_24h": 5,
                "avg_latency_seconds": 12.5,
                "error_rate": 0.2,
            }
        )
        cost = _cost_markdown(
            {
                "call_count": 10,
                "cache_hit_count": 4,
                "estimated_cost_usd": 1.23,
                "estimated_cost_avoided_usd": 0.45,
                "cost_by_model": {"gpt-5": 0.9, "gemini": 0.33},
            }
        )
        metrics = _metrics_markdown(
            {
                "total_tweets": 5,
                "total_impressions": 1500,
                "total_likes": 75,
                "total_retweets": 12,
                "avg_impressions": 300,
                "avg_likes": 15,
                "period_days": 7,
            }
        )
        reports = _recent_reports_markdown(
            [
                {
                    "category": "Tech",
                    "window_name": "morning",
                    "quality_state": "ok",
                    "generation_mode": "v1-brief",
                    "approval_state": "manual",
                }
            ]
        )

        assert "Pipeline Health" in health
        assert "20.0%" in health
        assert "gpt-5" in cost
        assert "40%" in cost
        assert "Tweets tracked: 5" in metrics
        assert "Tech | morning" in reports

    def test_metrics_and_recent_reports_handle_empty_inputs(self):
        from antigravity_mcp.pipelines.dashboard import _governance_markdown, _metrics_markdown, _recent_reports_markdown

        assert _metrics_markdown({"total_tweets": 0}) == ""
        assert "No reports yet." in _recent_reports_markdown([])

        governance = _governance_markdown(
            {
                "quality_counts": {},
                "approval_counts": {},
                "fallback_x_drafts": 0,
                "reports_considered": 0,
            }
        )

        assert "Quality states: none" in governance
        assert "Approval states: none" in governance

    def test_dashboard_markdown_stitches_all_sections(self):
        from antigravity_mcp.pipelines.dashboard import _dashboard_markdown

        markdown = _dashboard_markdown(
            {"reports": 3, "runs": 4, "cached_articles": 5},
            [{"job_name": "collect", "status": "success", "started_at": "2026-04-01T00:00:00+00:00"}],
            [{"category": "Tech", "window_name": "manual", "quality_state": "ok", "generation_mode": "", "approval_state": "manual"}],
            {"quality_counts": {"ok": 1}, "approval_counts": {"manual": 1}, "fallback_x_drafts": 0, "reports_considered": 1},
            {"last_run_at": "2026-04-01T00:00:00+00:00", "last_run_status": "success", "success_count_24h": 1, "failure_count_24h": 0, "total_runs_24h": 1, "avg_latency_seconds": None, "error_rate": 0.0},
            {"call_count": 0, "cache_hit_count": 0, "estimated_cost_usd": 0.0, "estimated_cost_avoided_usd": 0.0, "cost_by_model": {}},
            {"total_tweets": 2, "total_impressions": 100, "total_likes": 5, "total_retweets": 1, "avg_impressions": 50, "avg_likes": 2.5, "period_days": 7},
        )

        assert "[AUTO_DASHBOARD]" in markdown
        assert "Pipeline Health" in markdown
        assert "LLM Cost" in markdown
        assert "X Performance" in markdown
        assert "Governance Snapshot" in markdown
        assert "Recent Runs" in markdown


class TestDashboardRefresh:
    @pytest.mark.asyncio
    async def test_refresh_dashboard_updates_notion_when_configured(self, state_store, sample_report):
        from antigravity_mcp.pipelines.dashboard import refresh_dashboard

        sample_report.quality_state = "ok"
        state_store.save_report(sample_report)
        state_store.record_job_start("run-1", "collect")
        state_store.record_job_finish("run-1", status="success")

        mock_notion = MagicMock()
        mock_notion.is_configured.return_value = True
        mock_notion.replace_auto_dashboard_blocks = AsyncMock(return_value=7)

        fake_settings = MagicMock(notion_dashboard_page_id="page-123")
        with patch("antigravity_mcp.pipelines.dashboard.get_settings", return_value=fake_settings):
            run_id, payload, warnings, status = await refresh_dashboard(
                state_store=state_store,
                notion_adapter=mock_notion,
                run_id="refresh-1",
            )

        assert run_id == "refresh-1"
        assert status == "ok"
        assert warnings == []
        assert payload["updated_blocks"] == 7
        assert payload["dashboard_page_id"] == "page-123"
        mock_notion.replace_auto_dashboard_blocks.assert_awaited_once()

        saved_run = state_store.get_run("refresh-1")
        assert saved_run is not None
        assert saved_run.status == "success"

    @pytest.mark.asyncio
    async def test_refresh_dashboard_returns_partial_without_notion_page(self, state_store):
        from antigravity_mcp.pipelines.dashboard import refresh_dashboard

        mock_notion = MagicMock()
        mock_notion.is_configured.return_value = True

        fake_settings = MagicMock(notion_dashboard_page_id="")
        with patch("antigravity_mcp.pipelines.dashboard.get_settings", return_value=fake_settings):
            _, payload, warnings, status = await refresh_dashboard(
                state_store=state_store,
                notion_adapter=mock_notion,
                run_id="refresh-2",
            )

        assert status == "partial"
        assert payload["dashboard_page_id"] == ""
        assert any("not configured" in warning for warning in warnings)
        mock_notion.replace_auto_dashboard_blocks.assert_not_called()
