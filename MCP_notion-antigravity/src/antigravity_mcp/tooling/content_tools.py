from __future__ import annotations

from antigravity_mcp.pipelines.analyze import generate_briefs
from antigravity_mcp.pipelines.collect import collect_content_items, get_window
from antigravity_mcp.pipelines.publish import publish_report
from antigravity_mcp.state.events import error_response, ok, partial
from antigravity_mcp.state.store import PipelineStateStore


async def content_generate_brief_tool(
    categories: list[str] | None = None,
    window: str = "manual",
    max_items: int = 5,
) -> dict:
    store = PipelineStateStore()
    items, warnings = await collect_content_items(
        categories=categories,
        window_name=window,
        max_items=max_items,
        state_store=store,
    )
    if not items:
        if warnings:
            return partial({"reports": [], "report_ids": []}, warnings=warnings)
        return ok({"reports": [], "report_ids": []})

    window_start, window_end = get_window(window)
    run_id, reports, llm_warnings, status = await generate_briefs(
        items=items,
        window_name=window,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
        state_store=store,
    )
    payload = {
        "run_id": run_id,
        "report_ids": [report.report_id for report in reports],
        "reports": [report.to_dict() for report in reports],
    }
    all_warnings = warnings + llm_warnings
    if status == "partial" or all_warnings:
        return partial(payload, warnings=all_warnings, meta={"run_id": run_id})
    return ok(payload, meta={"run_id": run_id})


async def content_publish_report_tool(
    report_id: str,
    channels: list[str] | None = None,
    approval_mode: str = "manual",
) -> dict:
    store = PipelineStateStore()
    run_id, publication, warnings, status = await publish_report(
        report_id=report_id,
        channels=channels or ["x", "canva"],
        approval_mode=approval_mode,
        state_store=store,
    )
    if status == "error":
        return error_response("publish_failed", warnings[0] if warnings else "Publish failed.", data={"run_id": run_id})
    if warnings:
        return partial(publication, warnings=warnings, meta={"run_id": run_id})
    return ok(publication, meta={"run_id": run_id})
