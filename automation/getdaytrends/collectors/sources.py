"""collectors/sources — 개별 소스 수집 함수 모음.

scraper.py에서 추출한 소스별 트렌드 수집 로직을 모아둔 모듈.
각 소스(getdaytrends.com, Google Trends RSS, YouTube Trending RSS)와
공통 유틸리티(RSS 파싱, 볼륨 파싱, 캐시, 중복 필터, 트렌드 병합)를 포함.

기존 ``from scraper import ...`` 호환성은 scraper.py의 re-export로 유지.
"""

import asyncio
import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import httpx
from loguru import logger as log

try:
    from ..models import RawTrend, TrendSource
    from ..utils import run_async
except ImportError:
    from models import RawTrend, TrendSource
    from utils import run_async

# ══════════════════════════════════════════════════════
#  공통 상수 & 유틸리티
# ══════════════════════════════════════════════════════

_COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
}

# 기본 타임아웃 설정 (초)
_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=6.0)
_SHORT_TIMEOUT = httpx.Timeout(8.0, connect=4.0)

# Phase 3: getdaytrends.com 수집 결과 1시간 메모리 캐시
# { country_slug: (fetched_at_unix, [RawTrend, ...]) }
_FETCH_CACHE: dict[str, tuple[float, list[RawTrend]]] = {}
_FETCH_CACHE_TTL = 3600  # 1시간 (초)


# [v6.1] RSS pubDate 파싱 헬퍼
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


def _parse_volume_text(text: str) -> int:
    """볼륨 문자열을 숫자로 변환. '50K+' → 50000, '<10K' → 9999 등."""
    text = text.strip().upper().replace(",", "").replace("+", "")
    text = text.replace("UNDER ", "<")
    if not text or text == "N/A":
        return 0
    m = re.search(r"<?(\d+(?:\.\d+)?)\s*([KMB])?", text)
    if not m:
        return 0
    num = float(m.group(1))
    suffix = m.group(2) or ""
    multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(suffix, 1)
    result = int(num * multiplier)
    if text.startswith("<"):
        result = max(result - 1, 0)
    return result


# ══════════════════════════════════════════════════════
#  Source 1: getdaytrends.com
# ══════════════════════════════════════════════════════


def _getdaytrends_url(country_slug: str) -> str:
    base_url = "https://getdaytrends.com"
    return f"{base_url}/{country_slug}/" if country_slug else f"{base_url}/"


def _getdaytrends_cache_key(country_slug: str) -> str:
    return country_slug or "global"


def _fresh_getdaytrends_cache(cache_key: str, limit: int) -> list[RawTrend] | None:
    cached = _FETCH_CACHE.get(cache_key)
    if not cached:
        return None
    cached_at, cached_trends = cached
    cache_age = time.time() - cached_at
    if cache_age >= _FETCH_CACHE_TTL:
        return None
    log.info(f"[?섏쭛 罹먯떆] getdaytrends.com ?ъ궗?? {len(cached_trends)}媛?({cache_key}, {int(cache_age)}珥???")
    return cached_trends[:limit]


def _getdaytrends_soup(html: str) -> object:
    from bs4 import BeautifulSoup

    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _getdaytrends_rows(soup) -> list:
    rows = soup.select("table.trends tbody tr")
    return rows or soup.select("table tr")


def _getdaytrends_row_to_trend(row, country_slug: str) -> RawTrend | None:
    base_url = "https://getdaytrends.com"
    name_el = row.select_one(".main a") or row.select_one("a")
    if not name_el:
        return None

    name = name_el.get_text(strip=True).lstrip("#").strip()
    if not name:
        return None

    volume_el = row.select_one(".desc")
    volume_text = volume_el.get_text(strip=True) if volume_el else "N/A"
    href = name_el.get("href", "")
    link = f"{base_url}{href}" if href and not href.startswith("http") else href
    return RawTrend(
        name=name,
        source=TrendSource.GETDAYTRENDS,
        volume=volume_text,
        volume_numeric=_parse_volume_text(volume_text),
        link=link,
        country=country_slug or "global",
    )


def _parse_getdaytrends_html(html: str, country_slug: str, limit: int) -> list[RawTrend]:
    trends: list[RawTrend] = []
    for row in _getdaytrends_rows(_getdaytrends_soup(html)):
        trend = _getdaytrends_row_to_trend(row, country_slug)
        if trend is None:
            continue
        trends.append(trend)
        if len(trends) >= limit:
            break
    return trends


async def _async_fetch_getdaytrends(session: httpx.AsyncClient, country_slug: str, limit: int = 50) -> list[RawTrend]:
    """Fetch trends from getdaytrends.com asynchronously."""
    cache_key = _getdaytrends_cache_key(country_slug)
    cached_trends = _fresh_getdaytrends_cache(cache_key, limit)
    if cached_trends is not None:
        return cached_trends

    try:
        resp = await session.get(_getdaytrends_url(country_slug), headers=_COMMON_HEADERS, timeout=_DEFAULT_TIMEOUT)
        resp.raise_for_status()
        trends = _parse_getdaytrends_html(resp.text, country_slug, limit)
        if not trends:
            log.warning("getdaytrends.com parsing failed. Using fallback trends.")
            return _fallback_trends()

        _FETCH_CACHE[cache_key] = (time.time(), trends)
        log.info(f"getdaytrends.com collection complete: {len(trends)} ({country_slug or 'global'})")
        return trends

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code if e.response is not None else "unknown"
        log.error(f"getdaytrends.com HTTP error ({status_code}): {e}")
        return _fallback_trends()
    except httpx.RequestError as e:
        log.error(f"getdaytrends.com request failed: {type(e).__name__}: {e}")
        return _fallback_trends()
    except Exception as e:
        log.error(f"getdaytrends.com collection failed: {e}")
        return _fallback_trends()

def fetch_getdaytrends(country_slug: str, limit: int = 50) -> list[RawTrend]:
    """getdaytrends.com에서 트렌드 수집 (동기 호환 래퍼)."""
    return run_async(_async_fetch_getdaytrends_standalone(country_slug, limit))


async def _async_fetch_getdaytrends_standalone(country_slug: str, limit: int = 50) -> list[RawTrend]:
    """독립 세션으로 getdaytrends 수집 (단독 호출용)."""
    async with httpx.AsyncClient() as session:
        return await _async_fetch_getdaytrends(session, country_slug, limit)


def _fallback_trends() -> list[RawTrend]:
    """스크래핑 실패 시 대체 주제."""
    fallbacks = ["주말 계획", "점심 메뉴", "날씨", "커피", "퇴근"]
    return [RawTrend(name=t, source=TrendSource.GETDAYTRENDS) for t in fallbacks]


# ══════════════════════════════════════════════════════
#  Source 2: Google Trends RSS (무료, API 키 불필요)
# ══════════════════════════════════════════════════════

_GEO_MAP = {
    "korea": "KR",
    "us": "US",
    "united-states": "US",
    "japan": "JP",
    "united-kingdom": "GB",
    "india": "IN",
    "": "US",
}


def _is_korean_trend(name: str, country_slug: str) -> bool:
    """한국어 대상일 때 한글 포함 또는 영어권 국가 트렌드만 허용."""
    if len(name) < 2:
        return False  # 단일 문자 노이즈 제거
    if country_slug not in ("korea", "KR"):
        return True  # 비한국 국가는 그대로 허용
    # 한글 유니코드 범위: AC00-D7A3 (완성형), 1100-11FF (자모)
    has_hangul = any("\uac00" <= c <= "\ud7a3" or "\u1100" <= c <= "\u11ff" for c in name)
    # 영어 혹은 한글이면 허용
    is_ascii = all(ord(c) < 128 for c in name.replace(" ", ""))
    return has_hangul or is_ascii


def _google_trends_geo(country_slug: str) -> str:
    return _GEO_MAP.get(country_slug, "KR") if country_slug else "KR"


def _google_trends_rss_url(geo: str) -> str:
    return f"https://trends.google.com/trending/rss?geo={geo}"


def _parse_google_trends_root(raw: bytes) -> object:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        log.warning(f"Google Trends RSS parse failed: {exc}")
        return None

    root_tag = root.tag.split("}", 1)[-1].lower()
    if root_tag not in {"rss", "feed"}:
        log.warning(f"Google Trends RSS unexpected root tag: {root_tag}")
        return None
    return root


def _google_trends_news_items(item, ns: dict[str, str]) -> list[str]:
    news_items = []
    for news_item in item.findall("ht:news_item", ns)[:2]:
        news_title = news_item.find("ht:news_item_title", ns)
        if news_title is not None and news_title.text:
            news_items.append(news_title.text.strip())
    return news_items


def _google_trends_item_to_raw(item, ns: dict[str, str], country_slug: str) -> RawTrend | None:
    title_el = item.find("title")
    if title_el is None or not title_el.text:
        return None

    name = title_el.text.strip()
    if not _is_korean_trend(name, country_slug):
        log.debug(f"  [Google Trends] 鍮꾪븳援?뼱 ?꾪꽣: '{name}'")
        return None

    traffic_el = item.find("ht:approx_traffic", ns)
    volume_text = traffic_el.text.strip() if traffic_el is not None else "N/A"
    link_el = item.find("link")
    pub_date_el = item.find("pubDate")
    return RawTrend(
        name=name,
        source=TrendSource.GOOGLE_TRENDS,
        volume=volume_text,
        volume_numeric=_parse_volume_text(volume_text.replace("+", "").replace(",", "")),
        link=link_el.text.strip() if link_el is not None and link_el.text else "",
        country=country_slug or "global",
        extra={"news_headlines": _google_trends_news_items(item, ns)},
        published_at=_parse_rss_date(pub_date_el.text if pub_date_el is not None else None),
    )


def _parse_google_trends_items(raw: bytes, country_slug: str, limit: int) -> list[RawTrend]:
    root = _parse_google_trends_root(raw)
    if root is None:
        return []

    ns = {"ht": "https://trends.google.com/trending/rss"}
    trends: list[RawTrend] = []
    for item in root.findall(".//item"):
        trend = _google_trends_item_to_raw(item, ns, country_slug)
        if trend is None:
            continue
        trends.append(trend)
        if len(trends) >= limit:
            break
    return trends


async def _async_fetch_google_trends_rss(
    session: httpx.AsyncClient, country_slug: str, limit: int = 20
) -> list[RawTrend]:
    """Fetch realtime trends from Google Trends RSS asynchronously."""
    geo = _google_trends_geo(country_slug)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; TrendBot/2.3)"}

    try:
        resp = await session.get(_google_trends_rss_url(geo), headers=headers, timeout=_SHORT_TIMEOUT)
        resp.raise_for_status()
        trends = _parse_google_trends_items(resp.read(), country_slug, limit)
        log.info(f"Google Trends RSS collection complete: {len(trends)} ({geo})")
        return trends

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code if e.response is not None else "unknown"
        log.warning(f"Google Trends RSS HTTP error ({status_code}): {e}")
        return []
    except httpx.RequestError as e:
        log.warning(f"Google Trends RSS request failed: {type(e).__name__}: {e}")
        return []
    except Exception as e:
        log.warning(f"Google Trends RSS collection failed: {e}")
        return []

def fetch_google_trends_rss(country_slug: str, limit: int = 20) -> list[RawTrend]:
    """Google Trends RSS 수집 (동기 호환 래퍼)."""
    return run_async(_async_fetch_google_trends_rss_standalone(country_slug, limit))


async def _async_fetch_google_trends_rss_standalone(country_slug: str, limit: int = 20) -> list[RawTrend]:
    """독립 세션으로 Google Trends RSS 수집 (단독 호출용)."""
    async with httpx.AsyncClient() as session:
        return await _async_fetch_google_trends_rss(session, country_slug, limit)


def _is_similar_keyword(new_keyword: str, existing: set[str]) -> bool:
    """키워드 유사도 비교: 부분 문자열 매칭으로 중복 판단."""
    new_lower = new_keyword.lower().strip()
    if new_lower in existing:  # 정확 일치
        return True
    for kw in existing:
        kw_lower = kw.lower().strip()
        # 길이가 3자 이상인 경우만 부분 매칭 (너무 짧으면 오탐)
        if len(new_lower) >= 3 and len(kw_lower) >= 3:
            if new_lower in kw_lower or kw_lower in new_lower:
                log.debug(f"  유사 키워드 감지: '{new_keyword}' ≈ '{kw}'")
                return True
    return False


# ══════════════════════════════════════════════════════
#  Source 3: YouTube Trending RSS (무료, API키 불필요)
# ══════════════════════════════════════════════════════

_YOUTUBE_GEO_MAP = {
    "korea": "KR",
    "united-states": "US",
    "japan": "JP",
    "united-kingdom": "GB",
    "india": "IN",
    "": "KR",
}


async def _async_fetch_youtube_trending(
    session: httpx.AsyncClient, country_slug: str = "korea", limit: int = 10
) -> list[RawTrend]:
    """YouTube 인기 동영상 RSS에서 트렌드 키워드를 추출 (비동기)."""
    country_code = _YOUTUBE_GEO_MAP.get(country_slug, "KR")
    raw = await _fetch_youtube_trending_feed(session, _youtube_trending_url(country_code))
    if raw is None:
        return []

    trends = _parse_youtube_trending_feed(raw, country_slug or "korea", limit)
    log.info(f"YouTube Trending 수집 완료: {len(trends)}개 ({country_code})")
    return trends


def _youtube_trending_url(country_code: str) -> str:
    return f"https://www.youtube.com/feeds/videos.xml?gl={country_code}&hl=ko"


async def _fetch_youtube_trending_feed(session: httpx.AsyncClient, url: str) -> bytes | None:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; TrendBot/4.1)"}
    for attempt in range(1, 4):
        try:
            resp = await session.get(url, headers=headers, timeout=_SHORT_TIMEOUT)
            resp.raise_for_status()
            raw = resp.read()
            return raw if isinstance(raw, bytes) else None
        except Exception as e:
            if attempt == 3:
                log.debug(f"YouTube Trending 수집 최종 실패 (3회 초과): {e}")
                return None
            backoff = 2**attempt
            log.warning(f"YouTube API 에러({e}), {backoff}초 후 재시도 ({attempt}/3)")
            await asyncio.sleep(backoff)
    return None


def _parse_youtube_trending_feed(raw: bytes, country_slug: str, limit: int) -> list[RawTrend]:
    try:
        root = ET.fromstring(raw)
    except Exception as e:
        log.debug(f"YouTube Trending 수집 실패 (무시): {e}")
        return []

    ns = _youtube_feed_namespaces()
    trends: list[RawTrend] = []
    for entry in root.findall("atom:entry", ns)[:limit]:
        trend = _youtube_entry_to_raw_trend(entry, ns, country_slug)
        if trend is not None:
            trends.append(trend)
    return trends


def _youtube_feed_namespaces() -> dict[str, str]:
    return {
        "atom": "http://www.w3.org/2005/Atom",
        "media": "http://search.yahoo.com/mrss/",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }


def _youtube_entry_to_raw_trend(
    entry: ET.Element,
    ns: dict[str, str],
    country_slug: str,
) -> RawTrend | None:
    title_el = entry.find("atom:title", ns)
    if title_el is None or not title_el.text:
        return None

    name = title_el.text.strip()
    if len(name) < 2:
        return None

    view_count = _youtube_view_count(entry, ns)
    return RawTrend(
        name=name,
        source=TrendSource.YOUTUBE,
        volume=f"{view_count:,} views" if view_count else "N/A",
        volume_numeric=view_count,
        link=_youtube_entry_link(entry, ns),
        country=country_slug,
    )


def _youtube_entry_link(entry: ET.Element, ns: dict[str, str]) -> str:
    link_el = entry.find("atom:link", ns)
    return link_el.get("href", "") if link_el is not None else ""


def _youtube_view_count(entry: ET.Element, ns: dict[str, str]) -> int:
    stats_el = entry.find("yt:statistics", ns)
    if stats_el is None:
        return 0
    try:
        return int(stats_el.get("viewCount", "0"))
    except ValueError:
        return 0

def fetch_youtube_trending(country_slug: str = "korea", limit: int = 10) -> list[RawTrend]:
    """YouTube 인기 동영상 RSS 수집 (동기 호환 래퍼)."""
    return run_async(_async_fetch_youtube_trending_standalone(country_slug, limit))


async def _async_fetch_youtube_trending_standalone(country_slug: str = "korea", limit: int = 10) -> list[RawTrend]:
    """독립 세션으로 YouTube Trending 수집 (단독 호출용)."""
    async with httpx.AsyncClient() as session:
        return await _async_fetch_youtube_trending(session, country_slug, limit)


# ══════════════════════════════════════════════════════
#  Source 4: Hacker News (Algolia front-page API, 무료 무인증)
# ══════════════════════════════════════════════════════
#  X API에 종속되지 않은 보조 트렌드 신호. 기술/AI/스타트업 토픽에 강함.

_HN_FRONTPAGE_URL = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage={limit}"


async def _hacker_news_payload(session: httpx.AsyncClient, limit: int) -> dict:
    url = _HN_FRONTPAGE_URL.format(limit=limit)
    headers = {"User-Agent": "GetDayTrends/2.4 (mailto:biojuho@gmail.com)"}
    resp = await session.get(url, headers=headers, timeout=_SHORT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _hacker_news_title(hit: dict) -> str:
    return (hit.get("title") or hit.get("story_title") or "").strip()


def _hacker_news_link(hit: dict) -> str:
    story_id = hit.get("objectID", "")
    return hit.get("url") or (f"https://news.ycombinator.com/item?id={story_id}" if story_id else "")


def _hacker_news_trend_from_hit(hit: dict) -> RawTrend | None:
    title = _hacker_news_title(hit)
    if not title or len(title) < 3:
        return None

    points = int(hit.get("points") or 0)
    comments = int(hit.get("num_comments") or 0)
    return RawTrend(
        name=title,
        source=TrendSource.HACKER_NEWS,
        volume=f"{points} points / {comments} comments",
        volume_numeric=points * 10 + comments,
        link=_hacker_news_link(hit),
        country="global",
        extra={"points": points, "comments": comments},
    )


def _hacker_news_trends_from_payload(payload: dict) -> list[RawTrend]:
    trends: list[RawTrend] = []
    for hit in payload.get("hits") or []:
        trend = _hacker_news_trend_from_hit(hit)
        if trend is not None:
            trends.append(trend)
    return trends


async def _async_fetch_hacker_news(
    session: httpx.AsyncClient,
    limit: int = 20,
) -> list[RawTrend]:
    """Hacker News 프론트페이지에서 트렌드 추출 (Algolia 공개 API)."""
    try:
        payload = await _hacker_news_payload(session, limit)
    except (httpx.HTTPError, ValueError) as exc:
        log.warning(f"Hacker News 수집 실패: {type(exc).__name__}: {exc}")
        return []

    trends = _hacker_news_trends_from_payload(payload)
    log.info(f"Hacker News 수집 완료: {len(trends)}개")
    return trends


def fetch_hacker_news(limit: int = 20) -> list[RawTrend]:
    """Hacker News 수집 (동기 호환 래퍼)."""
    return run_async(_async_fetch_hacker_news_standalone(limit))


async def _async_fetch_hacker_news_standalone(limit: int = 20) -> list[RawTrend]:
    async with httpx.AsyncClient() as session:
        return await _async_fetch_hacker_news(session, limit)


# ══════════════════════════════════════════════════════
#  Source 5: Reddit /r/popular (무인증 공개 JSON, primary 트렌드)
# ══════════════════════════════════════════════════════
#  collectors/reddit.py 의 키워드별 enricher 와 다른 역할 — 여기서는
#  글로벌 인기 게시물을 trend candidate 로 수집한다.

_REDDIT_POPULAR_URL = "https://www.reddit.com/r/popular.json?limit={limit}&t=day"


def _reddit_popular_url(limit: int) -> str:
    return _REDDIT_POPULAR_URL.format(limit=limit)


def _reddit_popular_headers() -> dict[str, str]:
    return {"User-Agent": "GetDayTrends/2.4 (+mailto:biojuho@gmail.com)"}


async def _reddit_popular_payload(session: httpx.AsyncClient, limit: int) -> dict | None:
    try:
        resp = await session.get(_reddit_popular_url(limit), headers=_reddit_popular_headers(), timeout=_SHORT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning(f"Reddit /r/popular collection failed: {type(exc).__name__}: {exc}")
        return None


def _reddit_popular_children(payload: dict | None) -> list:
    if not payload:
        return []
    return (payload.get("data") or {}).get("children") or []


def _reddit_post_data(child: dict | None) -> dict:
    return (child or {}).get("data") or {}


def _reddit_post_is_candidate(data: dict) -> bool:
    title = (data.get("title") or "").strip()
    return bool(title and len(title) >= 4 and not data.get("over_18") and not data.get("stickied"))


def _reddit_post_link(data: dict) -> str:
    permalink = data.get("permalink") or ""
    if permalink and not permalink.startswith("http"):
        return f"https://www.reddit.com{permalink}"
    return permalink or (data.get("url") or "")


def _reddit_post_to_raw_trend(data: dict) -> RawTrend:
    title = (data.get("title") or "").strip()
    ups = int(data.get("ups") or 0)
    comments = int(data.get("num_comments") or 0)
    subreddit = (data.get("subreddit_name_prefixed") or "").strip()
    return RawTrend(
        name=title,
        source=TrendSource.REDDIT,
        volume=f"{ups} ups / {comments} comments",
        volume_numeric=ups + comments * 5,
        link=_reddit_post_link(data),
        country="global",
        extra={
            "ups": ups,
            "comments": comments,
            "subreddit": subreddit,
        },
    )


def _parse_reddit_popular_trends(payload: dict | None) -> list[RawTrend]:
    trends: list[RawTrend] = []
    for child in _reddit_popular_children(payload):
        data = _reddit_post_data(child)
        if _reddit_post_is_candidate(data):
            trends.append(_reddit_post_to_raw_trend(data))
    return trends


async def _async_fetch_reddit_popular(
    session: httpx.AsyncClient,
    limit: int = 20,
) -> list[RawTrend]:
    """Fetch trend candidates from Reddit /r/popular."""
    trends = _parse_reddit_popular_trends(await _reddit_popular_payload(session, limit))
    log.info(f"Reddit /r/popular collection complete: {len(trends)}")
    return trends


def fetch_reddit_popular(limit: int = 20) -> list[RawTrend]:
    """Reddit /r/popular 수집 (동기 호환 래퍼)."""
    return run_async(_async_fetch_reddit_popular_standalone(limit))


async def _async_fetch_reddit_popular_standalone(limit: int = 20) -> list[RawTrend]:
    async with httpx.AsyncClient() as session:
        return await _async_fetch_reddit_popular(session, limit)


# ══════════════════════════════════════════════════════
#  Merge & Deduplicate Trends
# ══════════════════════════════════════════════════════


def _merge_trends(
    primary: list[RawTrend],
    secondary: list[RawTrend],
    limit: int,
) -> list[RawTrend]:
    """Merge primary and secondary trends, preserving primary priority."""
    merged, added_from_secondary = _merge_exact_trend_names(primary, secondary)
    if added_from_secondary:
        log.info(f"Google Trends added {added_from_secondary} supplemental trends")
    return _dedupe_semantic_trends(merged)[:limit]


def _merge_exact_trend_names(primary: list[RawTrend], secondary: list[RawTrend]) -> tuple[list[RawTrend], int]:
    seen: dict[str, RawTrend] = {}
    for trend in primary:
        seen.setdefault(_trend_name_key(trend), trend)

    added_from_secondary = 0
    for trend in secondary:
        key = _trend_name_key(trend)
        if key not in seen:
            seen[key] = trend
            added_from_secondary += 1
    return list(seen.values()), added_from_secondary


def _trend_name_key(trend: RawTrend) -> str:
    return trend.name.lower().strip()


def _dedupe_semantic_trends(trends: list[RawTrend]) -> list[RawTrend]:
    if len(trends) <= 1:
        return trends
    try:
        from shared.embeddings import deduplicate_texts

        unique_indices = deduplicate_texts([trend.name for trend in trends], threshold=0.82)
    except Exception as exc:
        log.debug(f"[semantic merge] embedding dedupe unavailable: {exc}")
        return trends

    removed = len(trends) - len(unique_indices)
    if removed:
        log.info(f"[semantic merge] removed {removed} duplicate trends -> {len(unique_indices)}")
    return [trends[index] for index in unique_indices]
