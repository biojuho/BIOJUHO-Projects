from __future__ import annotations

import json
from datetime import datetime, timedelta
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
    now = datetime.now()
    if window_name == "morning":
        end = now.replace(hour=7, minute=0, second=0, microsecond=0)
        start = (end - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        return start, end
    if window_name == "evening":
        start = now.replace(hour=7, minute=0, second=0, microsecond=0)
        end = now.replace(hour=18, minute=0, second=0, microsecond=0)
        return start, end
    return now - timedelta(hours=24), now


def is_within_window(value: Any, start: datetime, end: datetime) -> bool:
    if not value:
        return True
    try:
        if isinstance(value, str):
            parsed = date_parser.parse(value)
        else:
            parsed = datetime(*value[:6])
        if parsed.tzinfo:
            parsed = parsed.replace(tzinfo=None)
        return start <= parsed <= end
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
    feed_adapter = feed_adapter or FeedAdapter()
    source_map = load_sources()
    selected_categories = categories or list(source_map.keys())
    start, end = get_window(window_name)

    warnings: list[str] = []
    items: list[ContentItem] = []

    for category in selected_categories:
        sources = source_map.get(category, [])
        collected_for_category = 0
        for source in sources:
            try:
                entries = await feed_adapter.fetch_entries(source["url"])
            except Exception as exc:
                warnings.append(f"{category}/{source['name']} fetch failed: {type(exc).__name__}")
                continue

            for entry in entries:
                published = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
                if not is_within_window(published, start, end):
                    continue
                link = getattr(entry, "link", "")
                if not link:
                    continue
                if state_store.has_seen_article(link=link, category=category, window_name=window_name):
                    continue
                items.append(
                    ContentItem(
                        source_name=source["name"],
                        category=category,
                        title=getattr(entry, "title", "Untitled"),
                        link=link,
                        published_at="",
                        summary=(getattr(entry, "summary", "") or getattr(entry, "description", ""))[:300],
                    )
                )
                collected_for_category += 1
                if collected_for_category >= max_items:
                    break
            if collected_for_category >= max_items:
                break
    return items, warnings
