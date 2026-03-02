"""
getdaytrends v2.2 - Multi-Source Trend Collection
getdaytrends.com + Google Trends RSS + Twitter API + Reddit + Google News RSS.
병렬 수집 지원 (ThreadPoolExecutor).
"""

import json
import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed

import requests
from bs4 import BeautifulSoup

from config import AppConfig
from models import MultiSourceContext, RawTrend, TrendSource

log = logging.getLogger(__name__)


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


def fetch_getdaytrends(country_slug: str, limit: int = 50) -> list[RawTrend]:
    """
    getdaytrends.com에서 트렌드 수집 (볼륨 + 링크 포함).
    """
    base_url = "https://getdaytrends.com"
    url = f"{base_url}/{country_slug}/" if country_slug else f"{base_url}/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

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

        log.info(f"getdaytrends.com 수집 완료: {len(trends)}개 ({country_slug or 'global'})")
        return trends

    except Exception as e:
        log.error(f"getdaytrends.com 수집 실패: {e}")
        return _fallback_trends()


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


def fetch_google_trends_rss(country_slug: str, limit: int = 20) -> list[RawTrend]:
    """
    Google Trends RSS에서 실시간 트렌딩 토픽 수집.
    URL: https://trends.google.com/trending/rss?geo=KR
    API 키 불필요, 시간당 업데이트.
    한국 대상일 때 한글/영어 외 언어 필터링.
    """
    geo = _GEO_MAP.get(country_slug, "KR") if country_slug else "KR"
    url = f"https://trends.google.com/trending/rss?geo={geo}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; TrendBot/2.2)"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read()

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

            # 관련 뉴스 헤드라인 (extra 필드에 저장)
            news_items = []
            for news_item in item.findall("ht:news_item", ns)[:2]:
                news_title = news_item.find("ht:news_item_title", ns)
                if news_title is not None and news_title.text:
                    news_items.append(news_title.text.strip())

            trends.append(RawTrend(
                name=name,
                source=TrendSource.GOOGLE_TRENDS,
                volume=volume_text,
                volume_numeric=_parse_volume_text(volume_text.replace("+", "").replace(",", "")),
                link=link,
                country=country_slug or "global",
                extra={"news_headlines": news_items},
            ))

            if len(trends) >= limit:
                break

        log.info(f"Google Trends RSS 수집 완료: {len(trends)}개 ({geo})")
        return trends

    except Exception as e:
        log.warning(f"Google Trends RSS 수집 실패: {e}")
        return []


# ══════════════════════════════════════════════════════
#  Source 3: X (Twitter) API v2
# ══════════════════════════════════════════════════════

def fetch_twitter_trends(keyword: str, bearer_token: str = "") -> str:
    """
    X API v2 최신 트윗 검색 (인게이지먼트 메트릭 포함).
    """
    if not bearer_token:
        return f"[X API 미설정] {keyword} 관련 실시간 데이터 없음"

    encoded_query = urllib.parse.quote(f"{keyword} -is:retweet lang:ko OR lang:en")
    url = (
        f"https://api.twitter.com/2/tweets/search/recent"
        f"?query={encoded_query}&max_results=10"
        f"&tweet.fields=public_metrics,created_at"
    )
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "User-Agent": "GetDayTrends/2.2",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))

        if "data" not in data:
            return "최근 관련 트윗 없음"

        tweets = data["data"]
        for t in tweets:
            metrics = t.get("public_metrics", {})
            t["_eng"] = metrics.get("like_count", 0) + metrics.get("retweet_count", 0) * 2
        tweets.sort(key=lambda t: t["_eng"], reverse=True)

        summaries = []
        for t in tweets[:5]:
            metrics = t.get("public_metrics", {})
            eng = f"[{metrics.get('like_count', 0)}L/{metrics.get('retweet_count', 0)}RT]"
            text = t["text"].replace("\n", " ")[:150]
            summaries.append(f"{eng} {text}")
        return "\n".join(summaries)

    except Exception as e:
        log.debug(f"Twitter API 오류 ({keyword}): {e}")
        return f"[X API 오류] {keyword} 트렌드 감지 실패"


# ══════════════════════════════════════════════════════
#  Source 4: Reddit (Public JSON API)
# ══════════════════════════════════════════════════════

def fetch_reddit_trends(keyword: str) -> str:
    """Reddit 핫 포스트 수집."""
    encoded_query = urllib.parse.quote(keyword)
    url = f"https://www.reddit.com/search.json?q={encoded_query}&sort=hot&limit=5&t=day"
    headers = {"User-Agent": "GetDayTrends/2.2"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))

        posts = []
        for item in data.get("data", {}).get("children", []):
            d = item["data"]
            posts.append(f"[{d.get('score', 0)}pts] {d['title']}")

        return "\n".join(posts) if posts else "관련 Reddit 게시물 없음"

    except Exception as e:
        log.debug(f"Reddit API 오류 ({keyword}): {e}")
        return f"[Reddit 접근 제한] {keyword} 데이터 없음"


# ══════════════════════════════════════════════════════
#  Source 5: Google News RSS (컨텍스트용)
# ══════════════════════════════════════════════════════

def fetch_google_news_trends(keyword: str) -> str:
    """Google News RSS 기반 헤드라인 수집."""
    encoded_topic = urllib.parse.quote(keyword)
    insights = []

    for hl, gl, ceid in [("ko", "KR", "KR:ko"), ("en-US", "US", "US:en")]:
        url = f"https://news.google.com/rss/search?q={encoded_topic}&hl={hl}&gl={gl}&ceid={ceid}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                root = ET.fromstring(response.read())
            for item in root.findall(".//item")[:3]:
                title = item.find("title")
                if title is not None and title.text:
                    insights.append(title.text)
        except Exception:
            continue

    return " | ".join(insights) if insights else "관련 뉴스 없음"


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
    동일 키워드(대소문자 무시)는 primary 쪽으로 병합.
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

    merged = list(seen.values())[:limit]
    return merged


# ══════════════════════════════════════════════════════
#  Orchestrator
# ══════════════════════════════════════════════════════

def collect_trends(
    config: AppConfig,
    conn=None,
) -> tuple[list[RawTrend], dict[str, MultiSourceContext]]:
    """
    전체 수집 파이프라인:
    1. getdaytrends.com + Google Trends RSS 병렬 수집
    2. 최근 N시간 처리된 중복 키워드 제거
    3. 각 트렌드에 대해 Twitter, Reddit, Google News 컨텍스트 수집
    """
    from db import get_recently_processed_keywords

    country_slug = config.resolve_country_slug()
    fetch_size = config.limit + 10  # 여유 있게 수집

    # ── 1단계: 두 소스 병렬 수집 ──────────────────────
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_gdt = ex.submit(fetch_getdaytrends, country_slug, fetch_size)
        f_gtr = ex.submit(fetch_google_trends_rss, country_slug, fetch_size)
        gdt_trends = f_gdt.result()
        gtr_trends = f_gtr.result()

    # ── 2단계: 병합 (getdaytrends 우선) ───────────────
    all_trends = _merge_trends(gdt_trends, gtr_trends, limit=fetch_size)
    log.info(f"병합 완료: getdaytrends={len(gdt_trends)}, google_trends={len(gtr_trends)} → {len(all_trends)}개")

    # ── 3단계: 중복 필터 ──────────────────────────────
    if conn is not None:
        seen = get_recently_processed_keywords(conn, hours=config.dedupe_window_hours)
        fresh = [t for t in all_trends if t.name not in seen]
        if fresh:
            log.info(f"중복 제거: {len(all_trends)}개 → {len(fresh)}개 (제외: {len(all_trends) - len(fresh)}개)")
            all_trends = fresh
        else:
            log.warning(f"모든 트렌드가 {config.dedupe_window_hours}시간 내 처리됨 → 중복 허용")

    raw_trends = all_trends[: config.limit]

    # ── 4단계: 컨텍스트 수집 (Google Trends 내장 헤드라인 활용) ──
    contexts = _collect_contexts_parallel(raw_trends, config)

    log.info(f"멀티소스 수집 완료: {len(raw_trends)}개 트렌드, {len(contexts)}개 컨텍스트")
    return raw_trends, contexts


# ══════════════════════════════════════════════════════
#  Parallel Context Collection
# ══════════════════════════════════════════════════════

def _fetch_single_source(
    keyword: str,
    source_name: str,
    bearer_token: str = "",
    extra_news: str = "",
) -> tuple[str, str, str]:
    """단일 소스 수집. (keyword, source_name, result_text) 반환."""
    try:
        if source_name == "twitter":
            return keyword, source_name, fetch_twitter_trends(keyword, bearer_token)
        elif source_name == "reddit":
            return keyword, source_name, fetch_reddit_trends(keyword)
        else:
            result = fetch_google_news_trends(keyword)
            # Google Trends RSS에서 가져온 헤드라인이 있으면 앞에 붙임
            if extra_news:
                result = f"{extra_news} | {result}" if result != "관련 뉴스 없음" else extra_news
            return keyword, source_name, result
    except Exception as e:
        log.warning(f"소스 수집 실패 ({source_name}/{keyword}): {e}")
        return keyword, source_name, f"[{source_name} 오류] {keyword}"


def _collect_contexts_parallel(
    raw_trends: list[RawTrend],
    config: AppConfig,
) -> dict[str, MultiSourceContext]:
    """ThreadPoolExecutor로 전체 트렌드 × 3소스 병렬 수집."""
    sources = ["twitter", "reddit", "news"]
    results: dict[str, dict[str, str]] = {t.name: {} for t in raw_trends}

    # Google Trends RSS에서 가져온 내장 헤드라인 미리 추출
    extra_news_map: dict[str, str] = {}
    for t in raw_trends:
        if t.source == TrendSource.GOOGLE_TRENDS:
            headlines = t.extra.get("news_headlines", [])
            if headlines:
                extra_news_map[t.name] = " | ".join(headlines)

    with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
        futures: dict = {}
        for trend in raw_trends:
            extra_news = extra_news_map.get(trend.name, "")
            for source in sources:
                future = executor.submit(
                    _fetch_single_source,
                    trend.name,
                    source,
                    config.twitter_bearer_token,
                    extra_news if source == "news" else "",
                )
                futures[future] = (trend.name, source)

        for future in as_completed(futures):
            try:
                keyword, source, text = future.result(timeout=15)
                results[keyword][source] = text
                log.debug(f"  병렬 수집 완료: '{keyword}' [{source}]")
            except FuturesTimeoutError:
                keyword, source = futures[future]
                results[keyword][source] = f"[{source} 타임아웃]"
                log.warning(f"  병렬 수집 타임아웃: '{keyword}' [{source}]")
            except Exception as e:
                keyword, source = futures[future]
                results[keyword][source] = f"[{source} 오류]"
                log.warning(f"  병렬 수집 오류 ({source}/{keyword}): {e}")

    contexts: dict[str, MultiSourceContext] = {}
    for keyword, source_data in results.items():
        contexts[keyword] = MultiSourceContext(
            twitter_insight=source_data.get("twitter", ""),
            reddit_insight=source_data.get("reddit", ""),
            news_insight=source_data.get("news", ""),
        )

    return contexts
