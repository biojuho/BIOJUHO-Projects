"""Fetch timestamped publisher-original news links for a trend keyword."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from content_filters import topic_is_allowed


BING_NEWS_RSS_URL = "https://www.bing.com/news/search"
_AGGREGATOR_DOMAINS = ("bing.com", "msn.com")


def _direct_url(value: str) -> str:
    parsed = urlparse(value)
    query_target = (parse_qs(parsed.query).get("url") or [""])[0]
    target = query_target or value
    target_parsed = urlparse(target)
    if target_parsed.scheme not in {"http", "https"}:
        return ""
    domain = target_parsed.netloc.casefold().removeprefix("www.")
    if any(domain == blocked or domain.endswith(f".{blocked}") for blocked in _AGGREGATOR_DOMAINS):
        return ""
    return target


def _source_name(item: ET.Element, url: str) -> str:
    for child in item:
        if child.tag.split("}", 1)[-1].casefold() == "source" and child.text:
            return re.sub(r"\s+on\s+msn$", "", child.text.strip(), flags=re.IGNORECASE)
    return urlparse(url).netloc.removeprefix("www.")


def parse_bing_news_rss(
    raw: bytes,
    *,
    limit: int = 8,
    now: datetime | None = None,
    max_age_hours: int = 48,
) -> list[dict[str, Any]]:
    root = ET.fromstring(raw)
    reference = (now or datetime.now(UTC)).astimezone(UTC)
    cutoff = reference - timedelta(hours=max_age_hours)
    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        url = _direct_url((item.findtext("link") or "").strip())
        if not title or not url or url in seen_urls or not topic_is_allowed(title):
            continue
        published_raw = (item.findtext("pubDate") or "").strip()
        try:
            published = parsedate_to_datetime(published_raw).astimezone(UTC)
        except (TypeError, ValueError):
            published = None
        if published is None or published < cutoff or published > reference + timedelta(minutes=10):
            continue
        seen_urls.add(url)
        results.append(
            {
                "title": title,
                "url": url,
                "source": _source_name(item, url),
                "published_at": published.isoformat() if published else None,
                "discovered_via": "Bing News RSS",
            }
        )
        if len(results) >= limit:
            break
    return results


async def fetch_bing_news_origins(
    session: httpx.AsyncClient,
    keyword: str,
    limit: int = 8,
) -> list[dict[str, Any]]:
    response = await session.get(
        BING_NEWS_RSS_URL,
        params={"q": keyword, "format": "rss", "mkt": "ko-KR"},
        timeout=httpx.Timeout(10.0, connect=4.0),
    )
    response.raise_for_status()
    return parse_bing_news_rss(response.content, limit=limit)
