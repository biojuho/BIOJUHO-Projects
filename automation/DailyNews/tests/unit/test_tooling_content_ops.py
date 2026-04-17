from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


def _report(report_id: str) -> SimpleNamespace:
    return SimpleNamespace(report_id=report_id, to_dict=lambda: {"report_id": report_id})


class TestContentTools:
    @pytest.mark.asyncio
    async def test_content_generate_brief_returns_partial_when_no_items_have_warnings(self, monkeypatch):
        from antigravity_mcp.tooling import content_tools

        async def fake_collect_content_items(*, categories, window_name, max_items, state_store):
            assert categories is None
            assert window_name == "manual"
            assert max_items == 5
            return [], ["feed timeout"]

        monkeypatch.setattr(content_tools, "collect_content_items", fake_collect_content_items)

        result = await content_tools.content_generate_brief_tool()

        assert result["status"] == "partial"
        assert result["meta"]["warnings"] == ["feed timeout"]
        assert result["data"]["report_ids"] == []

    @pytest.mark.asyncio
    async def test_content_generate_brief_returns_error_when_collection_fails(self, monkeypatch):
        from antigravity_mcp.tooling import content_tools

        async def fake_collect_content_items(*, categories, window_name, max_items, state_store):
            raise RuntimeError("collector exploded")

        alert = AsyncMock()
        monkeypatch.setattr(content_tools, "collect_content_items", fake_collect_content_items)
        monkeypatch.setattr(content_tools, "_alert_on_error", alert)

        result = await content_tools.content_generate_brief_tool(categories=["Tech"])

        assert result["status"] == "error"
        assert result["error"]["code"] == "collect_failed"
        alert.assert_awaited_once()
        assert alert.await_args.args[:3] == ("collect", "RuntimeError", "collector exploded")

    @pytest.mark.asyncio
    async def test_content_generate_brief_returns_error_when_analysis_fails(self, monkeypatch):
        from antigravity_mcp.tooling import content_tools

        async def fake_collect_content_items(*, categories, window_name, max_items, state_store):
            return [SimpleNamespace(category="Tech")], []

        async def fake_generate_briefs(**kwargs):
            raise RuntimeError("analysis exploded")

        alert = AsyncMock()
        monkeypatch.setattr(content_tools, "collect_content_items", fake_collect_content_items)
        monkeypatch.setattr(content_tools, "generate_briefs", fake_generate_briefs)
        monkeypatch.setattr(
            content_tools,
            "get_window",
            lambda window: (
                SimpleNamespace(isoformat=lambda: "2026-04-01T00:00:00+00:00"),
                SimpleNamespace(isoformat=lambda: "2026-04-01T06:00:00+00:00"),
            ),
        )
        monkeypatch.setattr(content_tools, "_alert_on_error", alert)

        result = await content_tools.content_generate_brief_tool(categories=["Tech"])

        assert result["status"] == "error"
        assert result["error"]["code"] == "analyze_failed"
        alert.assert_awaited_once()
        assert alert.await_args.args[:3] == ("analyze", "RuntimeError", "analysis exploded")

    @pytest.mark.asyncio
    async def test_content_generate_brief_returns_partial_with_reports_and_warnings(self, monkeypatch):
        from antigravity_mcp.tooling import content_tools

        async def fake_collect_content_items(*, categories, window_name, max_items, state_store):
            return [SimpleNamespace(category="Tech")], ["collect warning"]

        async def fake_generate_briefs(**kwargs):
            return "run-123", [_report("report-1")], ["llm warning"], "partial"

        monkeypatch.setattr(content_tools, "collect_content_items", fake_collect_content_items)
        monkeypatch.setattr(content_tools, "generate_briefs", fake_generate_briefs)
        monkeypatch.setattr(
            content_tools,
            "get_window",
            lambda window: (
                SimpleNamespace(isoformat=lambda: "2026-04-01T00:00:00+00:00"),
                SimpleNamespace(isoformat=lambda: "2026-04-01T06:00:00+00:00"),
            ),
        )

        result = await content_tools.content_generate_brief_tool(categories=["Tech"])

        assert result["status"] == "partial"
        assert result["meta"]["run_id"] == "run-123"
        assert result["meta"]["warnings"] == ["collect warning", "llm warning"]
        assert result["data"]["report_ids"] == ["report-1"]

    @pytest.mark.asyncio
    async def test_content_publish_report_tool_surfaces_partial_and_error_states(self, monkeypatch):
        from antigravity_mcp.tooling import content_tools

        publish_partial = AsyncMock(return_value=("run-1", {"report_id": "r1"}, ["needs review"], "partial"))
        monkeypatch.setattr(content_tools, "publish_report", publish_partial)

        partial_result = await content_tools.content_publish_report_tool("r1")

        assert partial_result["status"] == "partial"
        assert partial_result["meta"]["run_id"] == "run-1"
        assert partial_result["meta"]["warnings"] == ["needs review"]

        publish_error = AsyncMock(return_value=("run-2", {}, ["publish broke"], "error"))
        alert = AsyncMock()
        monkeypatch.setattr(content_tools, "publish_report", publish_error)
        monkeypatch.setattr(content_tools, "_alert_on_error", alert)

        error_result = await content_tools.content_publish_report_tool("r2")

        assert error_result["status"] == "error"
        assert error_result["error"]["code"] == "publish_failed"
        assert error_result["data"]["run_id"] == "run-2"
        alert.assert_awaited_once()
        assert alert.await_args.args == ("publish", "publish_error", "publish broke", "r2")

    @pytest.mark.asyncio
    async def test_content_publish_report_tool_alerts_when_publish_raises(self, monkeypatch):
        from antigravity_mcp.tooling import content_tools

        async def fake_publish_report(**kwargs):
            raise RuntimeError("network down")

        alert = AsyncMock()
        monkeypatch.setattr(content_tools, "publish_report", fake_publish_report)
        monkeypatch.setattr(content_tools, "_alert_on_error", alert)

        result = await content_tools.content_publish_report_tool("r1")

        assert result["status"] == "error"
        assert result["error"]["code"] == "publish_failed"
        alert.assert_awaited_once()
        assert alert.await_args.args == ("publish", "RuntimeError", "network down", "r1")

    @pytest.mark.asyncio
    async def test_content_invoke_skill_tool_wraps_success_and_error(self, monkeypatch):
        from antigravity_mcp.tooling import content_tools

        adapter = MagicMock()
        adapter.invoke = AsyncMock(
            side_effect=[
                {"status": "error", "message": "bad skill", "detail": 1},
                {"status": "ok", "result": {"headline": "ready"}},
            ]
        )
        monkeypatch.setattr(content_tools, "SkillAdapter", lambda: adapter)

        error_result = await content_tools.content_invoke_skill_tool("proofread", {"text": "draft"})
        ok_result = await content_tools.content_invoke_skill_tool("proofread", {"text": "draft"})

        assert error_result["status"] == "error"
        assert error_result["error"]["code"] == "skill_error"
        assert error_result["data"]["message"] == "bad skill"
        assert ok_result["status"] == "ok"
        assert ok_result["data"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_alert_on_error_skips_unconfigured_and_swallows_failures(self, monkeypatch):
        from antigravity_mcp.tooling import content_tools

        unconfigured = MagicMock(is_configured=False)
        unconfigured.send_error_alert = AsyncMock()
        monkeypatch.setattr(content_tools, "TelegramAdapter", lambda: unconfigured)

        await content_tools._alert_on_error("collect", "RuntimeError", "boom")

        unconfigured.send_error_alert.assert_not_called()

        broken = MagicMock(is_configured=True)
        broken.send_error_alert = AsyncMock(side_effect=RuntimeError("telegram down"))
        monkeypatch.setattr(content_tools, "TelegramAdapter", lambda: broken)

        await content_tools._alert_on_error("publish", "RuntimeError", "boom", "run-1")


class TestOpsTools:
    @pytest.mark.asyncio
    async def test_ops_get_run_status_and_list_runs(self, state_store, monkeypatch):
        from antigravity_mcp.tooling import ops_tools

        state_store.record_job_start("run-1", "collect")
        state_store.record_job_finish("run-1", status="success", summary={"items": 1})
        monkeypatch.setattr(ops_tools, "PipelineStateStore", lambda: state_store)

        found = await ops_tools.ops_get_run_status_tool("run-1")
        missing = await ops_tools.ops_get_run_status_tool("run-404")
        listed = await ops_tools.ops_list_runs_tool(job_name="collect", status="success", limit=5)

        assert found["status"] == "ok"
        assert found["data"]["run"]["run_id"] == "run-1"
        assert missing["status"] == "error"
        assert missing["error"]["code"] == "run_not_found"
        assert listed["status"] == "ok"
        assert listed["data"]["runs"][0]["run_id"] == "run-1"

    @pytest.mark.asyncio
    async def test_ops_refresh_dashboard_wraps_ok_and_partial(self, monkeypatch):
        from antigravity_mcp.tooling import ops_tools

        refresh = AsyncMock(
            side_effect=[
                ("run-ok", {"reports": []}, [], "ok"),
                ("run-partial", {"reports": []}, ["notion missing"], "partial"),
            ]
        )
        monkeypatch.setattr(ops_tools, "refresh_dashboard", refresh)

        ok_result = await ops_tools.ops_refresh_dashboard_tool()
        partial_result = await ops_tools.ops_refresh_dashboard_tool()

        assert ok_result["status"] == "ok"
        assert ok_result["meta"]["run_id"] == "run-ok"
        assert partial_result["status"] == "partial"
        assert partial_result["meta"]["warnings"] == ["notion missing"]

    @pytest.mark.asyncio
    async def test_ops_resync_report_wraps_ok_partial_and_error(self, state_store, monkeypatch):
        from antigravity_mcp.tooling import ops_tools

        monkeypatch.setattr(ops_tools, "PipelineStateStore", lambda: state_store)
        resync = AsyncMock(
            side_effect=[
                ("run-ok", {"report_id": "report-1"}, [], "ok"),
                ("run-partial", {"report_id": "report-2"}, ["missing page id"], "partial"),
                ("run-error", {}, ["Unknown report_id: report-404"], "error"),
            ]
        )
        monkeypatch.setattr(ops_tools, "resync_report_publication", resync)

        ok_result = await ops_tools.ops_resync_report_tool("report-1")
        partial_result = await ops_tools.ops_resync_report_tool("report-2")
        error_result = await ops_tools.ops_resync_report_tool("report-404")

        assert ok_result["status"] == "ok"
        assert ok_result["meta"]["run_id"] == "run-ok"
        assert partial_result["status"] == "partial"
        assert partial_result["meta"]["warnings"] == ["missing page id"]
        assert error_result["status"] == "error"
        assert error_result["error"]["code"] == "report_not_found"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("side_effect", "expected_code"),
        [
            (FileNotFoundError("missing dataset"), "dataset_not_found"),
            (ValueError("bad dataset"), "invalid_dataset"),
            (RuntimeError("unexpected"), "frozen_eval_failed"),
        ],
    )
    async def test_ops_run_frozen_eval_tool_handles_errors(self, monkeypatch, side_effect, expected_code):
        from antigravity_mcp.tooling import ops_tools

        async def fake_run_frozen_eval(**kwargs):
            raise side_effect

        monkeypatch.setattr(ops_tools, "run_frozen_eval", fake_run_frozen_eval)

        result = await ops_tools.ops_run_frozen_eval_tool("dataset.json", "out.json", "state.db")

        assert result["status"] == "error"
        assert result["error"]["code"] == expected_code

    @pytest.mark.asyncio
    async def test_ops_auto_collect_metrics_tool_returns_ok_and_partial(self, monkeypatch):
        from antigravity_mcp.tooling import ops_tools
        import antigravity_mcp.pipelines.metrics as metrics_module

        async def fake_collect_recent_metrics(*, state_store, hours):
            return "metrics-run", 2, []

        monkeypatch.setattr(metrics_module, "collect_recent_metrics", fake_collect_recent_metrics)
        ok_result = await ops_tools.ops_auto_collect_metrics_tool(hours=24)

        async def fake_collect_recent_metrics_partial(*, state_store, hours):
            return "metrics-run-2", 1, ["rate limited"]

        monkeypatch.setattr(metrics_module, "collect_recent_metrics", fake_collect_recent_metrics_partial)
        partial_result = await ops_tools.ops_auto_collect_metrics_tool(hours=12)

        assert ok_result["status"] == "ok"
        assert ok_result["data"]["tweets_updated"] == 2
        assert partial_result["status"] == "partial"
        assert partial_result["meta"]["warnings"] == ["rate limited"]

    @pytest.mark.asyncio
    async def test_ops_collect_tweet_metrics_tool_handles_unavailable_and_success(self, monkeypatch):
        from antigravity_mcp.tooling import ops_tools

        unavailable = SimpleNamespace(is_available=False)
        monkeypatch.setattr(ops_tools, "XMetricsAdapter", lambda state_store: unavailable)
        unavailable_result = await ops_tools.ops_collect_tweet_metrics_tool(["1"])

        collector = MagicMock(is_available=True)
        collector.collect_and_store = AsyncMock(return_value=3)
        monkeypatch.setattr(ops_tools, "XMetricsAdapter", lambda state_store: collector)
        ok_result = await ops_tools.ops_collect_tweet_metrics_tool(["1", "2"], report_id="report-1")

        assert unavailable_result["status"] == "error"
        assert unavailable_result["error"]["code"] == "x_bearer_missing"
        assert ok_result["status"] == "ok"
        assert ok_result["data"]["tweets_updated"] == 3
        collector.collect_and_store.assert_awaited_once_with(["1", "2"], report_id="report-1")

    @pytest.mark.asyncio
    async def test_ops_check_health_reports_healthy_and_degraded_states(self, monkeypatch):
        from antigravity_mcp.tooling import ops_tools

        healthy_store = MagicMock()
        healthy_store.get_pipeline_health.return_value = {"error_rate": 0.0, "total_runs_24h": 3, "failure_count_24h": 0}
        monkeypatch.setattr(ops_tools, "PipelineStateStore", lambda: healthy_store)
        monkeypatch.setattr(ops_tools, "_get_llm_client", object())
        monkeypatch.setattr(ops_tools, "_SHARED_LLM_IMPORT_ERROR", None)

        healthy_result = await ops_tools.ops_check_health_tool()

        degraded_store = MagicMock()
        degraded_store.get_pipeline_health.return_value = {"error_rate": 0.5, "total_runs_24h": 0, "failure_count_24h": 2}
        telegram = MagicMock()
        telegram.send_message = AsyncMock(return_value=False)
        monkeypatch.setattr(ops_tools, "PipelineStateStore", lambda: degraded_store)
        monkeypatch.setattr(ops_tools, "_get_llm_client", None)
        monkeypatch.setattr(ops_tools, "_SHARED_LLM_IMPORT_ERROR", RuntimeError("missing"))
        monkeypatch.setattr(ops_tools, "TelegramAdapter", lambda: telegram)

        degraded_result = await ops_tools.ops_check_health_tool(error_rate_threshold=0.2)

        assert healthy_result["status"] == "ok"
        assert healthy_result["data"]["status"] == "healthy"
        assert healthy_result["data"]["alerts"] == []
        assert degraded_result["status"] == "ok"
        assert degraded_result["data"]["status"] == "degraded"
        assert len(degraded_result["data"]["alerts"]) == 3
        telegram.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ops_get_cost_report_handles_shared_llm_presence_and_absence(self, monkeypatch):
        from antigravity_mcp.tooling import ops_tools

        store = MagicMock()
        store.get_token_usage_stats.side_effect = [
            {"total_cost": 12.5},
            {"total_cost": 12.5},
        ]
        monkeypatch.setattr(ops_tools, "PipelineStateStore", lambda: store)

        missing_shared = ModuleType("shared.llm")
        monkeypatch.setitem(sys.modules, "shared.llm", missing_shared)
        missing_result = await ops_tools.ops_get_cost_report_tool(days=3)

        fake_shared = ModuleType("shared.llm")
        fake_shared.export_usage_csv = lambda *args, **kwargs: "unused.csv"
        fake_shared.get_daily_stats = lambda *, days: [{"day": "2026-04-01", "cost": days}]
        monkeypatch.setitem(sys.modules, "shared.llm", fake_shared)
        present_result = await ops_tools.ops_get_cost_report_tool(days=5)

        assert missing_result["status"] == "ok"
        assert "daily_breakdown" not in missing_result["data"]
        assert present_result["status"] == "ok"
        assert present_result["data"]["daily_breakdown"] == [{"day": "2026-04-01", "cost": 5}]

    @pytest.mark.asyncio
    async def test_ops_export_calendar_and_performance_tools(self, monkeypatch):
        from antigravity_mcp.tooling import ops_tools
        import antigravity_mcp.integrations.scheduler_adapter as scheduler_module
        import antigravity_mcp.pipelines.export as export_module

        store = MagicMock()
        store.get_top_tweets.return_value = [{"tweet_id": "1"}]
        store.get_metrics_summary.return_value = {"impressions": 100}
        monkeypatch.setattr(ops_tools, "PipelineStateStore", lambda: store)

        monkeypatch.setattr(
            export_module,
            "export_daily_report_json",
            lambda *, date, state_store: {"path": f"{date or 'latest'}.json"},
        )
        monkeypatch.setattr(
            export_module,
            "export_performance_csv",
            lambda *, days, state_store: {"path": f"{days}.csv"},
        )

        class FakeScheduler:
            def __init__(self, state_store):
                self.state_store = state_store

            def get_optimal_hours(self, count):
                return [9, 12, 18][:count]

            def should_post_now(self):
                return True

            def get_next_posting_slot(self):
                return "2026-04-02T09:00:00+00:00"

        monkeypatch.setattr(scheduler_module, "SchedulerAdapter", FakeScheduler)

        export_result = await ops_tools.ops_export_analytics_tool(date="2026-04-01", days=14)
        calendar_result = await ops_tools.ops_get_content_calendar_tool(days=7)
        performance_result = await ops_tools.ops_get_tweet_performance_tool(days=7, limit=5, sort_by="likes")

        assert export_result["status"] == "ok"
        assert export_result["data"]["json_export"]["path"] == "2026-04-01.json"
        assert export_result["data"]["csv_export"]["path"] == "14.csv"
        assert calendar_result["status"] == "ok"
        assert calendar_result["data"]["should_post_now"] is True
        assert performance_result["status"] == "ok"
        assert performance_result["data"]["summary"]["impressions"] == 100
