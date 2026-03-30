from __future__ import annotations

from antigravity_mcp.config import get_settings
from antigravity_mcp.integrations.notion_adapter import NotionAdapter, NotionAdapterError
from antigravity_mcp.state.events import error_response, ok, partial


async def notion_search_tool(query: str, object_type: str = "page", limit: int = 10, cursor: str = "") -> dict:
    settings = get_settings()
    adapter = NotionAdapter(settings=settings)
    if not adapter.is_configured():
        return error_response("notion_not_configured", "NOTION_API_KEY is missing.")
    try:
        results, next_cursor = await adapter.search(
            query=query,
            object_type=object_type,
            limit=limit,
            cursor=cursor,
        )
        meta = {"cursor": next_cursor}
        if settings.settings_warnings:
            meta["warnings"] = list(settings.settings_warnings)
        return ok({"results": [result.to_dict() for result in results]}, meta=meta)
    except NotionAdapterError as exc:
        return error_response(exc.code, str(exc), retryable=exc.retryable)


async def notion_get_page_tool(page_id: str, include_blocks: bool = True, max_depth: int = 1) -> dict:
    adapter = NotionAdapter()
    if not adapter.is_configured():
        return error_response("notion_not_configured", "NOTION_API_KEY is missing.")
    try:
        return ok(await adapter.get_page(page_id=page_id, include_blocks=include_blocks, max_depth=max_depth))
    except NotionAdapterError as exc:
        return error_response(exc.code, str(exc), retryable=exc.retryable)


async def notion_create_page_tool(
    parent_page_id: str,
    title: str,
    markdown: str = "",
    properties: dict | None = None,
) -> dict:
    adapter = NotionAdapter()
    if not adapter.is_configured():
        return error_response("notion_not_configured", "NOTION_API_KEY is missing.")
    try:
        return ok(
            await adapter.create_page(
                parent_page_id=parent_page_id, title=title, markdown=markdown, properties=properties
            )
        )
    except NotionAdapterError as exc:
        return error_response(exc.code, str(exc), retryable=exc.retryable)


async def notion_append_blocks_tool(page_id: str, markdown: str) -> dict:
    adapter = NotionAdapter()
    if not adapter.is_configured():
        return error_response("notion_not_configured", "NOTION_API_KEY is missing.")
    try:
        return ok(await adapter.append_markdown(page_id=page_id, markdown=markdown))
    except NotionAdapterError as exc:
        return error_response(exc.code, str(exc), retryable=exc.retryable)


async def notion_create_record_tool(database_kind: str, properties: dict, markdown: str = "") -> dict:
    settings = get_settings()
    adapter = NotionAdapter(settings=settings)
    if not adapter.is_configured():
        return error_response("notion_not_configured", "NOTION_API_KEY is missing.")
    database_map = {
        "tasks": settings.notion_tasks_database_id,
        "reports": settings.notion_reports_database_id,
    }
    database_id = database_map.get(database_kind.lower(), "")
    if not database_id:
        return error_response("database_not_configured", f"Unknown or unconfigured database_kind: {database_kind}")
    try:
        result = await adapter.create_record(database_id=database_id, properties=properties, markdown=markdown)
        if settings.settings_warnings:
            return partial(result, warnings=list(settings.settings_warnings))
        return ok(result)
    except NotionAdapterError as exc:
        return error_response(exc.code, str(exc), retryable=exc.retryable)
