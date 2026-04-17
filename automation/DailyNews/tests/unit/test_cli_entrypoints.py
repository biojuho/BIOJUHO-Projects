from __future__ import annotations

import argparse
import builtins
import importlib
import io
import runpy
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class _StdoutBuffer:
    def __init__(self) -> None:
        self.buffer = io.BytesIO()


class TestCliModule:
    def test_import_defers_ops_dependencies(self, monkeypatch):
        sys.modules.pop("antigravity_mcp.cli", None)
        sys.modules.pop("antigravity_mcp.cli_ops", None)
        sys.modules.pop("antigravity_mcp.tooling.content_tools", None)
        original_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"antigravity_mcp.cli_ops", "antigravity_mcp.tooling.content_tools"}:
                raise AssertionError(f"{name} imported eagerly")
            return original_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", guarded_import)

        module = importlib.import_module("antigravity_mcp.cli")

        assert module.__name__ == "antigravity_mcp.cli"

    @pytest.mark.asyncio
    async def test_run_jobs_helpers_return_expected_exit_codes(self, monkeypatch):
        import antigravity_mcp.cli as cli

        stdout = _StdoutBuffer()
        monkeypatch.setattr(cli.sys, "stdout", stdout)
        monkeypatch.setattr(cli, "content_generate_brief_tool", AsyncMock(return_value={"status": "ok", "data": {}}))

        exit_code = await cli._run_jobs_generate_brief(
            argparse.Namespace(categories=["Tech"], window="manual", max_items=3)
        )

        assert exit_code == 0
        assert b'"status": "ok"' in stdout.buffer.getvalue()

        printed: list[str] = []
        monkeypatch.setattr(cli, "content_publish_report_tool", AsyncMock(return_value={"status": "error"}))
        monkeypatch.setattr(builtins, "print", lambda payload: printed.append(payload))

        exit_code = await cli._run_jobs_publish_report(
            argparse.Namespace(report_id="report-1", channels=["x"], approval_mode="manual")
        )

        assert exit_code == 1
        assert printed

    def test_build_parser_and_main_dispatch(self, monkeypatch):
        import antigravity_mcp.cli as cli

        parser = cli.build_parser()
        parsed = parser.parse_args(
            ["jobs", "generate-brief", "--categories", "Tech", "Economy_KR", "--window", "manual", "--max-items", "7"]
        )

        assert parsed.command == "jobs"
        assert parsed.jobs_command == "generate-brief"
        assert parsed.categories == ["Tech", "Economy_KR"]
        assert parsed.max_items == 7

        parsed_resync = parser.parse_args(["ops", "resync-report", "--report-id", "report-1"])
        assert parsed_resync.command == "ops"
        assert parsed_resync.ops_command == "resync-report"
        assert parsed_resync.report_id == "report-1"

        fake_server = ModuleType("antigravity_mcp.server")
        called = {"serve": 0, "generate": 0, "publish": 0, "ops": 0}

        def fake_server_main():
            called["serve"] += 1

        async def fake_generate(args):
            called["generate"] += 1
            return 11

        async def fake_publish(args):
            called["publish"] += 1
            return 12

        fake_server.main = fake_server_main
        monkeypatch.setitem(sys.modules, "antigravity_mcp.server", fake_server)
        monkeypatch.setattr(cli, "_run_jobs_generate_brief", fake_generate)
        monkeypatch.setattr(cli, "_run_jobs_publish_report", fake_publish)
        monkeypatch.setattr(cli, "dispatch_ops_command", lambda args: called.__setitem__("ops", called["ops"] + 1) or 13)

        assert cli.main(["serve"]) == 0
        assert cli.main(["jobs", "generate-brief"]) == 11
        assert cli.main(["jobs", "publish-report", "--report-id", "report-1"]) == 12
        assert cli.main(["ops", "refresh-dashboard"]) == 13
        assert called == {"serve": 1, "generate": 1, "publish": 1, "ops": 1}


class TestCliOpsModule:
    def test_import_defers_dashboard_dependencies(self, monkeypatch):
        sys.modules.pop("antigravity_mcp.cli_ops", None)
        sys.modules.pop("antigravity_mcp.tooling.ops_tools", None)
        original_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"antigravity_mcp.pipelines.dashboard", "antigravity_mcp.tooling.ops_tools"}:
                raise AssertionError(f"{name} imported eagerly")
            return original_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", guarded_import)

        module = importlib.import_module("antigravity_mcp.cli_ops")

        assert module.__name__ == "antigravity_mcp.cli_ops"

    @pytest.mark.asyncio
    async def test_run_ops_refresh_dashboard_and_frozen_eval(self, monkeypatch):
        import antigravity_mcp.cli_ops as cli_ops

        printed: list[str] = []
        monkeypatch.setattr(builtins, "print", lambda payload: printed.append(payload))
        monkeypatch.setattr(
            cli_ops,
            "refresh_dashboard",
            AsyncMock(return_value=("run-1", {"reports": []}, ["warn"], "partial")),
        )

        refresh_exit = await cli_ops.run_ops_refresh_dashboard()

        stdout = _StdoutBuffer()
        monkeypatch.setattr(cli_ops.sys, "stdout", stdout)
        monkeypatch.setattr(
            cli_ops,
            "ops_run_frozen_eval_tool",
            AsyncMock(return_value={"status": "ok", "data": {"cases": 1}}),
        )
        frozen_exit = await cli_ops.run_ops_frozen_eval(
            argparse.Namespace(dataset="dataset.json", output="out.json", state_db="state.db")
        )

        assert refresh_exit == 0
        assert printed
        assert frozen_exit == 0
        assert b'"status": "ok"' in stdout.buffer.getvalue()

    @pytest.mark.asyncio
    async def test_run_ops_replay_handles_missing_generate_publish_and_unknown_runs(self, monkeypatch):
        import antigravity_mcp.cli as cli
        import antigravity_mcp.cli_ops as cli_ops

        printed: list[str] = []
        monkeypatch.setattr(builtins, "print", lambda payload: printed.append(payload))
        monkeypatch.setattr(cli_ops, "ops_get_run_status_tool", AsyncMock(return_value={"status": "error"}))

        store = SimpleNamespace(get_run=lambda run_id: None)
        monkeypatch.setattr(cli_ops, "PipelineStateStore", lambda: store)
        assert await cli_ops.run_ops_replay(argparse.Namespace(run_id="missing")) == 1

        generate_store = SimpleNamespace(
            get_run=lambda run_id: SimpleNamespace(
                job_name="generate_brief",
                summary={"categories": ["Tech"], "window_name": "manual", "max_items": 3},
            )
        )
        monkeypatch.setattr(cli_ops, "PipelineStateStore", lambda: generate_store)
        monkeypatch.setattr(cli, "_run_jobs_generate_brief", AsyncMock(return_value=21))
        assert await cli_ops.run_ops_replay(argparse.Namespace(run_id="gen-1")) == 21

        publish_store = SimpleNamespace(
            get_run=lambda run_id: SimpleNamespace(job_name="publish_report", summary={"channels": ["x"]})
        )
        monkeypatch.setattr(cli_ops, "PipelineStateStore", lambda: publish_store)
        assert await cli_ops.run_ops_replay(argparse.Namespace(run_id="pub-1")) == 1

        ready_publish_store = SimpleNamespace(
            get_run=lambda run_id: SimpleNamespace(
                job_name="publish_report",
                summary={"report_id": "report-1", "channels": ["x"], "approval_mode": "auto"},
            )
        )
        monkeypatch.setattr(cli_ops, "PipelineStateStore", lambda: ready_publish_store)
        monkeypatch.setattr(cli, "_run_jobs_publish_report", AsyncMock(return_value=22))
        assert await cli_ops.run_ops_replay(argparse.Namespace(run_id="pub-2")) == 22

        unknown_store = SimpleNamespace(get_run=lambda run_id: SimpleNamespace(job_name="other", summary={}))
        monkeypatch.setattr(cli_ops, "PipelineStateStore", lambda: unknown_store)
        assert await cli_ops.run_ops_replay(argparse.Namespace(run_id="other-1")) == 1
        assert printed

    def test_dispatch_ops_command_and_main_entrypoint(self, monkeypatch):
        import antigravity_mcp.cli_ops as cli_ops

        async def fake_refresh():
            return 31

        async def fake_resync(args):
            return 34

        async def fake_replay(args):
            return 32

        async def fake_frozen(args):
            return 33

        monkeypatch.setattr(cli_ops, "run_ops_refresh_dashboard", fake_refresh)
        monkeypatch.setattr(cli_ops, "run_ops_resync_report", fake_resync)
        monkeypatch.setattr(cli_ops, "run_ops_replay", fake_replay)
        monkeypatch.setattr(cli_ops, "run_ops_frozen_eval", fake_frozen)

        assert cli_ops.dispatch_ops_command(argparse.Namespace(ops_command="refresh-dashboard")) == 31
        assert cli_ops.dispatch_ops_command(argparse.Namespace(ops_command="resync-report")) == 34
        assert cli_ops.dispatch_ops_command(argparse.Namespace(ops_command="replay-run")) == 32
        assert cli_ops.dispatch_ops_command(argparse.Namespace(ops_command="run-frozen-eval")) == 33
        assert cli_ops.dispatch_ops_command(argparse.Namespace(ops_command="unknown")) == 1

        import antigravity_mcp.cli as cli

        monkeypatch.setattr(cli, "main", lambda: 0)
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_module("antigravity_mcp.__main__", run_name="__main__")

        assert exc_info.value.code == 0
