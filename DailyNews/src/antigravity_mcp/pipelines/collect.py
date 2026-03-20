from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from dateutil import parser as date_parser

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ContentItem
from antigravity_mcp.integrations.feed_adapter import FeedAdapter
from antigravity_mcp.state.store import PipelineStateStore


def load_sources() -> dict[str, list[dict[str, str]]]:
    settings = get_settings()
    with settings.news_sources_file.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_window(window_name: str) -> tuple[datetime, datetime]:
    """Return time window boundaries in UTC.

    Schedules are defined in KST (UTC+9). feedparser normalizes dates
    to UTC, so the window must also be in UTC for consistent comparison.

    - morning: KST 18:00 (prev day) ~ KST 07:00 (today)  → UTC 09:00 (prev day) ~ 22:00 (prev day)
    - evening: KST 07:00 ~ KST 18:00 (today)              → UTC 22:00 (prev day) ~ 09:00 (today)
    """
    KST_OFFSET = timedelta(hours=9)
    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc + KST_OFFSET  # aware KST

    if window_name == "morning":
        # KST 18:00 (prev day) ~ KST 07:00 (today)
        end_kst = now_kst.replace(hour=7, minute=0, second=0, microsecond=0)
        start_kst = (end_kst - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        return start_kst - KST_OFFSET, end_kst - KST_OFFSET
    if window_name == "evening":
        # KST 07:00 ~ KST 18:00 (today)
        start_kst = now_kst.replace(hour=7, minute=0, second=0, microsecond=0)
        end_kst = now_kst.replace(hour=18, minute=0, second=0, microsecond=0)
        return start_kst - KST_OFFSET, end_kst - KST_OFFSET
    return now_utc - timedelta(hours=24), now_utc


def is_within_window(value: Any, start: datetime, end: datetime) -> bool:
    if not value:
        return True
    try:
        if isinstance(value, str):
            parsed = date_parser.parse(value)
        else:
            parsed = datetime(*value[:6])
        # Normalize both sides to UTC-aware for consistent comparison
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        aware_start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
        aware_end = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
        return aware_start <= parsed <= aware_end
    except Exception:
        return True


async def collect_content_items(
    *,
    categories: list[str] | None,
    window_name: str,
    max_items: int,
    state_store: PipelineStateStore,
    feed_adapter: FeedAdapter | None = None,
) -> tuple[list[ContentItem], list[str]]:
    settings = get_settings()
    feed_adapter = feed_adapter or FeedAdapter(state_store=state_store)
    source_map = load_sources()
    selected_categories = categories or list(source_map.keys())
    start, end = get_window(window_name)
    semaphore = asyncio.Semaphore(max(1, settings.pipeline_max_concurrency))

    import math

    warnings: list[str] = []
    items: list[ContentItem] = []

    async def _collect_category(category: str) -> tuple[list[ContentItem], list[str]]:
        """Collect items for a single category (runs concurrently)."""
        sources = source_map.get(category, [])
        if not sources:
            return [], []

        cat_warnings: list[str] = []
        cat_items: list[ContentItem] = []

        async def _fetch_one(source: dict[str, str]) -> tuple[str, list, Exception | None]:
            try:
                async with semaphore:
                    entries = await feed_adapter.fetch_entries(source["url"])
                return source["name"], entries, None
            except Exception as exc:
                return source["name"], [], exc

        fetch_results = await asyncio.gather(*[_fetch_one(s) for s in sources])

        max_per_source = max(1, math.ceil(max_items / max(1, len(sources))))

        collected_for_category = 0
        for source_name, entries, exc in fetch_results:
            if exc is not None:
                cat_warnings.append(f"{category}/{source_name} fetch failed: {type(exc).__name__}")
                continue

            source_count = 0
            for entry in entries:
                if collected_for_category >= max_items:
                    break
                if source_count >= max_per_source:
                    break
                published = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
                if not is_within_window(published, start, end):
                    continue
                link = getattr(entry, "link", "")
                if not link:
                    continue
                if state_store.has_seen_article(link=link, category=category, window_name=window_name):
                    continue
                cat_items.append(
                    ContentItem(
                        source_name=source_name,
                        category=category,
                        title=getattr(entry, "title", "Untitled"),
                        link=link,
                        published_at="",
                        summary=(getattr(entry, "summary", "") or getattr(entry, "description", ""))[:300],
                    )
                )
                collected_for_category += 1
                source_count += 1
            if collected_for_category >= max_items:
                break
        return cat_items, cat_warnings

    # Parallel category collection
    results = await asyncio.gather(*[_collect_category(cat) for cat in selected_categories])
    for cat_items, cat_warnings in results:
        items.extend(cat_items)
        warnings.extend(cat_warnings)

    return items, warnings
