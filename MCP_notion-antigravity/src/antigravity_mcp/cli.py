from __future__ import annotations

import argparse
import asyncio
import json

from antigravity_mcp.pipelines.dashboard import refresh_dashboard
from antigravity_mcp.state.events import json_dumps
from antigravity_mcp.state.store import PipelineStateStore
from antigravity_mcp.tooling.content_tools import (
    content_generate_brief_tool,
    content_publish_report_tool,
)
from antigravity_mcp.tooling.ops_tools import ops_get_run_status_tool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="antigravity-mcp", description="Antigravity Content Engine CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("serve", help="Run the MCP server")

    jobs = subparsers.add_parser("jobs", help="Run content jobs")
    job_subparsers = jobs.add_subparsers(dest="jobs_command", required=True)

    generate = job_subparsers.add_parser("generate-brief", help="Collect sources and generate draft briefs")
    generate.add_argument("--categories", nargs="*", default=None)
    generate.add_argument("--window", default="manual")
    generate.add_argument("--max-items", type=int, default=5)

    publish = job_subparsers.add_parser("publish-report", help="Publish a stored report draft")
    publish.add_argument("--report-id", required=True)
    publish.add_argument("--channels", nargs="*", default=["x", "canva"])
    publish.add_argument("--approval-mode", default="manual")

    ops = subparsers.add_parser("ops", help="Operational commands")
    ops_subparsers = ops.add_subparsers(dest="ops_command", required=True)

    ops_subparsers.add_parser("refresh-dashboard", help="Refresh the Notion dashboard auto section")

    replay = ops_subparsers.add_parser("replay-run", help="Replay a supported run")
    replay.add_argument("--run-id", required=True)

    return parser


async def _run_jobs_generate_brief(args: argparse.Namespace) -> int:
    result = await content_generate_brief_tool(
        categories=args.categories,
        window=args.window,
        max_items=args.max_items,
    )
    print(json_dumps(result))
    return 0 if result["status"] != "error" else 1


async def _run_jobs_publish_report(args: argparse.Namespace) -> int:
    result = await content_publish_report_tool(
        report_id=args.report_id,
        channels=args.channels,
        approval_mode=args.approval_mode,
    )
    print(json_dumps(result))
    return 0 if result["status"] != "error" else 1


async def _run_ops_refresh_dashboard() -> int:
    run_id, payload, warnings, status = await refresh_dashboard(state_store=PipelineStateStore())
    result = {
        "status": status,
        "run_id": run_id,
        "data": payload,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status != "error" else 1


async def _run_ops_replay(args: argparse.Namespace) -> int:
    store = PipelineStateStore()
    run = store.get_run(args.run_id)
    if run is None:
        print(json_dumps({"status": "error", "data": {}, "meta": {"warnings": []}, "error": {"code": "run_not_found", "message": f"Unknown run_id: {args.run_id}", "retryable": False}}))
        return 1
    if run.job_name == "generate_brief":
        summary = run.summary or {}
        replay_args = argparse.Namespace(
            categories=summary.get("categories"),
            window=summary.get("window_name", "manual"),
            max_items=summary.get("max_items", 5),
        )
        return await _run_jobs_generate_brief(replay_args)
    if run.job_name == "publish_report":
        summary = run.summary or {}
        replay_args = argparse.Namespace(
            report_id=summary.get("report_id", ""),
            channels=summary.get("channels", ["x", "canva"]),
            approval_mode=summary.get("approval_mode", "manual"),
        )
        if not replay_args.report_id:
            print(json_dumps(await ops_get_run_status_tool(args.run_id)))
            return 1
        return await _run_jobs_publish_report(replay_args)
    print(json_dumps(await ops_get_run_status_tool(args.run_id)))
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "serve":
        from antigravity_mcp.server import main as server_main

        server_main()
        return 0
    if args.command == "jobs" and args.jobs_command == "generate-brief":
        return asyncio.run(_run_jobs_generate_brief(args))
    if args.command == "jobs" and args.jobs_command == "publish-report":
        return asyncio.run(_run_jobs_publish_report(args))
    if args.command == "ops" and args.ops_command == "refresh-dashboard":
        return asyncio.run(_run_ops_refresh_dashboard())
    if args.command == "ops" and args.ops_command == "replay-run":
        return asyncio.run(_run_ops_replay(args))
    parser.print_help()
    return 1
