"""
getdaytrends v2.4 - Multi-Source Trend Collection (asyncio)
getdaytrends.com + Google Trends RSS + Twitter API + Reddit + Google News RSS.
비동기 병렬 수집 지원 (aiohttp + asyncio.gather).
"""

import asyncio
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET

import httpx

from config import AppConfig
from models import MultiSourceContext, RawTrend, TrendSource
from utils import run_async

from loguru import logger as log

# Phase 3: getdaytrends.com 수집 결과 1시간 메모리 캐시
# { country_slug: (fetched_at_unix, [RawTrend, ...]) }
_FETCH_CACHE: dict[str, tuple[float, list[RawTrend]]] = {}
_FETCH_CACHE_TTL = 3600  # 1시간 (초)

# 기본 타임아웃 설정 (초) [Phase 2 최적화: 단축]
_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=6.0)   # 기존 20/8
_SHORT_TIMEOUT = httpx.Timeout(8.0, connect=4.0)      # 기존 12/5


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
    from datetime import datetime as _dt, timezone
    dt = _parse_rss_date(date_str)
    if not dt:
        return ""
    now = _dt.now(timezone.utc)
    if dt.tzinfo is None:
        from datetime import timezone as _tz
        dt = dt.replace(tzinfo=_tz.utc)
    delta = now - dt
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{max(int(delta.total_seconds() / 60), 1)}분 전"
    elif hours < 24:
        return f"{int(hours)}시간 전"
    else:
        return f"{int(hours / 24)}일 전"

_COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
}


# ══════════════════════════════════════════════════════
#  Source 1: getdaytrends.com
# ══════════════════════════════════════════════════════

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


async def _async_fetch_getdaytrends(
    session: httpx.AsyncClient, country_slug: str, limit: int = 50
) -> list[RawTrend]:
    """getdaytrends.com에서 트렌드 수집 (비동기)."""
    from bs4 import BeautifulSoup

    base_url = "https://getdaytrends.com"
    url = f"{base_url}/{country_slug}/" if country_slug else f"{base_url}/"

    # Phase 3: 캐시 히트 확인 (1시간 TTL)
    cache_key = country_slug or "global"
    cached = _FETCH_CACHE.get(cache_key)
    if cached:
        cached_at, cached_trends = cached
        if time.time() - cached_at < _FETCH_CACHE_TTL:
            log.info(f"[수집 캐시] getdaytrends.com 재사용: {len(cached_trends)}개 ({cache_key}, {int(time.time() - cached_at)}초 전)")
            return cached_trends[:limit]

    try:
        resp = await session.get(url, headers=_COMMON_HEADERS, timeout=_DEFAULT_TIMEOUT)
        resp.raise_for_status()
        html = resp.text

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        trends = []
        rows = soup.select("table.trends tbody tr")
        if not rows:
            rows = soup.select("table tr")

        for row in rows:
            name_el = row.select_one(".main a") or row.select_one("a")
            if not name_el:
                continue

            name = name_el.get_text(strip=True).lstrip("#").strip()
            if not name:
                continue

            volume_el = row.select_one(".desc")
            volume_text = volume_el.get_text(strip=True) if volume_el else "N/A"

            href = name_el.get("href", "")
            link = f"{base_url}{href}" if href and not href.startswith("http") else href

            trends.append(RawTrend(
                name=name,
                source=TrendSource.GETDAYTRENDS,
                volume=volume_text,
                volume_numeric=_parse_volume_text(volume_text),
                link=link,
                country=country_slug or "global",
            ))

            if len(trends) >= limit:
                break

        if not trends:
            log.warning("getdaytrends.com 파싱 실패. 대체 트렌드 사용.")
            return _fallback_trends()

        # Phase 3: 캐시 저장
        _FETCH_CACHE[cache_key] = (time.time(), trends)
        log.info(f"getdaytrends.com 수집 완료: {len(trends)}개 ({country_slug or 'global'})")
        return trends

    except Exception as e:
        log.error(f"getdaytrends.com 수집 실패: {e}")
        return _fallback_trends()


def fetch_getdaytrends(country_slug: str, limit: int = 50) -> list[RawTrend]:
    """getdaytrends.com에서 트렌드 수집 (동기 호환 래퍼)."""
    return run_async(_async_fetch_getdaytrends_standalone(country_slug, limit))


async def _async_fetch_getdaytrends_standalone(
    country_slug: str, limit: int = 50
) -> list[RawTrend]:
    """독립 세션으로 getdaytrends 수집 (단독 호출용)."""
    async with httpx.AsyncClient() as session:
        return await _async_fetch_getdaytrends(session, country_slug, limit)


def _fallback_trends() -> list[RawTrend]:
    """스크래핑 실패 시 대체 주제."""
    fallbacks = ["주말 계획", "점심 메뉴", "날씨", "커피", "퇴근"]
    return [
        RawTrend(name=t, source=TrendSource.GETDAYTRENDS)
        for t in fallbacks
    ]


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
    has_hangul = any('\uAC00' <= c <= '\uD7A3' or '\u1100' <= c <= '\u11FF' for c in name)
    # 영어 혹은 한글이면 허용
    is_ascii = all(ord(c) < 128 for c in name.replace(" ", ""))
    return has_hangul or is_ascii


async def _async_fetch_google_trends_rss(
    session: httpx.AsyncClient, country_slug: str, limit: int = 20
) -> list[RawTrend]:
    """Google Trends RSS에서 실시간 트렌딩 토픽 수집 (비동기)."""
    geo = _GEO_MAP.get(country_slug, "KR") if country_slug else "KR"
    url = f"https://trends.google.com/trending/rss?geo={geo}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; TrendBot/2.3)"}

    try:
        resp = await session.get(url, headers=headers, timeout=_SHORT_TIMEOUT)
        raw = resp.read()

        root = ET.fromstring(raw)
        ns = {"ht": "https://trends.google.com/trending/rss"}

        trends = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            if title_el is None or not title_el.text:
                continue

            name = title_el.text.strip()

            # 한국 대상이면 비한국어 필터링
            if not _is_korean_trend(name, country_slug):
                log.debug(f"  [Google Trends] 비한국어 필터: '{name}'")
                continue

            # 트래픽 볼륨 (ht:approx_traffic)
            traffic_el = item.find("ht:approx_traffic", ns)
            volume_text = traffic_el.text.strip() if traffic_el is not None else "N/A"

            # 뉴스 링크
            link_el = item.find("link")
            link = link_el.text.strip() if link_el is not None and link_el.text else ""

            # [가능 시] 발행 시점 파싱
            news_items = []
            for news_item in item.findall("ht:news_item", ns)[:2]:
                news_title = news_item.find("ht:news_item_title", ns)
                if news_title is not None and news_title.text:
                    news_items.append(news_title.text.strip())

            # [v6.1] pubDate 파싱
            pub_date_el = item.find("pubDate")
            published_at = _parse_rss_date(
                pub_date_el.text if pub_date_el is not None else None
            )

            trends.append(RawTrend(
                name=name,
                source=TrendSource.GOOGLE_TRENDS,
                volume=volume_text,
                volume_numeric=_parse_volume_text(volume_text.replace("+", "").replace(",", "")),
                link=link,
                country=country_slug or "global",
                extra={"news_headlines": news_items},
                published_at=published_at,
            ))

            if len(trends) >= limit:
                break

        log.info(f"Google Trends RSS 수집 완료: {len(trends)}개 ({geo})")
        return trends

    except Exception as e:
        log.warning(f"Google Trends RSS 수집 실패: {e}")
        return []


def fetch_google_trends_rss(country_slug: str, limit: int = 20) -> list[RawTrend]:
    """Google Trends RSS 수집 (동기 호환 래퍼)."""
    return run_async(_async_fetch_google_trends_rss_standalone(country_slug, limit))


async def _async_fetch_google_trends_rss_standalone(
    country_slug: str, limit: int = 20
) -> list[RawTrend]:
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
#  Source 6: YouTube Trending RSS (무료, API키 불필요)
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
    """YouTube 인기 동영상 RSS에서 트렌드 키워드 추출 (비동기). [v9.1] 적응형 타임아웃 & 백오프 적용"""
    country_code = _YOUTUBE_GEO_MAP.get(country_slug, "KR")
    # YouTube RSS trending feed (chart=mostviewed 폐기 대응)
    url = f"https://www.youtube.com/feeds/videos.xml?gl={country_code}&hl=ko"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; TrendBot/4.1)"}

    raw = None
    for attempt in range(1, 4):
        try:
            resp = await session.get(url, headers=headers, timeout=_SHORT_TIMEOUT)
            resp.raise_for_status()
            raw = resp.read()
            break
        except Exception as e:
            if attempt == 3:
                log.debug(f"YouTube Trending 수집 최종 실패 (3회 초과): {e}")
                return []
            backoff = 2 ** attempt
            log.warning(f"YouTube API 에러({e}), {backoff}초 후 재시도 ({attempt}/3)")
            await asyncio.sleep(backoff)
            
    if not isinstance(raw, bytes):
        return []

    try:
        root = ET.fromstring(raw)
        # YouTube Atom feed namespace
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "media": "http://search.yahoo.com/mrss/",
            "yt": "http://www.youtube.com/xml/schemas/2015",
        }

        trends = []
        for entry in root.findall("atom:entry", ns)[:limit]:
            title_el = entry.find("atom:title", ns)
            if title_el is None or not title_el.text:
                continue
            name = title_el.text.strip()
            if len(name) < 2:
                continue

            # 동영상 링크
            link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""

            # 조회 수 (yt:statistics viewCount)
            stats_el = entry.find("yt:statistics", ns)
            view_count = 0
            if stats_el is not None:
                try:
                    view_count = int(stats_el.get("viewCount", "0"))
                except ValueError:
                    pass

            trends.append(RawTrend(
                name=name,
                source=TrendSource.YOUTUBE,
                volume=f"{view_count:,} views" if view_count else "N/A",
                volume_numeric=view_count,
                link=link,
                country=country_slug or "korea",
            ))

        log.info(f"YouTube Trending 수집 완료: {len(trends)}개 ({country_code})")
        return trends

    except Exception as e:
        log.debug(f"YouTube Trending 수집 실패 (무시): {e}")
        return []


def fetch_youtube_trending(country_slug: str = "korea", limit: int = 10) -> list[RawTrend]:
    """YouTube 인기 동영상 RSS 수집 (동기 호환 래퍼)."""
    return run_async(_async_fetch_youtube_trending_standalone(country_slug, limit))


async def _async_fetch_youtube_trending_standalone(
    country_slug: str = "korea", limit: int = 10
) -> list[RawTrend]:
    """독립 세션으로 YouTube Trending 수집 (단독 호출용)."""
    async with httpx.AsyncClient() as session:
        return await _async_fetch_youtube_trending(session, country_slug, limit)


# ══════════════════════════════════════════════════════
#  Merge & Deduplicate Trends
# ══════════════════════════════════════════════════════

def _merge_trends(
    primary: list[RawTrend],
    secondary: list[RawTrend],
    limit: int,
) -> list[RawTrend]:
    """
    두 소스 트렌드 병합 + 중복 제거.
    primary(getdaytrends) 우선, secondary(Google Trends) 보충.
    [v14.1] 문자열 정확 매칭 + 임베딩 의미적 중복 감지.
    """
    seen: dict[str, RawTrend] = {}

    for t in primary:
        key = t.name.lower().strip()
        if key not in seen:
            seen[key] = t

    added_from_secondary = 0
    for t in secondary:
        key = t.name.lower().strip()
        if key not in seen:
            seen[key] = t
            added_from_secondary += 1

    if added_from_secondary:
        log.info(f"Google Trends에서 {added_from_secondary}개 추가 트렌드 병합")

    merged = list(seen.values())

    # [v14.1] 임베딩 기반 소스 간 의미적 중복 제거
    if len(merged) > 1:
        try:
            from shared.embeddings import deduplicate_texts
            names = [t.name for t in merged]
            unique_indices = deduplicate_texts(names, threshold=0.82)
            removed = len(merged) - len(unique_indices)
            if removed:
                merged = [merged[i] for i in unique_indices]
                log.info(f"[의미적 병합] 소스 간 중복 {removed}개 제거 → {len(merged)}개")
        except Exception as _e:
            log.debug(f"[의미적 병합] 임베딩 사용 불가 (무시): {_e}")

    return merged[:limit]


# ══════════════════════════════════════════════════════
#  Async Orchestrator
# ══════════════════════════════════════════════════════

async def _async_collect_trends(
    config: AppConfig,
    conn=None,
) -> tuple[list[RawTrend], dict[str, MultiSourceContext]]:
    """
    전체 수집 파이프라인 (비동기):
    1. getdaytrends.com + Google Trends RSS 병렬 수집
    2. 최근 N시간 처리된 중복 키워드 제거
    3. 각 트렌드에 대해 Twitter, Reddit, Google News 컨텍스트 병렬 수집
    """
    from db import get_recently_processed_keywords

    country_slug = config.resolve_country_slug()
    fetch_size = config.limit + 10  # 여유 있게 수집

    # ── O1-1: 단일 httpx 세션 + 연결 풀 최적화 (aiohttp 잔재 제거) ──
    limits = httpx.Limits(
        max_connections=config.max_workers * 2,
        max_keepalive_connections=config.max_workers,
        keepalive_expiry=30,
    )
    async with httpx.AsyncClient(limits=limits) as session:
        # 1단계: 소스 병렬 수집 (YouTube 포함)
        fetch_tasks = [
            _async_fetch_getdaytrends(session, country_slug, fetch_size),
            _async_fetch_google_trends_rss(session, country_slug, fetch_size),
        ]

        fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        gdt_trends = fetch_results[0] if not isinstance(fetch_results[0], Exception) else []
        gtr_trends = fetch_results[1] if not isinstance(fetch_results[1], Exception) else []

        if isinstance(fetch_results[0], Exception):
            log.error(f"getdaytrends 수집 실패: {fetch_results[0]}")
        if isinstance(fetch_results[1], Exception):
            log.warning(f"Google Trends 수집 실패: {fetch_results[1]}")

        # [v9.1] 부분 성공(Partial Success) 허용 및 전체 실패 시 우회(Fallback) 아키텍처
        total_sources = 2
        success_sources = sum(1 for t_list in (gdt_trends, gtr_trends) if t_list)

        if success_sources == 0:
            log.error("[장애] 모든 트렌드 소스 수집 실패! Fallback 트렌드로 우회합니다.")
            gdt_trends = _fallback_trends()  # 실패 시 모의 트렌드 사용
        elif success_sources / total_sources < 0.5:
            log.warning(f"[부분 성공] 데이터 소스 수집 성공률 50% 미만 ({success_sources}/{total_sources}). 파이프라인 강행.")
        else:
            log.info(f"[부분 성공] 수집 성공: {success_sources}/{total_sources} 개 소스 가동 중.")

        # 소스 품질 기록 (v5.0)
        if getattr(config, "enable_source_quality_tracking", True) and conn is not None:
            from db import record_source_quality
            import time
            await record_source_quality(conn, "getdaytrends", bool(gdt_trends), 0, len(gdt_trends),
                                        min(len(gdt_trends) / max(fetch_size, 1), 1.0))
            await record_source_quality(conn, "google_trends", bool(gtr_trends), 0, len(gtr_trends),
                                        min(len(gtr_trends) / 20, 1.0))

        # 2단계: 병합 (getdaytrends → google_trends 순서 우선)
        all_trends = _merge_trends(gdt_trends, gtr_trends, limit=fetch_size)
        log.info(
            f"병합 완료: getdaytrends={len(gdt_trends)}, google_trends={len(gtr_trends)} "
            f"→ 총 {len(all_trends)}개"
        )

        # 3단계: 중복 필터 (유사도 기반)
        if conn is not None:
            try:
                seen = await get_recently_processed_keywords(conn, hours=config.dedupe_window_hours)
            except Exception as _e:
                log.warning(f"중복 필터 조회 실패 (무시): {_e}")
                seen = set()
            fresh = [t for t in all_trends if not _is_similar_keyword(t.name, seen)]
            if fresh:
                log.info(f"중복 제거: {len(all_trends)}개 → {len(fresh)}개 (제외: {len(all_trends) - len(fresh)}개)")
                all_trends = fresh
            else:
                log.warning(f"모든 트렌드가 {config.dedupe_window_hours}시간 내 처리됨 → 중복 허용")

        # [v14.1] 4단계 전 의미적 중복 제거 (임베딩 기반)
        if len(all_trends) > 1 and getattr(config, 'enable_embedding_clustering', True):
            try:
                from shared.embeddings import deduplicate_texts
                names = [t.name for t in all_trends]
                unique_indices = deduplicate_texts(
                    names,
                    threshold=getattr(config, 'embedding_cluster_threshold', 0.75),
                )
                removed = len(all_trends) - len(unique_indices)
                if removed:
                    all_trends = [all_trends[i] for i in unique_indices]
                    log.info(f"[수집 임베딩 중복] {removed}개 의미적 중복 제거 → {len(all_trends)}개")
            except Exception as _e:
                log.debug(f"[수집 임베딩 중복] 사용 불가: {_e}")

        raw_trends = all_trends[: config.limit]

        # 4단계: 기본 컨텍스트 (Google Trends RSS 헤드라인만)
        contexts: dict[str, MultiSourceContext] = {}
        for t in raw_trends:
            extra_news = ""
            if t.source == TrendSource.GOOGLE_TRENDS:
                extra_news = " | ".join(t.extra.get("news_headlines", []))
            elif t.source == TrendSource.YOUTUBE:
                # YouTube 트렌드는 타이틀을 뉴스 인사이트로 초기화
                extra_news = f"[YouTube 인기] {t.name}"
            contexts[t.name] = MultiSourceContext(news_insight=extra_news)

    log.info(f"멀티소스 수집 완료: {len(raw_trends)}개 트렌드 (기본 컨텍스트만 구성)")
    return raw_trends, contexts

# ══════════════════════════════════════════════════════
#  Sync Public API (하위 호환)
# ══════════════════════════════════════════════════════

def collect_trends(
    config: AppConfig,
    conn=None,
) -> tuple[list[RawTrend], dict[str, MultiSourceContext]]:
    """
    전체 수집 파이프라인 (동기 호환 공개 API).
    내부적으로 asyncio 비동기 파이프라인을 실행.
    """
    return run_async(_async_collect_trends(config, conn))


def collect_contexts(
    raw_trends: list[RawTrend],
    config: AppConfig,
    conn=None,
) -> dict[str, MultiSourceContext]:
    """
    Tiered Fetching용 심층 컨텍스트 수집 (동기 호환 공개 API).
    raw_trends: 컨텍스트를 수집할 트렌드 목록
    conn: 소스 품질 기록용 DB 컨넥션 (v5.0, 선택)
    """
    return run_async(_async_collect_contexts(raw_trends, config, conn=conn))



# -- backward-compat re-exports from context_collector --
from context_collector import (  # noqa: F401
    _async_collect_contexts,
    _async_fetch_google_news_trends,
    _async_fetch_google_trends_related,
    _async_fetch_reddit_trends,
    _async_fetch_twitter_trends,
    _async_fetch_google_suggest,
    _calc_quality_score,
    fetch_google_news_trends,
    fetch_reddit_trends,
    fetch_twitter_trends,
    post_to_x_async,
    post_to_x,
)
