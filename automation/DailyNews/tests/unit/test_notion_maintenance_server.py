from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestNotionTools:
    @pytest.mark.asyncio
    async def test_notion_search_tool_handles_not_configured_success_and_error(self, monkeypatch):
        from antigravity_mcp.domain.models import PageSummary
        from antigravity_mcp.integrations.notion_adapter import NotionAdapterError
        from antigravity_mcp.tooling import notion_tools

        settings = MagicMock(settings_warnings=["warn-1"])
        monkeypatch.setattr(notion_tools, "get_settings", lambda: settings)

        not_configured = MagicMock()
        not_configured.is_configured.return_value = False
        monkeypatch.setattr(notion_tools, "NotionAdapter", lambda settings=None: not_configured)
        result = await notion_tools.notion_search_tool("query")
        assert result["status"] == "error"
        assert result["error"]["code"] == "notion_not_configured"

        configured = MagicMock()
        configured.is_configured.return_value = True
        configured.search = AsyncMock(
            return_value=([PageSummary(id="page-1", title="Alpha", url="https://notion.so/alpha")], "cursor-1")
        )
        monkeypatch.setattr(notion_tools, "NotionAdapter", lambda settings=None: configured)
        result = await notion_tools.notion_search_tool("query")
        assert result["status"] == "ok"
        assert result["meta"]["cursor"] == "cursor-1"
        assert result["meta"]["warnings"] == ["warn-1"]
        assert result["data"]["results"][0]["id"] == "page-1"

        broken = MagicMock()
        broken.is_configured.return_value = True
        broken.search = AsyncMock(side_effect=NotionAdapterError("rate_limited", "slow down", retryable=True))
        monkeypatch.setattr(notion_tools, "NotionAdapter", lambda settings=None: broken)
        result = await notion_tools.notion_search_tool("query")
        assert result["status"] == "error"
        assert result["error"]["code"] == "rate_limited"
        assert result["error"]["retryable"] is True

    @pytest.mark.asyncio
    async def test_notion_page_tools_wrap_success_and_errors(self, monkeypatch):
        from antigravity_mcp.integrations.notion_adapter import NotionAdapterError
        from antigravity_mcp.tooling import notion_tools

        adapter = MagicMock()
        adapter.is_configured.return_value = True
        adapter.get_page = AsyncMock(return_value={"page": {"id": "page-1"}})
        adapter.create_page = AsyncMock(return_value={"id": "page-2"})
        adapter.append_markdown = AsyncMock(return_value={"appended": 3})
        monkeypatch.setattr(notion_tools, "NotionAdapter", lambda settings=None: adapter)

        page = await notion_tools.notion_get_page_tool("page-1", include_blocks=False, max_depth=2)
        created = await notion_tools.notion_create_page_tool("parent-1", "Title", "Body", {"foo": "bar"})
        appended = await notion_tools.notion_append_blocks_tool("page-1", "## body")

        assert page["status"] == "ok"
        assert created["data"]["id"] == "page-2"
        assert appended["data"]["appended"] == 3

        failing = MagicMock()
        failing.is_configured.return_value = True
        failing.get_page = AsyncMock(side_effect=NotionAdapterError("missing", "not found"))
        failing.create_page = AsyncMock(side_effect=NotionAdapterError("denied", "forbidden", retryable=True))
        failing.append_markdown = AsyncMock(side_effect=NotionAdapterError("bad_block", "bad block"))
        monkeypatch.setattr(notion_tools, "NotionAdapter", lambda settings=None: failing)

        page_error = await notion_tools.notion_get_page_tool("missing")
        create_error = await notion_tools.notion_create_page_tool("parent", "Title")
        append_error = await notion_tools.notion_append_blocks_tool("page", "Body")

        assert page_error["error"]["code"] == "missing"
        assert create_error["error"]["retryable"] is True
        assert append_error["error"]["code"] == "bad_block"

    @pytest.mark.asyncio
    async def test_notion_create_record_tool_handles_mapping_warnings_and_errors(self, monkeypatch):
        from antigravity_mcp.integrations.notion_adapter import NotionAdapterError
        from antigravity_mcp.tooling import notion_tools

        settings = MagicMock(
            notion_tasks_database_id="tasks-db",
            notion_reports_database_id="reports-db",
            settings_warnings=["warn-1"],
        )
        monkeypatch.setattr(notion_tools, "get_settings", lambda: settings)

        adapter = MagicMock()
        adapter.is_configured.return_value = True
        adapter.create_record = AsyncMock(return_value={"id": "record-1"})
        monkeypatch.setattr(notion_tools, "NotionAdapter", lambda settings=None: adapter)

        partial = await notion_tools.notion_create_record_tool("tasks", {"Name": "x"}, markdown="body")
        assert partial["status"] == "partial"
        assert partial["meta"]["warnings"] == ["warn-1"]

        settings.settings_warnings = []
        ok_result = await notion_tools.notion_create_record_tool("reports", {"Name": "x"})
        assert ok_result["status"] == "ok"
        adapter.create_record.assert_awaited_with(database_id="reports-db", properties={"Name": "x"}, markdown="")

        bad_db = await notion_tools.notion_create_record_tool("unknown", {})
        assert bad_db["error"]["code"] == "database_not_configured"

        adapter.create_record = AsyncMock(side_effect=NotionAdapterError("write_failed", "boom"))
        error_result = await notion_tools.notion_create_record_tool("tasks", {})
        assert error_result["error"]["code"] == "write_failed"


class TestMaintenancePipeline:
    def test_backup_db_creates_sqlite_backup(self, tmp_path: Path):
        from antigravity_mcp.pipelines.maintenance import backup_db
        from antigravity_mcp.state.store import PipelineStateStore

        store = PipelineStateStore(path=tmp_path / "pipeline_state.db")
        try:
            store.record_job_start("run-1", "collect")
            backup_path = Path(backup_db(state_store=store, dest_dir=tmp_path / "backups"))
        finally:
            store.close()

        assert backup_path.exists()
        assert backup_path.parent.name == "backups"

    @pytest.mark.asyncio
    async def test_run_daily_maintenance_success_and_backup_cleanup(self, tmp_path: Path):
        from antigravity_mcp.pipelines.maintenance import run_daily_maintenance
        from antigravity_mcp.state.store import PipelineStateStore

        store = PipelineStateStore(path=tmp_path / "pipeline_state.db")
        try:
            store.record_article(
                link="https://example.com/old",
                source="Feed",
                category="Tech",
                window_name="manual",
                notion_page_id=None,
                run_id="seed",
            )
            backup_dir = tmp_path / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            for idx in range(3):
                (backup_dir / f"pipeline_state_2026010{idx}_000000.db").write_text("old", encoding="utf-8")

            settings = MagicMock(data_dir=tmp_path)
            with patch("antigravity_mcp.pipelines.maintenance.get_settings", return_value=settings):
                result = await run_daily_maintenance(state_store=store, prune_articles_days=0, keep_backups=1)

            assert result["articles_pruned"] >= 1
            assert "backup_path" in result
            assert result["old_backups_removed"] >= 2
            saved_run = store.get_run(result["run_id"])
            assert saved_run is not None
            assert saved_run.status == "success"
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_run_daily_maintenance_records_backup_error(self, tmp_path: Path):
        from antigravity_mcp.pipelines import maintenance
        from antigravity_mcp.state.store import PipelineStateStore

        store = PipelineStateStore(path=tmp_path / "pipeline_state.db")
        try:
            with patch.object(maintenance, "backup_db", side_effect=RuntimeError("disk full")):
                result = await maintenance.run_daily_maintenance(state_store=store)

            assert result["backup_error"] == "disk full"
            assert "backup_path" not in result
        finally:
            store.close()


class FakeFastMCP:
    def __init__(self, name: str):
        self.name = name
        self.tools: dict[str, object] = {}
        self.resources: dict[str, object] = {}
        self.ran = False

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator

    def resource(self, uri: str):
        def decorator(func):
            self.resources[uri] = func
            return func

        return decorator

    def run(self):
        self.ran = True


class TestServer:
    @pytest.mark.asyncio
    async def test_build_server_registers_and_executes_tools(self, monkeypatch):
        import antigravity_mcp.server as server_module

        fake_settings = MagicMock()
        fake_settings.validate.return_value = ["missing value"]
        fake_settings.public_summary.return_value = {"env": "test"}
        monkeypatch.setattr(server_module, "FastMCP", FakeFastMCP)
        monkeypatch.setattr(server_module, "get_settings", lambda: fake_settings)
        monkeypatch.setattr(server_module, "configure_logging", lambda settings: None)

        async_map = {
            "notion_search_tool": AsyncMock(return_value={"status": "ok", "data": {"results": []}}),
            "notion_get_page_tool": AsyncMock(return_value={"status": "ok", "data": {"page": {}}}),
            "notion_create_page_tool": AsyncMock(return_value={"status": "ok", "data": {"id": "page"}}),
            "notion_append_blocks_tool": AsyncMock(return_value={"status": "ok", "data": {"appended": 1}}),
            "notion_create_record_tool": AsyncMock(return_value={"status": "ok", "data": {"id": "record"}}),
            "content_generate_brief_tool": AsyncMock(return_value={"status": "ok", "data": {"report_ids": []}}),
            "content_publish_report_tool": AsyncMock(return_value={"status": "ok", "data": {"report_id": "r1"}}),
            "content_invoke_skill_tool": AsyncMock(return_value={"status": "ok", "data": {"result": {}}}),
            "ops_get_run_status_tool": AsyncMock(return_value={"status": "ok", "data": {"run": {}}}),
            "ops_list_runs_tool": AsyncMock(return_value={"status": "ok", "data": {"runs": []}}),
            "ops_refresh_dashboard_tool": AsyncMock(return_value={"status": "ok", "data": {"reports": 1}}),
            "ops_run_frozen_eval_tool": AsyncMock(return_value={"status": "ok", "data": {"cases": []}}),
            "ops_cleanup_tool": AsyncMock(return_value={"status": "ok", "data": {"dry_run": True}}),
            "ops_check_health_tool": AsyncMock(return_value={"status": "ok", "data": {"status": "healthy"}}),
            "ops_auto_collect_metrics_tool": AsyncMock(return_value={"status": "ok", "data": {"tweets_updated": 1}}),
            "ops_collect_tweet_metrics_tool": AsyncMock(return_value={"status": "ok", "data": {"tweets_updated": 1}}),
            "ops_get_tweet_performance_tool": AsyncMock(return_value={"status": "ok", "data": {"summary": {}}}),
            "ops_get_cost_report_tool": AsyncMock(return_value={"status": "ok", "data": {"cost": 1}}),
            "ops_export_analytics_tool": AsyncMock(return_value={"status": "ok", "data": {"json_export": {}}}),
            "ops_get_content_calendar_tool": AsyncMock(return_value={"status": "ok", "data": {"next_slot": {}}}),
        }
        for name, mock in async_map.items():
            monkeypatch.setattr(server_module, name, mock)

        store = MagicMock()
        store.get_token_usage_stats.return_value = {"total_cost": 1.2}
        store.prune_llm_cache.return_value = 4
        monkeypatch.setattr(server_module, "PipelineStateStore", lambda: store)

        server = server_module.build_server()

        await server.tools["notion_search"]("q", "page", 5, "")
        await server.tools["notion_get_page"]("page-1", True, 1)
        await server.tools["notion_create_page"]("parent", "Title", "Body", {"a": 1})
        await server.tools["notion_append_blocks"]("page-1", "Body")
        await server.tools["notion_create_record"]("tasks", {"Name": "x"}, "Body")
        await server.tools["content_generate_brief"](["Tech"], "manual", 3)
        await server.tools["content_publish_report"]("report-1", ["x"], "manual")
        await server.tools["content_invoke_skill"]("proofread", {"text": "draft"})
        await server.tools["ops_get_run_status"]("run-1")
        await server.tools["ops_list_runs"]("job", "success", 5)
        await server.tools["ops_refresh_dashboard"]()
        await server.tools["ops_run_frozen_eval"]("dataset", "output", "state")
        await server.tools["ops_cleanup"](True)
        await server.tools["ops_check_health"](0.2, 24)
        await server.tools["ops_auto_collect_metrics"](48)
        await server.tools["ops_collect_tweet_metrics"](["1"], "report-1")
        await server.tools["ops_get_tweet_performance"](7, 10, "likes")
        await server.tools["ops_get_cost_report"](7)
        await server.tools["ops_export_analytics"]("2026-04-01", 30)
        await server.tools["ops_get_content_calendar"](7)

        token_usage = await server.tools["get_token_usage"](12)
        deprecated_search = await server.tools["search_notion"]("alpha")
        deprecated_read = await server.tools["read_page"]("page-1")
        deprecated_task = await server.tools["add_task"]("Title", "Body", "Task", "high", "goal", "achievement")
        deprecated_page = await server.tools["create_page"]("parent", "Title", "Body")
        deprecated_append = await server.tools["append_block"]("page-1", "Body")
        settings_json = server.resources["config://settings"]()

        assert server.name == "Antigravity Content Engine MCP"
        assert token_usage["status"] == "ok"
        assert token_usage["data"]["cache_entries_pruned"] == 4
        assert all(
            "DEPRECATED" in response["meta"]["warnings"][0]
            for response in [deprecated_search, deprecated_read, deprecated_task, deprecated_page, deprecated_append]
        )
        assert json.loads(settings_json) == {"env": "test"}

    def test_server_main_runs_built_server(self, monkeypatch):
        import antigravity_mcp.server as server_module

        fake_server = FakeFastMCP("test")
        monkeypatch.setattr(server_module, "build_server", lambda: fake_server)

        server_module.main()

        assert fake_server.ran is True
