from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import TYPE_CHECKING, Any, cast

try:
    from dateutil import parser as date_parser  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - optional dependency
    date_parser = None

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ContentItem
from antigravity_mcp.state.store import PipelineStateStore

if TYPE_CHECKING:
    from antigravity_mcp.integrations.feed_adapter import FeedAdapter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _FetchResult:
    source_name: str
    entries: list[Any]
    error: Exception | None


async def fetch_article_body(url: str, max_chars: int = 1500) -> str:
    """Fetch and extract article body text from a URL using trafilatura."""
    try:
        import trafilatura

        downloaded = await asyncio.to_thread(trafilatura.fetch_url, url)
        if not downloaded:
            return ""
        text = await asyncio.to_thread(
            trafilatura.extract,
            downloaded,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        return (text or "")[:max_chars]
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        logger.debug("Article body fetch failed for %s: %s", url, exc)
        return ""


def load_sources() -> dict[str, list[dict[str, str]]]:
    settings = get_settings()
    try:
        with settings.news_sources_file.open("r", encoding="utf-8") as handle:
            raw_sources = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load news sources from %s: %s", settings.news_sources_file, exc)
        return {}

    if not isinstance(raw_sources, dict):
        logger.warning("News sources config must be a JSON object, got %s", type(raw_sources).__name__)
        return {}

    normalized: dict[str, list[dict[str, str]]] = {}
    for category, raw_entries in raw_sources.items():
        if not isinstance(category, str):
            logger.warning("Skipping non-string category key in news sources config: %r", category)
            continue
        if not isinstance(raw_entries, list):
            logger.warning("Skipping category %s because sources are not a list", category)
            continue

        valid_entries: list[dict[str, str]] = []
        for entry in raw_entries:
            if not isinstance(entry, dict):
                logger.warning("Skipping malformed source entry in %s: %r", category, entry)
                continue

            name = entry.get("name")
            url = entry.get("url")
            if not isinstance(name, str) or not name.strip() or not isinstance(url, str) or not url.strip():
                logger.warning("Skipping incomplete source entry in %s: %r", category, entry)
                continue

            valid_entries.append({"name": name.strip(), "url": url.strip()})

        normalized[category] = valid_entries

    return normalized


def get_window(window_name: str) -> tuple[datetime, datetime]:
    """Return time window boundaries in UTC.

    Schedules are defined in KST (UTC+9). feedparser normalizes dates
    to UTC, so the window must also be in UTC for consistent comparison.

    - morning: KST 18:00 (prev day) ~ KST 07:00 (today)  → UTC 09:00 (prev day) ~ 22:00 (prev day)
    - evening: KST 07:00 ~ KST 18:00 (today)              → UTC 22:00 (prev day) ~ 09:00 (today)
    """
    KST_OFFSET = timedelta(hours=9)
    now_utc = datetime.now(UTC)
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


def is_within_window(value: Any, start: datetime, end: datetime, *, allow_missing: bool = False) -> bool:
    if not value:
        if allow_missing:
            logger.debug("Including entry with missing publish date because allow_missing=True")
            return True
        # No publish date at all — cannot verify, exclude to avoid stale content
        logger.debug("Excluding entry with missing publish date from window check")
        return False
    try:
        if isinstance(value, str):
            if date_parser is not None:
                parsed = cast("datetime", date_parser.parse(value))
            else:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            parsed = datetime(*value[:6])
        # Normalize both sides to UTC-aware for consistent comparison
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        aware_start = start if start.tzinfo else start.replace(tzinfo=UTC)
        aware_end = end if end.tzinfo else end.replace(tzinfo=UTC)
        return aware_start <= parsed <= aware_end
    except (ValueError, TypeError, OverflowError) as exc:
        logger.warning("Date parsing failed for value %r, excluding entry: %s", value, exc)
        return False


async def _fetch_source_entries(
    source: dict[str, str],
    feed_adapter: FeedAdapter,
    semaphore: asyncio.Semaphore,
) -> _FetchResult:
    try:
        async with semaphore:
            entries = await feed_adapter.fetch_entries(source["url"])
        return _FetchResult(source_name=source["name"], entries=entries, error=None)
    except Exception as exc:
        return _FetchResult(source_name=source["name"], entries=[], error=exc)


def _candidate_links(fetch_results: list[_FetchResult]) -> list[str]:
    links: list[str] = []
    for result in fetch_results:
        if result.error is not None:
            continue
        for entry in result.entries:
            link = getattr(entry, "link", "")
            if link:
                links.append(link)
    return links


def _max_per_source(max_items: int, sources: list[dict[str, str]]) -> int:
    return max(1, ceil(max_items / max(1, len(sources))))


def _content_item_from_entry(entry: Any, *, source_name: str, category: str, link: str) -> ContentItem:
    return ContentItem(
        source_name=source_name,
        category=category,
        title=getattr(entry, "title", "Untitled"),
        link=link,
        published_at="",
        summary=(getattr(entry, "summary", "") or getattr(entry, "description", ""))[:300],
    )


async def _fetch_article_bodies(category: str, items: list[ContentItem]) -> None:
    body_sem = asyncio.Semaphore(5)

    async def _fetch_body(item: ContentItem) -> None:
        async with body_sem:
            body = await fetch_article_body(item.link)
            if body:
                item.full_text = body

    await asyncio.gather(*[_fetch_body(item) for item in items])
    body_count = sum(1 for item in items if item.full_text)
    if body_count:
        logger.info("[%s] Deep collect: %d/%d articles with body text", category, body_count, len(items))


async def _collect_category(
    *,
    category: str,
    source_map: dict[str, list[dict[str, str]]],
    window_name: str,
    max_items: int,
    state_store: PipelineStateStore,
    feed_adapter: FeedAdapter,
    semaphore: asyncio.Semaphore,
    start: datetime,
    end: datetime,
    fetch_bodies: bool,
) -> tuple[list[ContentItem], list[str]]:
    sources = source_map.get(category, [])
    if not sources:
        return [], [f"No sources configured for category '{category}'."]

    cat_warnings: list[str] = []
    cat_items: list[ContentItem] = []
    fetch_results = await asyncio.gather(
        *[_fetch_source_entries(source, feed_adapter, semaphore) for source in sources]
    )
    max_per_source = _max_per_source(max_items, sources)
    seen_links = state_store.get_seen_links(
        links=_candidate_links(list(fetch_results)),
        category=category,
        window_name=window_name,
    )

    collected_for_category = 0
    for result in fetch_results:
        if result.error is not None:
            cat_warnings.append(f"{category}/{result.source_name} fetch failed: {type(result.error).__name__}")
            continue

        source_count = 0
        for entry in result.entries:
            if collected_for_category >= max_items:
                break
            if source_count >= max_per_source:
                break
            published = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
            if not is_within_window(published, start, end, allow_missing=window_name == "manual"):
                continue
            link = getattr(entry, "link", "")
            if not link:
                continue
            if link in seen_links:
                continue
            cat_items.append(
                _content_item_from_entry(entry, source_name=result.source_name, category=category, link=link)
            )
            collected_for_category += 1
            source_count += 1
        if collected_for_category >= max_items:
            break

    if fetch_bodies and cat_items:
        await _fetch_article_bodies(category, cat_items)

    return cat_items, cat_warnings


async def collect_content_items(
    *,
    categories: list[str] | None,
    window_name: str,
    max_items: int,
    state_store: PipelineStateStore,
    feed_adapter: FeedAdapter | None = None,
    fetch_bodies: bool = True,
) -> tuple[list[ContentItem], list[str]]:
    settings = get_settings()
    if feed_adapter is None:
        from antigravity_mcp.integrations.feed_adapter import FeedAdapter

        feed_adapter = FeedAdapter(state_store=state_store)
    source_map = load_sources()
    warnings: list[str] = []
    items: list[ContentItem] = []

    if not source_map:
        warnings.append("Source configuration unavailable or empty.")
        return items, warnings

    selected_categories = categories or list(source_map.keys())
    start, end = get_window(window_name)
    semaphore = asyncio.Semaphore(max(1, settings.pipeline_max_concurrency))

    # Parallel category collection
    results = await asyncio.gather(
        *[
            _collect_category(
                category=category,
                source_map=source_map,
                window_name=window_name,
                max_items=max_items,
                state_store=state_store,
                feed_adapter=feed_adapter,
                semaphore=semaphore,
                start=start,
                end=end,
                fetch_bodies=fetch_bodies,
            )
            for category in selected_categories
        ]
    )
    for cat_items, cat_warnings in results:
        items.extend(cat_items)
        warnings.extend(cat_warnings)

    return items, warnings
