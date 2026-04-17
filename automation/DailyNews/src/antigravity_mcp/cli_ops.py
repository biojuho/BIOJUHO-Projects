from __future__ import annotations

import argparse
import asyncio
import json
import sys

from antigravity_mcp.state.events import json_dumps
from antigravity_mcp.state.store import PipelineStateStore


async def refresh_dashboard(*args, **kwargs):
    from antigravity_mcp.pipelines.dashboard import refresh_dashboard as _refresh_dashboard

    return await _refresh_dashboard(*args, **kwargs)


async def ops_get_run_status_tool(*args, **kwargs):
    from antigravity_mcp.tooling.ops_tools import ops_get_run_status_tool as _ops_get_run_status_tool

    return await _ops_get_run_status_tool(*args, **kwargs)


async def ops_run_frozen_eval_tool(*args, **kwargs):
    from antigravity_mcp.tooling.ops_tools import ops_run_frozen_eval_tool as _ops_run_frozen_eval_tool

    return await _ops_run_frozen_eval_tool(*args, **kwargs)


async def ops_resync_report_tool(*args, **kwargs):
    from antigravity_mcp.tooling.ops_tools import ops_resync_report_tool as _ops_resync_report_tool

    return await _ops_resync_report_tool(*args, **kwargs)


async def run_ops_refresh_dashboard() -> int:
    store = PipelineStateStore()
    try:
        run_id, payload, warnings, status = await refresh_dashboard(state_store=store)
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()
    result = {
        "status": status,
        "run_id": run_id,
        "data": payload,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status != "error" else 1


async def run_ops_replay(args: argparse.Namespace) -> int:
    from antigravity_mcp.cli import _run_jobs_generate_brief, _run_jobs_publish_report

    store = PipelineStateStore()
    try:
        run = store.get_run(args.run_id)
        if run is None:
            print(
                json_dumps(
                    {
                        "status": "error",
                        "data": {},
                        "meta": {"warnings": []},
                        "error": {
                            "code": "run_not_found",
                            "message": f"Unknown run_id: {args.run_id}",
                            "retryable": False,
                        },
                    }
                )
            )
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
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


async def run_ops_frozen_eval(args: argparse.Namespace) -> int:
    result = await ops_run_frozen_eval_tool(
        dataset_path=args.dataset,
        output_path=args.output,
        state_db_path=args.state_db,
    )
    sys.stdout.buffer.write((json_dumps(result) + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()
    return 0 if result["status"] != "error" else 1


async def run_ops_resync_report(args: argparse.Namespace) -> int:
    result = await ops_resync_report_tool(report_id=args.report_id)
    sys.stdout.buffer.write((json_dumps(result) + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()
    return 0 if result["status"] != "error" else 1


def dispatch_ops_command(args: argparse.Namespace) -> int:
    if args.ops_command == "refresh-dashboard":
        return asyncio.run(run_ops_refresh_dashboard())
    if args.ops_command == "resync-report":
        return asyncio.run(run_ops_resync_report(args))
    if args.ops_command == "replay-run":
        return asyncio.run(run_ops_replay(args))
    if args.ops_command == "run-frozen-eval":
        return asyncio.run(run_ops_frozen_eval(args))
    return 1
