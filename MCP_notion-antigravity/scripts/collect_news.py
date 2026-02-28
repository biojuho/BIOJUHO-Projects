from __future__ import annotations

import argparse
import asyncio
from datetime import date
from typing import Any

import httpx
from notion_client import AsyncClient

from runtime import (
    AlreadyRunningError,
    JobLock,
    PipelineStateStore,
    configure_stdout_utf8,
    create_notion_page_with_retry,
    fetch_feed_entries,
    generate_run_id,
    get_logger,
)
from settings import ANTIGRAVITY_NEWS_DB_ID, NOTION_API_KEY, PIPELINE_HTTP_TIMEOUT_SEC


RSS_FEEDS = {
    "GeekNews": "https://feeds.feedburner.com/geeknews-feed",
    "Hacker News (Top)": "https://news.ycombinator.com/rss",
    "IT World Korea": "https://www.itworld.co.kr/rss/feed/index.php",
}


async def get_existing_urls(database_id: str, api_key: str, logger) -> set[str]:
    existing_urls: set[str] = set()
    has_more = True
    next_cursor: str | None = None
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    logger.info("dedupe", "start", "loading existing notion links")

    async with httpx.AsyncClient(timeout=PIPELINE_HTTP_TIMEOUT_SEC) as client:
        while has_more:
            payload: dict[str, Any] = {
                "page_size": 100,
                "sorts": [{"property": "Date", "direction": "descending"}],
            }
            if next_cursor:
                payload["start_cursor"] = next_cursor

            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            for page in data.get("results", []):
                link_value = page.get("properties", {}).get("Link", {}).get("url")
                if link_value:
                    existing_urls.add(link_value)

            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor")

    logger.info("dedupe", "success", "loaded notion links", count=len(existing_urls))
    return existing_urls


def _entry_description(entry: Any) -> str:
    if hasattr(entry, "description") and entry.description:
        return str(entry.description)[:200]
    if hasattr(entry, "summary") and entry.summary:
        return str(entry.summary)[:200]
    return ""


async def collect_and_upload_news(*, max_items: int, run_id: str | None = None) -> int:
    configure_stdout_utf8()
    run_id = run_id or generate_run_id("collect_news")
    logger = get_logger("collect_news", run_id)
    state = PipelineStateStore()
    state.record_job_start(run_id, "collect_news")

    if not NOTION_API_KEY:
        logger.error("bootstrap", "failed", "NOTION_API_KEY missing")
        state.record_job_finish(run_id, status="failed", error_text="NOTION_API_KEY missing")
        return 1
    if not ANTIGRAVITY_NEWS_DB_ID:
        logger.error("bootstrap", "failed", "ANTIGRAVITY_NEWS_DB_ID missing")
        state.record_job_finish(run_id, status="failed", error_text="ANTIGRAVITY_NEWS_DB_ID missing")
        return 1

    summary = {"saved": 0, "skipped": 0, "sources_failed": 0}
    notion = AsyncClient(auth=NOTION_API_KEY)

    try:
        with JobLock("collect_news", run_id):
            existing_urls = await get_existing_urls(ANTIGRAVITY_NEWS_DB_ID, NOTION_API_KEY, logger)
            today_str = date.today().isoformat()

            for source_name, feed_url in RSS_FEEDS.items():
                logger.info("fetch", "start", "fetching feed", source=source_name, url=feed_url)
                try:
                    entries = await fetch_feed_entries(feed_url)
                except Exception as exc:
                    summary["sources_failed"] += 1
                    logger.error("fetch", "failed", "feed fetch failed", source=source_name, error=str(exc))
                    continue

                for entry in entries[:max_items]:
                    title = getattr(entry, "title", "Untitled")
                    link = getattr(entry, "link", "")
                    if not link:
                        summary["skipped"] += 1
                        logger.warning("dedupe", "skipped", "entry missing link", source=source_name, title=title[:80])
                        continue
                    if link in existing_urls or state.has_article(link):
                        summary["skipped"] += 1
                        logger.info("dedupe", "skipped", "duplicate article", source=source_name, link=link)
                        continue

                    description = _entry_description(entry)
                    page = await create_notion_page_with_retry(
                        notion_client=notion,
                        parent={"database_id": ANTIGRAVITY_NEWS_DB_ID},
                        properties={
                            "Name": {"title": [{"text": {"content": title}}]},
                            "Date": {"date": {"start": today_str}},
                            "Source": {"select": {"name": source_name}},
                            "Link": {"url": link},
                            "Description": {"rich_text": [{"text": {"content": description}}]},
                        },
                        children=[],
                        logger=logger,
                        step="upload",
                    )

                    page_id = page.get("id")
                    state.record_article(link=link, source=source_name, notion_page_id=page_id, run_id=run_id)
                    existing_urls.add(link)
                    summary["saved"] += 1
                    logger.info("upload", "success", "article saved", source=source_name, link=link, page_id=page_id)

            state.record_job_finish(run_id, status="success", summary=summary)
            logger.info("complete", "success", "collect_news finished", **summary)
            return 0
    except AlreadyRunningError:
        logger.warning("lock", "skipped", "job already running")
        state.record_job_finish(run_id, status="skipped", error_text="already running")
        return 2
    except Exception as exc:
        logger.error("complete", "failed", "collect_news failed", error=str(exc))
        state.record_job_finish(run_id, status="failed", summary=summary, error_text=str(exc))
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect RSS news and upload non-duplicates to Notion.")
    parser.add_argument("--max-items", type=int, default=10, help="Maximum items to upload per feed")
    parser.add_argument("--run-id", help="Optional run identifier for logs and state tracking")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(collect_and_upload_news(max_items=args.max_items, run_id=args.run_id))


if __name__ == "__main__":
    raise SystemExit(main())
