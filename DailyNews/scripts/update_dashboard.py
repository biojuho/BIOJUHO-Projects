from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import date
from typing import Any

import httpx
from notion_client import AsyncClient

from runtime import (
    AlreadyRunningError,
    JobLock,
    PipelineStateStore,
    async_retry,
    configure_stdout_utf8,
    generate_run_id,
    get_logger,
)
from settings import (
    ANTIGRAVITY_TASKS_DB_ID,
    DASHBOARD_CONFIG_FILE,
    DASHBOARD_PAGE_ID,
    NOTION_API_KEY,
    NOTION_API_VERSION,
    NOTION_TASKS_DATA_SOURCE_ID,
    PIPELINE_HTTP_TIMEOUT_SEC,
)


def save_config(page_id: str) -> None:
    DASHBOARD_CONFIG_FILE.write_text(json.dumps({"dashboard_page_id": page_id}, indent=2), encoding="utf-8")


async def get_or_create_dashboard(notion: AsyncClient, logger) -> str:
    if DASHBOARD_PAGE_ID:
        logger.info("dashboard", "success", "using dashboard page from env", page_id=DASHBOARD_PAGE_ID)
        return DASHBOARD_PAGE_ID

    if DASHBOARD_CONFIG_FILE.exists():
        try:
            config = json.loads(DASHBOARD_CONFIG_FILE.read_text(encoding="utf-8"))
            page_id = config.get("dashboard_page_id")
            if page_id:
                await notion.pages.retrieve(page_id=page_id)
                logger.info("dashboard", "success", "using dashboard page from config", page_id=page_id)
                return page_id
        except Exception as exc:
            logger.warning("dashboard", "degraded", "dashboard config invalid", error=str(exc))

    response = await notion.search(query="Antigravity Newsroom", filter={"property": "object", "value": "page"})
    if response.get("results"):
        page_id = response["results"][0]["id"]
        save_config(page_id)
        logger.info("dashboard", "success", "using dashboard page from notion search", page_id=page_id)
        return page_id

    new_page = await notion.pages.create(
        parent={"database_id": ANTIGRAVITY_TASKS_DB_ID},
        properties={
            "Name": {"title": [{"text": {"content": "Antigravity Newsroom"}}]},
            "Type": {"select": {"name": "Dashboard"}},
            "Date": {"date": {"start": date.today().isoformat()}},
        },
        icon={"emoji": "🛰"},
    )
    page_id = new_page["id"]
    save_config(page_id)
    logger.info("dashboard", "success", "created dashboard page", page_id=page_id)
    return page_id


async def query_todays_articles(logger) -> list[dict[str, Any]]:
    today_str = date.today().isoformat()
    query_id = NOTION_TASKS_DATA_SOURCE_ID or ANTIGRAVITY_TASKS_DB_ID
    query_kind = "data_sources" if NOTION_TASKS_DATA_SOURCE_ID else "databases"
    url = f"https://api.notion.com/v1/{query_kind}/{query_id}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }
    payload = {
        "filter": {
            "and": [
                {"property": "Date", "date": {"equals": today_str}},
                {"property": "Type", "select": {"does_not_equal": "Dashboard"}},
            ]
        }
    }

    async def _fetch() -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=PIPELINE_HTTP_TIMEOUT_SEC) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json().get("results", [])

    return await async_retry(_fetch, attempts=3, base_delay=1.5)


def summarize_categories(articles: list[dict[str, Any]]) -> tuple[int, str]:
    categories: dict[str, int] = {}
    for page in articles:
        title_items = page.get("properties", {}).get("Name", {}).get("title", [])
        title = title_items[0].get("plain_text", "") if title_items else ""
        match = re.search(r"\[(.*?)\]", title)
        category = match.group(1) if match else "Uncategorized"
        categories[category] = categories.get(category, 0) + 1
    summary = " | ".join(f"{name}: {count}" for name, count in sorted(categories.items()))
    return len(articles), summary or "No category data"


async def list_child_blocks(notion: AsyncClient, block_id: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        response = await notion.blocks.children.list(block_id=block_id, start_cursor=cursor)
        blocks.extend(response.get("results", []))
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
    return blocks


def heading_text(block: dict[str, Any]) -> str:
    block_type = block.get("type")
    if block_type not in {"heading_1", "heading_2", "heading_3"}:
        return ""
    rich_text = block.get(block_type, {}).get("rich_text", [])
    return "".join(item.get("plain_text", "") for item in rich_text)


async def clear_auto_dashboard_sections(notion: AsyncClient, page_id: str, logger) -> None:
    blocks = await list_child_blocks(notion, page_id)
    to_delete: list[str] = []
    deleting = False

    for block in blocks:
        text = heading_text(block)
        if text.startswith("[AUTO_DASHBOARD]"):
            deleting = True
            to_delete.append(block["id"])
            continue
        if deleting:
            to_delete.append(block["id"])
            if block.get("type") == "divider":
                deleting = False

    for block_id in to_delete:
        await notion.blocks.delete(block_id=block_id)

    logger.info("dashboard", "success", "cleared previous auto dashboard sections", deleted=len(to_delete))


async def update_dashboard(page_id: str, notion: AsyncClient, logger) -> None:
    articles = await query_todays_articles(logger)
    article_count, category_summary = summarize_categories(articles)
    await clear_auto_dashboard_sections(notion, page_id, logger)

    today_str = date.today().isoformat()
    children = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": f"[AUTO_DASHBOARD] {today_str}"}}]},
        },
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"emoji": "📊"},
                "color": "blue_background",
                "rich_text": [
                    {"text": {"content": f"Total Articles: {article_count}\n"}},
                    {"text": {"content": f"Breakdown: {category_summary}"}},
                ],
            },
        },
        {"object": "block", "type": "divider", "divider": {}},
    ]

    await notion.blocks.children.append(block_id=page_id, children=children)
    logger.info("dashboard", "success", "dashboard updated", page_id=page_id, articles=article_count)


async def run_update_dashboard(*, run_id: str | None = None) -> int:
    configure_stdout_utf8()
    run_id = run_id or generate_run_id("update_dashboard")
    logger = get_logger("update_dashboard", run_id)
    state = PipelineStateStore()
    state.record_job_start(run_id, "update_dashboard")

    if not NOTION_API_KEY:
        logger.error("bootstrap", "failed", "NOTION_API_KEY missing")
        state.record_job_finish(run_id, status="failed", error_text="NOTION_API_KEY missing")
        return 1
    if not ANTIGRAVITY_TASKS_DB_ID:
        logger.error("bootstrap", "failed", "ANTIGRAVITY_TASKS_DB_ID missing")
        state.record_job_finish(run_id, status="failed", error_text="ANTIGRAVITY_TASKS_DB_ID missing")
        return 1

    notion = AsyncClient(auth=NOTION_API_KEY)
    try:
        with JobLock("update_dashboard", run_id):
            page_id = await get_or_create_dashboard(notion, logger)
            await update_dashboard(page_id, notion, logger)
            state.record_job_finish(run_id, status="success", summary={"page_id": page_id})
            return 0
    except AlreadyRunningError:
        logger.warning("lock", "skipped", "job already running")
        state.record_job_finish(run_id, status="skipped", error_text="already running")
        return 2
    except Exception as exc:
        logger.error("complete", "failed", "dashboard update failed", error=str(exc))
        state.record_job_finish(run_id, status="failed", error_text=str(exc))
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update the Antigravity dashboard page in Notion.")
    parser.add_argument("--run-id", help="Optional run identifier for logs and state tracking")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(run_update_dashboard(run_id=args.run_id))


if __name__ == "__main__":
    raise SystemExit(main())
