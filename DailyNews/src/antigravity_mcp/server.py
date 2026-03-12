from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from antigravity_mcp.config import get_settings
from antigravity_mcp.state.events import json_dumps, ok
from antigravity_mcp.state.store import PipelineStateStore
from antigravity_mcp.tooling.content_tools import (
    content_generate_brief_tool,
    content_publish_report_tool,
)
from antigravity_mcp.tooling.notion_tools import (
    notion_append_blocks_tool,
    notion_create_page_tool,
    notion_create_record_tool,
    notion_get_page_tool,
    notion_search_tool,
)
from antigravity_mcp.tooling.content_tools import content_invoke_skill_tool
from antigravity_mcp.tooling.ops_tools import (
    ops_check_health_tool,
    ops_cleanup_tool,
    ops_collect_tweet_metrics_tool,
    ops_get_run_status_tool,
    ops_get_tweet_performance_tool,
    ops_list_runs_tool,
    ops_refresh_dashboard_tool,
)

_DEPRECATION_MSG = " This tool will be removed in v0.3.0."


def build_server() -> FastMCP:
    settings = get_settings()
    server = FastMCP("Antigravity Content Engine MCP")

    @server.tool()
    async def notion_search(query: str, object_type: str = "page", limit: int = 10, cursor: str = "") -> dict:
        return await notion_search_tool(query=query, object_type=object_type, limit=limit, cursor=cursor)

    @server.tool()
    async def notion_get_page(page_id: str, include_blocks: bool = True, max_depth: int = 1) -> dict:
        return await notion_get_page_tool(page_id=page_id, include_blocks=include_blocks, max_depth=max_depth)

    @server.tool()
    async def notion_create_page(
        parent_page_id: str,
        title: str,
        markdown: str = "",
        properties: dict | None = None,
    ) -> dict:
        return await notion_create_page_tool(
            parent_page_id=parent_page_id,
            title=title,
            markdown=markdown,
            properties=properties,
        )

    @server.tool()
    async def notion_append_blocks(page_id: str, markdown: str) -> dict:
        return await notion_append_blocks_tool(page_id=page_id, markdown=markdown)

    @server.tool()
    async def notion_create_record(database_kind: str, properties: dict, markdown: str = "") -> dict:
        return await notion_create_record_tool(database_kind=database_kind, properties=properties, markdown=markdown)

    @server.tool()
    async def content_generate_brief(
        categories: list[str] | None = None,
        window: str = "manual",
        max_items: int = 5,
    ) -> dict:
        return await content_generate_brief_tool(categories=categories, window=window, max_items=max_items)

    @server.tool()
    async def content_publish_report(
        report_id: str,
        channels: list[str] | None = None,
        approval_mode: str = "manual",
    ) -> dict:
        return await content_publish_report_tool(
            report_id=report_id,
            channels=channels,
            approval_mode=approval_mode,
        )

    @server.tool()
    async def content_invoke_skill(skill_name: str, params: dict | None = None) -> dict:
        """Invoke a named pipeline skill (summarize_category, market_snapshot, proofread, etc.)."""
        return await content_invoke_skill_tool(skill_name=skill_name, params=params)

    @server.tool()
    async def ops_get_run_status(run_id: str) -> dict:
        return await ops_get_run_status_tool(run_id=run_id)

    @server.tool()
    async def ops_list_runs(job_name: str = "", status: str = "", limit: int = 20) -> dict:
        return await ops_list_runs_tool(job_name=job_name, status=status, limit=limit)

    @server.tool()
    async def ops_refresh_dashboard() -> dict:
        return await ops_refresh_dashboard_tool()

    @server.tool()
    async def ops_cleanup(dry_run: bool = False) -> dict:
        """Prune expired LLM cache entries and article cache rows older than 30 days."""
        return await ops_cleanup_tool(dry_run=dry_run)

    @server.tool()
    async def ops_check_health(
        error_rate_threshold: float = 0.20,
        alert_on_silence_hours: int = 24,
    ) -> dict:
        """Check pipeline health metrics and send Telegram alert if thresholds exceeded."""
        return await ops_check_health_tool(
            error_rate_threshold=error_rate_threshold,
            alert_on_silence_hours=alert_on_silence_hours,
        )

    # ── Phase 5: Tweet metrics & performance ───────────────────────────

    @server.tool()
    async def ops_collect_tweet_metrics(tweet_ids: list[str], report_id: str = "") -> dict:
        """Fetch and store engagement metrics for published tweets from X API v2."""
        return await ops_collect_tweet_metrics_tool(tweet_ids=tweet_ids, report_id=report_id)

    @server.tool()
    async def ops_get_tweet_performance(days: int = 7, limit: int = 10, sort_by: str = "impressions") -> dict:
        """Get top-performing tweets and aggregate engagement summary."""
        return await ops_get_tweet_performance_tool(days=days, limit=limit, sort_by=sort_by)

    # ── Phase 4: Cost monitoring ─────────────────────────────────────────

    @server.tool()
    async def get_token_usage(hours: int = 24) -> dict:
        """Get LLM token usage stats and estimated cost for the last N hours."""
        store = PipelineStateStore()
        stats = store.get_token_usage_stats(hours=hours)
        cache_pruned = store.prune_llm_cache()
        stats["cache_entries_pruned"] = cache_pruned
        return ok(stats)

    @server.tool()
    async def search_notion(query: str) -> dict:
        response = await notion_search_tool(query=query, object_type="page", limit=5, cursor="")
        response.setdefault("meta", {}).setdefault("warnings", []).append(
            "DEPRECATED: use 'notion_search' instead." + _DEPRECATION_MSG
        )
        return response

    @server.tool()
    async def read_page(page_id: str) -> dict:
        response = await notion_get_page_tool(page_id=page_id, include_blocks=True, max_depth=1)
        response.setdefault("meta", {}).setdefault("warnings", []).append(
            "DEPRECATED: use 'notion_get_page' instead." + _DEPRECATION_MSG
        )
        return response

    @server.tool()
    async def add_task(
        title: str,
        content: str = "",
        type: str = "Task",
        priority: str = "medium",
        goal: str = "",
        achievement: str = "",
    ) -> dict:
        response = await notion_create_record_tool(
            database_kind="tasks",
            properties={
                "Name": {"title": [{"type": "text", "text": {"content": title}}]},
                "Type": {"select": {"name": type.title()}},
                "Priority": {"select": {"name": priority.title()}},
                **(
                    {"Goal": {"rich_text": [{"type": "text", "text": {"content": goal}}]}}
                    if goal
                    else {}
                ),
                **(
                    {"Achievement": {"rich_text": [{"type": "text", "text": {"content": achievement}}]}}
                    if achievement
                    else {}
                ),
            },
            markdown=content,
        )
        response.setdefault("meta", {}).setdefault("warnings", []).append(
            "DEPRECATED: use 'notion_create_record' instead." + _DEPRECATION_MSG
        )
        return response

    @server.tool()
    async def create_page(parent_page_id: str, title: str, content: str = "") -> dict:
        response = await notion_create_page_tool(
            parent_page_id=parent_page_id,
            title=title,
            markdown=content,
        )
        response.setdefault("meta", {}).setdefault("warnings", []).append(
            "DEPRECATED: use 'notion_create_page' instead." + _DEPRECATION_MSG
        )
        return response

    @server.tool()
    async def append_block(page_id: str, content: str) -> dict:
        response = await notion_append_blocks_tool(page_id=page_id, markdown=content)
        response.setdefault("meta", {}).setdefault("warnings", []).append(
            "DEPRECATED: use 'notion_append_blocks' instead." + _DEPRECATION_MSG
        )
        return response

    @server.resource("config://settings")
    def settings_resource() -> str:
        return json_dumps(settings.public_summary())

    return server


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
