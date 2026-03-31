from __future__ import annotations

import argparse
import asyncio
from datetime import date
from typing import Any

import httpx
from credibility import CredibilityScorer
from deduplicator import NewsDeduplicator
from news_bot import _is_relevant_to_category
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
from settings import (
    NEWS_SOURCES_FILE,
    NOTION_API_KEY,
    NOTION_API_VERSION,
    NOTION_REPORTS_DATABASE_ID,
    PIPELINE_HTTP_TIMEOUT_SEC,
)

# Pipeline quality gates
_DEDUPLICATOR = NewsDeduplicator(threshold=0.85)
_CREDIBILITY_SCORER = CredibilityScorer()
_MIN_CREDIBILITY_SCORE = 4.0  # Filter clickbait / low-trust sources


def _load_all_feeds() -> dict[str, list[dict[str, str]]]:
    """Load feeds from news_sources.json (single source of truth)."""
    import json

    with NEWS_SOURCES_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


async def get_existing_urls(database_id: str, api_key: str, logger) -> set[str]:
    existing_urls: set[str] = set()
    has_more = True
    next_cursor: str | None = None
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": NOTION_API_VERSION,
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
    if not NOTION_REPORTS_DATABASE_ID:
        logger.error("bootstrap", "failed", "NOTION_REPORTS_DATABASE_ID missing")
        state.record_job_finish(run_id, status="failed", error_text="NOTION_REPORTS_DATABASE_ID missing")
        return 1

    summary = {"saved": 0, "skipped": 0, "sources_failed": 0, "credibility_filtered": 0, "dedup_removed": 0}
    notion = AsyncClient(auth=NOTION_API_KEY)

    try:
        with JobLock("collect_news", run_id):
            existing_urls = await get_existing_urls(NOTION_REPORTS_DATABASE_ID, NOTION_API_KEY, logger)
            today_str = date.today().isoformat()
            all_sources = _load_all_feeds()

            for category, sources in all_sources.items():
                # Collect all raw entries for this category first
                category_entries: list[dict] = []

                for source in sources:
                    source_name = source["name"]
                    feed_url = source["url"]
                    logger.info("fetch", "start", "fetching feed", category=category, source=source_name, url=feed_url)
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
                            continue
                        if link in existing_urls or state.has_article(link):
                            summary["skipped"] += 1
                            continue

                        description = _entry_description(entry)
                        if not _is_relevant_to_category(title, description, category):
                            summary["skipped"] += 1
                            continue

                        category_entries.append(
                            {
                                "title": title,
                                "link": link,
                                "source": source_name,
                                "description": description,
                                "category": category,
                            }
                        )

                if not category_entries:
                    continue

                # [GATE 1] Credibility filter — remove clickbait and low-trust sources
                credible_entries = _CREDIBILITY_SCORER.filter_articles(
                    category_entries, min_score=_MIN_CREDIBILITY_SCORE
                )
                filtered_count = len(category_entries) - len(credible_entries)
                if filtered_count:
                    summary["credibility_filtered"] += filtered_count
                    logger.info(
                        "credibility",
                        "filtered",
                        f"{filtered_count} low-trust articles removed",
                        category=category,
                    )

                # [GATE 2] Title-similarity dedup — merge near-duplicate headlines
                deduped_entries = _DEDUPLICATOR.deduplicate(credible_entries)
                dedup_removed = len(credible_entries) - len(deduped_entries)
                if dedup_removed:
                    summary["dedup_removed"] += dedup_removed
                    logger.info(
                        "dedup",
                        "removed",
                        f"{dedup_removed} near-duplicate articles merged",
                        category=category,
                    )

                # Upload deduplicated, credible articles to Notion
                for article in deduped_entries:
                    title = article["title"]
                    link = article["link"]
                    source_name = article["source"]
                    description = article["description"]

                    # Build Notion properties with optional quality metadata
                    properties: dict = {
                        "Name": {"title": [{"text": {"content": title}}]},
                        "Date": {"date": {"start": today_str}},
                        "Source": {"select": {"name": category}},
                        "Link": {"url": link},
                        "Description": {"rich_text": [{"text": {"content": description}}]},
                    }

                    page = await create_notion_page_with_retry(
                        notion_client=notion,
                        parent={"database_id": NOTION_REPORTS_DATABASE_ID},
                        properties=properties,
                        children=[],
                        logger=logger,
                        step="upload",
                    )

                    page_id = page.get("id")
                    state.record_article(link=link, source=source_name, notion_page_id=page_id, run_id=run_id)
                    existing_urls.add(link)
                    summary["saved"] += 1
                    logger.info(
                        "upload",
                        "success",
                        "article saved",
                        category=category,
                        source=source_name,
                        link=link,
                        page_id=page_id,
                    )

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
