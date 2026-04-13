from __future__ import annotations

import argparse
import asyncio
import sys

from antigravity_mcp.state.events import json_dumps


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

    frozen_eval = ops_subparsers.add_parser("run-frozen-eval", help="Run the frozen evaluation dataset")
    frozen_eval.add_argument("--dataset", default="")
    frozen_eval.add_argument("--output", default="")
    frozen_eval.add_argument("--state-db", default="")

    # Newsletter management (v2.0)
    from antigravity_mcp.cli_newsletter import register_newsletter_parser
    register_newsletter_parser(subparsers)

    # Signal Arbitrage (v2.1)
    from antigravity_mcp.cli_signal import register_signal_parser
    register_signal_parser(subparsers)

    return parser


async def _run_jobs_generate_brief(args: argparse.Namespace) -> int:
    result = await content_generate_brief_tool(
        categories=args.categories,
        window=args.window,
        max_items=args.max_items,
    )
    sys.stdout.buffer.write((json_dumps(result) + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()
    return 0 if result["status"] != "error" else 1


async def _run_jobs_publish_report(args: argparse.Namespace) -> int:
    result = await content_publish_report_tool(
        report_id=args.report_id,
        channels=args.channels,
        approval_mode=args.approval_mode,
    )
    print(json_dumps(result))
    return 0 if result["status"] != "error" else 1


async def content_generate_brief_tool(*args, **kwargs):
    from antigravity_mcp.tooling.content_tools import (
        content_generate_brief_tool as _content_generate_brief_tool,
    )

    return await _content_generate_brief_tool(*args, **kwargs)


async def content_publish_report_tool(*args, **kwargs):
    from antigravity_mcp.tooling.content_tools import (
        content_publish_report_tool as _content_publish_report_tool,
    )

    return await _content_publish_report_tool(*args, **kwargs)


def dispatch_ops_command(args: argparse.Namespace) -> int:
    from antigravity_mcp.cli_ops import dispatch_ops_command as _dispatch_ops_command

    return _dispatch_ops_command(args)


def main(argv: list[str] | None = None) -> int:
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

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
    if args.command == "ops":
        return dispatch_ops_command(args)
    if args.command == "newsletter":
        from antigravity_mcp.cli_newsletter import dispatch_newsletter_command
        return dispatch_newsletter_command(args)
    if args.command == "signal":
        from antigravity_mcp.cli_signal import dispatch_signal_command
        return dispatch_signal_command(args)
    parser.print_help()
    return 1
