from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from dateutil import parser as date_parser
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
    run_with_timeout,
)
from settings import ANTIGRAVITY_NEWS_DB_ID, NEWS_SOURCES_FILE, NOTION_API_KEY, OUTPUT_DIR


def get_extraction_window(force: bool) -> tuple[datetime, datetime, str]:
    now = datetime.now()
    hour = now.hour
    if force:
        return now - timedelta(hours=24), now, "test"
    if 6 <= hour < 8:
        start = now.replace(hour=18, minute=0, second=0, microsecond=0) - timedelta(days=1)
        end = now.replace(hour=7, minute=0, second=0, microsecond=0)
        return start, end, "morning"
    if 17 <= hour < 19:
        start = now.replace(hour=7, minute=0, second=0, microsecond=0)
        end = now.replace(hour=18, minute=0, second=0, microsecond=0)
        return start, end, "evening"
    raise RuntimeError("outside extraction window; use --force to override")


def is_within_window(published_time: Any, start: datetime, end: datetime) -> bool:
    if not published_time:
        return True
    try:
        if isinstance(published_time, str):
            published_dt = date_parser.parse(published_time)
        else:
            published_dt = datetime(*published_time[:6])
        if published_dt.tzinfo:
            published_dt = published_dt.replace(tzinfo=None)
        return start <= published_dt <= end
    except Exception:
        return True


def load_news_sources() -> dict[str, list[dict[str, str]]]:
    with NEWS_SOURCES_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_analysis(analysis: dict[str, Any]) -> tuple[list[str], str, list[str]]:
    summary = [str(item) for item in analysis.get("summary", []) if item]
    insights = analysis.get("insights") or []
    insight_lines = []
    for insight in insights[:3]:
        topic = insight.get("topic", "Topic")
        detail = insight.get("insight", "")
        importance = insight.get("importance", "")
        insight_lines.append(f"[{topic}] {detail}".strip() + (f" ({importance})" if importance else ""))

    if analysis.get("insight"):
        insight_text = str(analysis["insight"])
    else:
        insight_text = "\n".join(insight_lines)

    if analysis.get("x_post"):
        x_posts = [str(analysis["x_post"])]
    else:
        x_posts = [str(item) for item in analysis.get("x_thread", []) if item]

    return summary, insight_text, x_posts


async def upload_to_notion(
    *,
    category: str,
    analysis: dict[str, Any],
    notion: AsyncClient,
    logger,
    today_str: str,
) -> dict[str, Any]:
    summary, insight_text, x_posts = normalize_analysis(analysis)
    description = f"[Summary]\n" + "\n".join(summary[:3])
    if insight_text:
        description += f"\n\n[Insight]\n{insight_text}"

    children: list[dict[str, Any]] = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": "3-Line Summary"}}]},
        }
    ]

    for item in summary:
        children.append(
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"text": {"content": item}}]},
            }
        )

    children.extend(
        [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "Insight"}}]},
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": insight_text or "No insight available"}}]},
            },
        ]
    )

    if x_posts:
        children.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "X Draft"}}]},
            }
        )
        children.append(
            {
                "object": "block",
                "type": "code",
                "code": {
                    "language": "plain text",
                    "rich_text": [{"text": {"content": "\n\n".join(x_posts)}}],
                },
            }
        )

    return await create_notion_page_with_retry(
        notion_client=notion,
        parent={"database_id": ANTIGRAVITY_NEWS_DB_ID},
        properties={
            "Name": {"title": [{"text": {"content": f"{category} Daily Report - {today_str}"}}]},
            "Date": {"date": {"start": today_str}},
            "Description": {"rich_text": [{"text": {"content": description[:1900]}}]},
            "Source": {"select": {"name": "Mixed"}},
        },
        children=children,
        logger=logger,
        step=f"upload:{category}",
    )


async def process_category(
    *,
    category: str,
    sources: list[dict[str, str]],
    start: datetime,
    end: datetime,
    max_items: int,
    notion: AsyncClient,
    brain: Any,
    logger,
    today_str: str,
    window_name: str,
) -> dict[str, Any]:
    all_articles: list[dict[str, Any]] = []
    seen_links: set[str] = set()

    for source in sources:
        source_name = source["name"]
        source_url = source["url"]
        logger.info("fetch", "start", "fetching source", category=category, source=source_name, url=source_url)
        try:
            entries = await fetch_feed_entries(source_url)
        except Exception as exc:
            logger.error("fetch", "failed", "source fetch failed", category=category, source=source_name, error=str(exc))
            continue

        for entry in entries:
            published = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
            if not is_within_window(published, start, end):
                continue

            link = getattr(entry, "link", "")
            if not link or link in seen_links:
                continue

            article = {
                "title": getattr(entry, "title", "Untitled"),
                "description": (getattr(entry, "description", "") or getattr(entry, "summary", ""))[:300],
                "link": link,
                "published": published,
            }
            seen_links.add(link)
            all_articles.append(article)
            if len(all_articles) >= max_items:
                break

        logger.info(
            "fetch",
            "success",
            "source processed",
            category=category,
            source=source_name,
            found=len(all_articles),
        )

    if not all_articles:
        logger.warning("category", "skipped", "no articles in time window", category=category)
        return {"category": category, "status": "skipped", "articles": 0}

    if brain is None:
        logger.warning("analysis", "skipped", "brain module unavailable", category=category)
        return {"category": category, "status": "skipped", "articles": len(all_articles)}

    try:
        analysis = await run_with_timeout(
            asyncio.to_thread(brain.analyze_news, category, all_articles[:max_items]),
            60,
        )
    except Exception as exc:
        logger.error("analysis", "failed", "analysis failed", category=category, error=str(exc))
        return {"category": category, "status": "failed", "articles": len(all_articles), "error": str(exc)}

    if not analysis:
        logger.warning("analysis", "skipped", "analysis returned no result", category=category)
        return {"category": category, "status": "skipped", "articles": len(all_articles)}

    await asyncio.sleep(3)

    image_path = OUTPUT_DIR / f"infographic_{category}_{date.today()}_{window_name}.png"
    try:
        from generate_infographic import create_news_card

        summary, insight_text, _ = normalize_analysis(analysis)
        await run_with_timeout(
            asyncio.to_thread(
                create_news_card,
                category=category,
                summary=summary,
                insight=insight_text,
                output_path=str(image_path),
            ),
            30,
        )
        logger.info("image", "success", "infographic created", category=category, path=image_path)
    except Exception as exc:
        logger.warning("image", "failed", "infographic generation failed", category=category, error=str(exc))

    try:
        await upload_to_notion(
            category=category,
            analysis=analysis,
            notion=notion,
            logger=logger,
            today_str=today_str,
        )
    except Exception as exc:
        return {"category": category, "status": "failed", "articles": len(all_articles), "error": str(exc)}

    _, _, x_posts = normalize_analysis(analysis)
    if x_posts:
        tweets_path = OUTPUT_DIR / f"daily_tweets_{date.today()}_{window_name}.txt"
        with tweets_path.open("a", encoding="utf-8") as handle:
            handle.write(f"=== {category} ===\n")
            handle.write("\n\n".join(x_posts))
            handle.write("\n\n")

    logger.info("category", "success", "category processed", category=category, articles=len(all_articles))
    return {"category": category, "status": "success", "articles": len(all_articles)}


async def run_daily_news(*, force: bool, max_items: int, run_id: str | None = None) -> int:
    configure_stdout_utf8()
    run_id = run_id or generate_run_id("run_daily_news")
    logger = get_logger("run_daily_news", run_id)
    state = PipelineStateStore()
    state.record_job_start(run_id, "run_daily_news")

    if not NOTION_API_KEY:
        logger.error("bootstrap", "failed", "NOTION_API_KEY missing")
        state.record_job_finish(run_id, status="failed", error_text="NOTION_API_KEY missing")
        return 1
    if not ANTIGRAVITY_NEWS_DB_ID:
        logger.error("bootstrap", "failed", "ANTIGRAVITY_NEWS_DB_ID missing")
        state.record_job_finish(run_id, status="failed", error_text="ANTIGRAVITY_NEWS_DB_ID missing")
        return 1

    try:
        start, end, window_name = get_extraction_window(force)
    except RuntimeError as exc:
        logger.warning("window", "skipped", str(exc))
        state.record_job_finish(run_id, status="skipped", error_text=str(exc))
        return 1

    try:
        from brain_module import BrainModule

        brain = BrainModule()
    except Exception as exc:
        brain = None
        logger.warning("bootstrap", "degraded", "brain module unavailable", error=str(exc))

    notion = AsyncClient(auth=NOTION_API_KEY)
    today_str = date.today().isoformat()
    summary: dict[str, Any] = {
        "window": window_name,
        "categories_success": 0,
        "categories_failed": 0,
        "categories_skipped": 0,
        "articles": 0,
    }

    try:
        with JobLock("run_daily_news", run_id):
            news_sources = load_news_sources()
            logger.info(
                "window",
                "start",
                "processing extraction window",
                start=start.isoformat(),
                end=end.isoformat(),
                window=window_name,
            )

            for category, sources in news_sources.items():
                try:
                    result = await process_category(
                        category=category,
                        sources=sources,
                        start=start,
                        end=end,
                        max_items=max_items,
                        notion=notion,
                        brain=brain,
                        logger=logger,
                        today_str=today_str,
                        window_name=window_name,
                    )
                except Exception as exc:
                    logger.error("category", "failed", "unhandled category error", category=category, error=str(exc))
                    summary["categories_failed"] += 1
                    continue

                summary["articles"] += int(result.get("articles", 0))
                status = result.get("status")
                if status == "success":
                    summary["categories_success"] += 1
                elif status == "failed":
                    summary["categories_failed"] += 1
                else:
                    summary["categories_skipped"] += 1

            state.record_job_finish(run_id, status="success", summary=summary)
            logger.info("complete", "success", "run_daily_news finished", **summary)
            return 0
    except AlreadyRunningError:
        logger.warning("lock", "skipped", "job already running")
        state.record_job_finish(run_id, status="skipped", error_text="already running")
        return 2
    except Exception as exc:
        logger.error("complete", "failed", "run_daily_news failed", error=str(exc))
        state.record_job_finish(run_id, status="failed", summary=summary, error_text=str(exc))
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the daily news extraction and analysis pipeline.")
    parser.add_argument("--force", action="store_true", help="Ignore schedule window and use the last 24 hours")
    parser.add_argument("--max-items", type=int, default=5, help="Maximum articles to analyze per category")
    parser.add_argument("--run-id", help="Optional run identifier for logs and state tracking")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(run_daily_news(force=args.force, max_items=args.max_items, run_id=args.run_id))


if __name__ == "__main__":
    raise SystemExit(main())
