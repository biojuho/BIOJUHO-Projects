from __future__ import annotations

from antigravity_mcp.pipelines.dashboard import refresh_dashboard
from antigravity_mcp.state.events import error_response, ok, partial
from antigravity_mcp.state.store import PipelineStateStore


async def ops_get_run_status_tool(run_id: str) -> dict:
    store = PipelineStateStore()
    run = store.get_run(run_id)
    if run is None:
        return error_response("run_not_found", f"Unknown run_id: {run_id}")
    return ok({"run": run.to_dict()})


async def ops_list_runs_tool(job_name: str = "", status: str = "", limit: int = 20) -> dict:
    store = PipelineStateStore()
    runs = store.list_runs(job_name=job_name or None, status=status or None, limit=limit)
    return ok({"runs": [run.to_dict() for run in runs]})


async def ops_refresh_dashboard_tool() -> dict:
    store = PipelineStateStore()
    run_id, payload, warnings, status = await refresh_dashboard(state_store=store)
    if status == "partial":
        return partial(payload, warnings=warnings, meta={"run_id": run_id})
    return ok(payload, meta={"run_id": run_id})
