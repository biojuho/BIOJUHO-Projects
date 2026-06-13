"""Google News / Google Suggest collectors."""

from __future__ import annotations

import json
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import httpx
from loguru import logger as log

try:
    from ..utils import run_async
except ImportError:
    from utils import run_async

_SHORT_TIMEOUT = httpx.Timeout(8.0, connect=4.0)
_MAX_TREND_NEWS_AGE_DAYS = 30


def _resolve_timeout(timeout: httpx.Timeout | float | None) -> httpx.Timeout | float:
    return _SHORT_TIMEOUT if timeout is None else timeout


def _parse_rss_date(date_str: str | None) -> datetime | None:
    """Parse RSS pubDate (RFC 2822)."""
    if not date_str:
        return None
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(date_str.strip())
    except Exception:
        return None


def _format_news_age(date_str: str | None) -> str:
    """Render a human-readable age string from pubDate."""
    dt = _parse_rss_date(date_str)
    if not dt:
        return ""
    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = now - dt
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{max(int(delta.total_seconds() / 60), 1)}분 전"
    if hours < 24:
        return f"{int(hours)}시간 전"
    return f"{int(hours / 24)}일 전"


def _is_fresh_enough(dt: datetime | None) -> bool:
    if dt is None:
        return True
    dt_utc = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    age_days = (datetime.now(UTC) - dt_utc.astimezone(UTC)).total_seconds() / 86400
    return age_days <= _MAX_TREND_NEWS_AGE_DAYS


async def _async_fetch_google_news_trends(
    session: httpx.AsyncClient,
    keyword: str,
    timeout: httpx.Timeout | float | None = None,
) -> str:
    """Fetch recent Google News RSS headlines for a keyword."""
    insights: list[str] = []
    seen_titles: set[str] = set()

    for url in _google_news_rss_urls(keyword):
        root = await _fetch_google_news_rss_root(session, url, timeout)
        if root is not None:
            _append_google_news_headlines(root, insights, seen_titles)

    return " | ".join(insights) if insights else "관련 뉴스 없음"


def _google_news_rss_urls(keyword: str) -> list[str]:
    encoded_topic = urllib.parse.quote(keyword)
    return [
        f"https://news.google.com/rss/search?q={encoded_topic}&hl={hl}&gl={gl}&ceid={ceid}"
        for hl, gl, ceid in (("ko", "KR", "KR:ko"), ("en-US", "US", "US:en"))
    ]


async def _fetch_google_news_rss_root(
    session: httpx.AsyncClient,
    url: str,
    timeout: httpx.Timeout | float | None,
) -> ET.Element | None:
    try:
        resp = await session.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_resolve_timeout(timeout),
        )
        return ET.fromstring(resp.read())
    except Exception:
        return None


def _append_google_news_headlines(
    root: ET.Element,
    insights: list[str],
    seen_titles: set[str],
) -> None:
    for item in root.findall(".//item")[:5]:
        headline = _google_news_headline(item, seen_titles)
        if headline:
            insights.append(headline)


def _google_news_headline(item: ET.Element, seen_titles: set[str]) -> str:
    title = item.find("title")
    pub_date = item.find("pubDate")
    if title is None or not title.text:
        return ""

    title_text = title.text.strip()
    title_key = title_text.casefold()
    if title_key in seen_titles:
        return ""

    date_text = pub_date.text if pub_date is not None else None
    dt = _parse_rss_date(date_text)
    if not _is_fresh_enough(dt):
        return ""

    seen_titles.add(title_key)
    return _format_google_news_headline(title_text, date_text, dt)


def _format_google_news_headline(
    title_text: str,
    date_text: str | None,
    dt: datetime | None,
) -> str:
    age_str = _format_news_age(date_text)
    time_label = dt.strftime("%m/%d %H:%M") if dt else ""
    if age_str and time_label:
        return f"[{time_label}, {age_str}] {title_text}"
    if age_str:
        return f"[{age_str}] {title_text}"
    return title_text

def fetch_google_news_trends(keyword: str) -> str:
    """Sync wrapper for Google News RSS collection."""
    return run_async(_async_fetch_google_news_trends_standalone(keyword))


async def _async_fetch_google_news_trends_standalone(keyword: str) -> str:
    async with httpx.AsyncClient() as session:
        return await _async_fetch_google_news_trends(session, keyword)


async def _async_fetch_google_trends_related(
    session: httpx.AsyncClient,
    trends: list,
    country: str = "korea",
) -> dict[str, list[str]]:
    """Reuse Google Trends RSS headlines as related-query hints."""
    try:
        from ..models import TrendSource
    except ImportError:
        from models import TrendSource

    result: dict[str, list[str]] = {}
    for trend in trends:
        if trend.source != TrendSource.GOOGLE_TRENDS:
            continue
        headlines = (trend.extra or {}).get("news_headlines", [])
        if headlines:
            result[trend.name] = list(headlines)
    return result


async def _async_fetch_google_suggest(
    query: str,
    language: str = "ko",
    country: str = "kr",
) -> list[str]:
    """Fetch Google autocomplete suggestions."""
    encoded = urllib.parse.quote(query)
    url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={encoded}&hl={language}&gl={country}"

    try:
        async with httpx.AsyncClient() as session:
            resp = await session.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=_SHORT_TIMEOUT,
            )
            resp.raise_for_status()
            data = json.loads(resp.text)
            if isinstance(data, list) and len(data) >= 2:
                return [item for item in data[1] if isinstance(item, str)]
            return []
    except Exception as exc:
        log.debug(f"Google Suggest collection failed ({query}): {exc}")
        return []
