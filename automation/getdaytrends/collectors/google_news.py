"""
getdaytrends — Google News / Google Suggest Context Collector
Google News RSS + Google Suggest 자동완성 기반 컨텍스트 수집.
collectors/context.py에서 분리됨.
"""

import urllib.parse
import xml.etree.ElementTree as ET
from datetime import UTC

import httpx
from loguru import logger as log

try:
    from ..utils import run_async
except ImportError:
    from utils import run_async

_SHORT_TIMEOUT = httpx.Timeout(8.0, connect=4.0)


def _resolve_timeout(timeout: httpx.Timeout | float | None) -> httpx.Timeout | float:
    return _SHORT_TIMEOUT if timeout is None else timeout


# ══════════════════════════════════════════════════════
#  RSS Date Helpers
# ══════════════════════════════════════════════════════


def _parse_rss_date(date_str: str | None) -> "datetime | None":
    """RSS pubDate (RFC 2822) → datetime. 파싱 실패 시 None."""
    if not date_str:
        return None
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(date_str.strip())
    except Exception:
        return None


def _format_news_age(date_str: str | None) -> str:
    """pubDate → '어제', '2시간 전' 등 사람 읽기용 문자열."""
    from datetime import datetime as _dt

    dt = _parse_rss_date(date_str)
    if not dt:
        return ""
    now = _dt.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = now - dt
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{max(int(delta.total_seconds() / 60), 1)}분 전"
    elif hours < 24:
        return f"{int(hours)}시간 전"
    else:
        return f"{int(hours / 24)}일 전"


# ══════════════════════════════════════════════════════
#  Google News RSS
# ══════════════════════════════════════════════════════


async def _async_fetch_google_news_trends(
    session: httpx.AsyncClient,
    keyword: str,
    timeout: httpx.Timeout | float | None = None,
) -> str:
    """Google News RSS 기반 헤드라인 수집 (비동기)."""
    encoded_topic = urllib.parse.quote(keyword)
    insights = []

    for hl, gl, ceid in [("ko", "KR", "KR:ko"), ("en-US", "US", "US:en")]:
        url = f"https://news.google.com/rss/search?q={encoded_topic}&hl={hl}&gl={gl}&ceid={ceid}"
        try:
            resp = await session.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=_resolve_timeout(timeout),
            )
            raw = resp.read()
            root = ET.fromstring(raw)
            for item in root.findall(".//item")[:5]:
                title = item.find("title")
                pub_date = item.find("pubDate")
                if title is not None and title.text:
                    age_str = _format_news_age(pub_date.text if pub_date is not None else None)
                    dt = _parse_rss_date(pub_date.text if pub_date is not None else None)
                    time_label = dt.strftime("%m/%d %H:%M") if dt else ""
                    if age_str and time_label:
                        headline = f"[{time_label}, {age_str}] {title.text.strip()}"
                    elif age_str:
                        headline = f"[{age_str}] {title.text.strip()}"
                    else:
                        headline = title.text.strip()
                    insights.append(headline)
        except Exception:
            continue

    return " | ".join(insights) if insights else "관련 뉴스 없음"


def fetch_google_news_trends(keyword: str) -> str:
    """Google News RSS 수집 (동기 호환 래퍼)."""
    return run_async(_async_fetch_google_news_trends_standalone(keyword))


async def _async_fetch_google_news_trends_standalone(keyword: str) -> str:
    async with httpx.AsyncClient() as session:
        return await _async_fetch_google_news_trends(session, keyword)


# ══════════════════════════════════════════════════════
#  Google Trends Related Queries
# ══════════════════════════════════════════════════════


async def _async_fetch_google_trends_related(
    session: httpx.AsyncClient,
    trends: list,
    country: str = "korea",
) -> dict[str, list[str]]:
    """Google Trends 소스의 news_headlines를 related queries로 변환."""
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


# ══════════════════════════════════════════════════════
#  Google Suggest (Autocomplete)
# ══════════════════════════════════════════════════════


async def _async_fetch_google_suggest(
    query: str,
    language: str = "ko",
    country: str = "kr",
) -> list[str]:
    """Google Suggest (자동완성) API로 연관 키워드 수집."""
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
            import json

            data = json.loads(resp.text)
            if isinstance(data, list) and len(data) >= 2:
                return [s for s in data[1] if isinstance(s, str)]
            return []
    except Exception as e:
        log.debug(f"Google Suggest 수집 실패 ({query}): {e}")
        return []
