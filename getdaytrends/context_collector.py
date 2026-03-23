"""
getdaytrends — Context Collector
Twitter/Reddit/Google News/Google Suggest 컨텍스트 수집.
scraper.py에서 분리됨.
"""

import asyncio
import time
import urllib.parse
import xml.etree.ElementTree as ET

import httpx

from config import AppConfig
from models import MultiSourceContext, RawTrend, TrendSource
from utils import run_async

from loguru import logger as log

# Timeout settings (from scraper)
_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=6.0)
_SHORT_TIMEOUT = httpx.Timeout(8.0, connect=4.0)

_COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
}

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
#  Source 3: X (Twitter) API v2
# ══════════════════════════════════════════════════════

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


async def _async_fetch_x_via_twikit_or_jina(
    session: httpx.AsyncClient, keyword: str
) -> str:
    """Twikit 우선 시도, 실패 시 Jina AI Reader 폴백."""
    # Phase 1: Twikit (비공식 API — 무료, 구조화된 데이터)
    try:
        from x_client import is_available, search_tweets_formatted
        if is_available():
            result = await search_tweets_formatted(keyword, count=10)
            if result and len(result) > 30:
                log.debug(f"[Twikit] '{keyword}' 트윗 수집 성공")
                return result
    except Exception as e:
        log.debug(f"[Twikit] '{keyword}' 수집 실패: {e}")

    # Phase 2: Jina AI Reader 폴백
    return await _async_fetch_x_via_twikit_or_jina(session, keyword)


async def _async_fetch_x_via_jina(
    session: httpx.AsyncClient, keyword: str
) -> str:
    """Jina AI Reader로 X 검색 결과 무료 스크래핑 (비동기)."""
    encoded = urllib.parse.quote(f"{keyword} lang:ko")
    jina_url = f"https://r.jina.ai/https://x.com/search?q={encoded}&f=live"
    headers = {
        "User-Agent": "GetDayTrends/2.3",
        "Accept": "text/plain",
    }
    try:
        resp = await session.get(jina_url, headers=headers, timeout=_SHORT_TIMEOUT)
        resp.raise_for_status()
        text = resp.text
        text = text.strip()
        # 의미 있는 내용만 추출 (첫 500자)
        if len(text) > 50:
            return text[:500]
        return f"[X 검색] {keyword} 관련 실시간 데이터 부족"
    except Exception as e:
        log.debug(f"Jina X 스크래핑 실패 ({keyword}): {e}")
        return f"[X 데이터 없음] {keyword}"


def _check_rate_limit(headers: "httpx.Headers") -> None:
    """X API 레이트 리밋 헤더 확인 후 경고 로그."""
    remaining = headers.get("x-rate-limit-remaining")
    limit = headers.get("x-rate-limit-limit")
    reset = headers.get("x-rate-limit-reset")
    if remaining is not None and limit is not None:
        try:
            if int(remaining) <= 3:
                reset_in = int(reset) - int(time.time()) if reset else "?"
                log.warning(
                    f"[X API] 레이트 리밋 임박: {remaining}/{limit} 남음, "
                    f"{reset_in}초 후 초기화"
                )
        except (ValueError, TypeError):
            pass


async def _async_fetch_twitter_trends(
    session: httpx.AsyncClient, keyword: str, bearer_token: str = ""
) -> str:
    """X API v2 최신 트윗 검색 (비동기). Bearer Token 미설정 시 Jina 폴백.

    Phase 4 강화:
    - 품질 필터: -is:retweet -is:quote -is:nullcast min_faves:3
    - max_results=25 (기존 10)
    - 레이트 리밋 헤더 모니터링
    - context_annotations로 카테고리 힌트 추출
    """
    if not bearer_token:
        return await _async_fetch_x_via_twikit_or_jina(session, keyword)

    # 품질 필터 강화: 리트윗/인용/스팸 제외, 좋아요 3개 이상
    query_str = (
        f"{keyword} -is:retweet -is:quote -is:nullcast "
        "lang:ko min_faves:3"
    )
    encoded_query = urllib.parse.quote(query_str)
    url = (
        "https://api.twitter.com/2/tweets/search/recent"
        f"?query={encoded_query}&max_results=25"
        "&tweet.fields=public_metrics,created_at,context_annotations"
        "&expansions=author_id"
    )
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "User-Agent": "GetDayTrends/2.4",
    }

    try:
        resp = await session.get(url, headers=headers, timeout=_SHORT_TIMEOUT)
        _check_rate_limit(resp.headers)

        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after", "60")
            log.warning(f"[X API] 레이트 리밋 초과. {retry_after}초 후 재시도 필요")
            return await _async_fetch_x_via_twikit_or_jina(session, keyword)

        if resp.status_code == 403:
            log.debug(f"[X API] 검색 권한 없음 (Basic 티어 미지원). Jina 폴백.")
            return await _async_fetch_x_via_twikit_or_jina(session, keyword)

        resp.raise_for_status()
        data = resp.json()

        if "data" not in data:
            log.debug(f"[X API] '{keyword}' 최근 트윗 없음")
            return "최근 관련 트윗 없음"

        tweets = data["data"]

        # 참여도 기반 정렬 (좋아요 + RT×2 + 인용×1.5)
        for t in tweets:
            m = t.get("public_metrics", {})
            t["_eng"] = (
                m.get("like_count", 0)
                + m.get("retweet_count", 0) * 2
                + m.get("quote_count", 0)
            )
        tweets.sort(key=lambda t: t["_eng"], reverse=True)

        summaries = []
        for t in tweets[:7]:
            m = t.get("public_metrics", {})
            eng = f"[{m.get('like_count', 0)}L/{m.get('retweet_count', 0)}RT]"
            text = t["text"].replace("\n", " ")[:200]
            # [v6.1] created_at 타임스탬프 주입 — LLM이 트윗 시점 파악 가능
            time_label = ""
            raw_ts = t.get("created_at", "")
            if raw_ts:
                try:
                    from datetime import datetime, timedelta, timezone
                    dt_utc = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                    dt_local = dt_utc.astimezone(timezone(timedelta(hours=9)))  # KST
                    time_label = dt_local.strftime("%m/%d %H:%M")
                except Exception:
                    pass
            prefix = f"[{time_label}] " if time_label else ""
            summaries.append(f"{prefix}{eng} {text}")

        return "\n".join(summaries)

    except httpx.HTTPStatusError as e:
        log.debug(f"Twitter API HTTP 오류 ({keyword}): {e.response.status_code} → Jina 폴백")
        return await _async_fetch_x_via_twikit_or_jina(session, keyword)
    except Exception as e:
        log.debug(f"Twitter API 오류 ({keyword}): {e}")
        return f"[X API 오류] {keyword} 트렌드 감지 실패"


def fetch_twitter_trends(keyword: str, bearer_token: str = "") -> str:
    """X API v2 최신 트윗 검색 (동기 호환 래퍼)."""
    return run_async(_async_fetch_twitter_trends_standalone(keyword, bearer_token))


async def _async_fetch_twitter_trends_standalone(
    keyword: str, bearer_token: str = ""
) -> str:
    """독립 세션으로 X 트렌드 수집 (단독 호출용)."""
    async with httpx.AsyncClient() as session:
        return await _async_fetch_twitter_trends(session, keyword, bearer_token)


# ── X 포스팅 (OAuth 2.0 유저 컨텍스트) ──────────────────

async def post_to_x_async(
    content: str,
    access_token: str,
    session: httpx.AsyncClient | None = None,
) -> dict:
    """
    X API v2로 트윗 게시 (OAuth 2.0 유저 컨텍스트).
    access_token: OAuth 2.0 PKCE 플로우로 획득한 유저 토큰.

    반환값:
        {"ok": True, "tweet_id": "123..."}  성공 시
        {"ok": False, "error": "...", "code": 403}  실패 시
    """
    if not access_token:
        return {"ok": False, "error": "X access_token 미설정", "code": 0}

    if len(content) > 280:
        return {"ok": False, "error": f"트윗 280자 초과 ({len(content)}자)", "code": 0}

    url = "https://api.twitter.com/2/tweets"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "GetDayTrends/2.4",
    }
    payload = {"text": content}

    async def _do_post(sess: httpx.AsyncClient) -> dict:
        try:
            resp = await sess.post(
                url, headers=headers, json=payload, timeout=_SHORT_TIMEOUT
            )
            body = resp.json()
            if resp.status_code in (200, 201):
                tweet_id = body.get("data", {}).get("id", "")
                log.info(f"[X 게시] 완료 (id={tweet_id}): {content[:50]}...")
                return {"ok": True, "tweet_id": tweet_id}
            else:
                err = body.get("detail", body.get("title", str(body)))
                log.warning(f"[X 게시] 실패 {resp.status_code}: {err}")
                return {"ok": False, "error": err, "code": resp.status_code}
        except Exception as e:
            log.error(f"[X 게시] 예외: {e}")
            return {"ok": False, "error": str(e), "code": 0}

    if session is not None:
        return await _do_post(session)
    async with httpx.AsyncClient() as _sess:
        return await _do_post(_sess)


def post_to_x(content: str, access_token: str) -> dict:
    """X 트윗 게시 (동기 래퍼)."""
    return run_async(post_to_x_async(content, access_token))

# ══════════════════════════════════════════════════════
#  Source 4: Reddit (Public JSON API)
# ══════════════════════════════════════════════════════

async def _async_fetch_reddit_trends(
    session: httpx.AsyncClient, keyword: str
) -> str:
    """Reddit 핫 포스트 수집 (비동기)."""
    encoded_query = urllib.parse.quote(keyword)
    url = f"https://www.reddit.com/search.json?q={encoded_query}&sort=hot&limit=5&t=day"
    headers = {"User-Agent": "GetDayTrends/2.3"}

    try:
        resp = await session.get(url, headers=headers, timeout=_SHORT_TIMEOUT)
        data = resp.json()

        posts = []
        for item in data.get("data", {}).get("children", []):
            d = item["data"]
            posts.append(f"[{d.get('score', 0)}pts] {d['title']}")

        return "\n".join(posts) if posts else "관련 Reddit 게시물 없음"

    except Exception as e:
        log.debug(f"Reddit API 오류 ({keyword}): {e}")
        return f"[Reddit 접근 제한] {keyword} 데이터 없음"


def fetch_reddit_trends(keyword: str) -> str:
    """Reddit 핫 포스트 수집 (동기 호환 래퍼)."""
    return run_async(_async_fetch_reddit_trends_standalone(keyword))


async def _async_fetch_reddit_trends_standalone(keyword: str) -> str:
    """독립 세션으로 Reddit 수집 (단독 호출용)."""
    async with httpx.AsyncClient() as session:
        return await _async_fetch_reddit_trends(session, keyword)

# ══════════════════════════════════════════════════════
#  Source 5: Google News RSS (컨텍스트용)
# ══════════════════════════════════════════════════════

async def _async_fetch_google_news_trends(
    session: httpx.AsyncClient, keyword: str
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
                timeout=_SHORT_TIMEOUT,
            )
            raw = resp.read()
            root = ET.fromstring(raw)
            for item in root.findall(".//item")[:5]:  # 3 → 5 헤드라인
                title = item.find("title")
                pub_date = item.find("pubDate")
                if title is not None and title.text:
                    age_str = _format_news_age(pub_date.text if pub_date is not None else None)
                    # [v10.0] 발행 시각을 날짜+시간으로 포함 (LLM이 시점 파악 가능)
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

def _calc_quality_score(text: str) -> float:
    """
    컨텍스트 텍스트 기반 품질 점수 (0.0~1.0).
    '없음', '오류', '실패', '제한' 포함 → 0.0 / 내용 충분 → 1.0
    """
    if not text or len(text) < 20:
        return 0.0
    low = text.lower()
    if any(kw in low for kw in ["없음", "오류", "실패", "제한", "error", "none", "fail"]):
        return 0.0
    if len(text) >= 200:
        return 1.0
    return round(len(text) / 200, 2)  # 0.1 ~ 0.99


def fetch_google_news_trends(keyword: str) -> str:
    """Google News RSS 수집 (동기 호환 래퍼)."""
    return run_async(_async_fetch_google_news_trends_standalone(keyword))


async def _async_fetch_google_news_trends_standalone(keyword: str) -> str:
    """독립 세션으로 Google News 수집 (단독 호출용)."""
    async with httpx.AsyncClient() as session:
        return await _async_fetch_google_news_trends(session, keyword)

async def _async_fetch_single_source(
    session: httpx.AsyncClient,
    keyword: str,
    source_name: str,
    bearer_token: str = "",
    extra_news: str = "",
    conn=None,
    timeout_override: float | None = None,
) -> tuple[str, str, str]:
    """단일 소스 수집 (비동기). 소스 품질 메트릭 기록 포함.
    
    timeout_override: B-3 동적 타임아웃. None이면 기본 _SHORT_TIMEOUT 사용.
    """
    import time
    t0 = time.perf_counter()
    effective_timeout = timeout_override or _SHORT_TIMEOUT
    result_text = ""
    success = True
    try:
        if source_name == "twitter":
            result_text = await _async_fetch_twitter_trends(session, keyword, bearer_token)
        elif source_name == "reddit":
            result_text = await _async_fetch_reddit_trends(session, keyword)
        else:
            result_text = await _async_fetch_google_news_trends(session, keyword)
            if extra_news:
                result_text = f"{extra_news} | {result_text}" if result_text != "관련 뉴스 없음" else extra_news
    except Exception as e:
        log.warning(f"소스 수집 실패 ({source_name}/{keyword}): {e}")
        result_text = f"[{source_name} 오류] {keyword}"
        success = False

    # 소스 품질 메트릭 기록 (conn 있을 때만)
    if conn is not None:
        latency_ms = (time.perf_counter() - t0) * 1000
        quality_score = _calc_quality_score(result_text) if success else 0.0
        from db import record_source_quality
        await record_source_quality(
            conn, source_name, success, latency_ms, 1 if success else 0, quality_score
        )

    return keyword, source_name, result_text


async def _async_collect_contexts(
    raw_trends: list[RawTrend],
    config: AppConfig,
    session: httpx.AsyncClient | None = None,
    conn=None,
) -> dict[str, MultiSourceContext]:
    """asyncio.gather로 전체 트렌드 x 3소스 병렬 수집.

    session이 제공되면 재사용 (O1-1: 세션 공유). 없으면 독립 세션 생성.
    conn이 제공되면 소스 품질 메트릭 기록 (v5.0).
    """
    sources = ["twitter", "reddit", "news"]
    results: dict[str, dict[str, str]] = {t.name: {} for t in raw_trends}

    # [v9.0 B-3] 소스 품질 기반 적응형 필터링 + 동적 타임아웃
    # 최근 7일 평균 품질이 0.3 미만인 소스는 수집 스킵
    skip_sources: set[str] = set()
    source_timeouts: dict[str, float] = {}  # 소스별 동적 타임아웃 (초)
    if conn is not None and getattr(config, "enable_source_quality_tracking", True):
        try:
            from db import get_source_quality_summary
            quality_summary = await get_source_quality_summary(conn, days=7)
            for src_name, stats in quality_summary.items():
                avg_quality = stats.get("avg_quality_score", 0.5)
                success_rate = stats.get("success_rate", 100.0)
                if avg_quality < 0.3 and src_name in sources:
                    skip_sources.add(src_name)
                    log.info(
                        f"  [B-3 품질 필터] '{src_name}' 소스 스킵 "
                        f"(평균 품질={avg_quality:.2f} < 0.3)"
                    )
                elif src_name in sources:
                    # 동적 타임아웃: 저품질→빠른 포기, 고품질→여유롭게
                    if avg_quality >= 0.7 and success_rate >= 80:
                        source_timeouts[src_name] = 10.0
                    elif avg_quality < 0.5 or success_rate < 60:
                        source_timeouts[src_name] = 2.0
                    else:
                        source_timeouts[src_name] = 5.0
            if source_timeouts:
                log.info(f"  [B-3 타임아웃] 소스별 동적 타임아웃: {source_timeouts}")
        except Exception as _e:
            log.debug(f"소스 품질 조회 실패 (무시): {_e}")

    active_sources = [s for s in sources if s not in skip_sources]

    # Google Trends RSS에서 가져온 내장 헤드라인 미리 추출
    extra_news_map: dict[str, str] = {}
    for t in raw_trends:
        if t.source == TrendSource.GOOGLE_TRENDS:
            headlines = t.extra.get("news_headlines", [])
            if headlines:
                extra_news_map[t.name] = " | ".join(headlines)

    # 동시 요청 수 제한을 위한 세마포어
    semaphore = asyncio.Semaphore(config.max_workers)

    async def _limited_fetch(
        sess: httpx.AsyncClient,
        keyword: str,
        source: str,
        bearer_token: str,
        extra_news: str,
    ) -> tuple[str, str, str]:
        async with semaphore:
            return await _async_fetch_single_source(
                sess, keyword, source, bearer_token, extra_news,
                conn=conn if getattr(config, "enable_source_quality_tracking", True) else None,
                timeout_override=source_timeouts.get(source),
            )

    async def _run_all(sess: httpx.AsyncClient):
        tasks = []
        for trend in raw_trends:
            extra_news = extra_news_map.get(trend.name, "")
            for source in active_sources:
                tasks.append(_limited_fetch(
                    sess,
                    trend.name,
                    source,
                    config.twitter_bearer_token,
                    extra_news if source == "news" else "",
                ))
        return await asyncio.gather(*tasks, return_exceptions=True)

    # O1-1: 제공된 세션 재사용, 없으면 독립 세션 생성
    if session is not None:
        gathered = await _run_all(session)
    else:
        async with httpx.AsyncClient() as _session:
            gathered = await _run_all(_session)

    for item in gathered:
        if isinstance(item, Exception):
            log.warning(f"컨텍스트 수집 예외: {item}")
            continue
        keyword, source, text = item
        if keyword in results:
            results[keyword][source] = text
            log.debug(f"  비동기 수집 완료: '{keyword}' [{source}]")

    contexts: dict[str, MultiSourceContext] = {}
    for keyword, source_data in results.items():
        news_insight = source_data.get("news", "")

        # [Phase 4] Scrapling 뉴스 보강 — RSS 인사이트가 부족하면 직접 스크래핑
        try:
            from news_scraper import enrich_news_context
            news_insight = enrich_news_context(keyword, news_insight)
        except ImportError:
            pass  # Scrapling 미설치 시 기존 동작 유지
        except Exception as _e:
            log.debug(f"[Scrapling] 뉴스 보강 실패 '{keyword}': {_e}")

        contexts[keyword] = MultiSourceContext(
            twitter_insight=source_data.get("twitter", ""),
            reddit_insight=source_data.get("reddit", ""),
            news_insight=news_insight,
        )

    return contexts

# ══════════════════════════════════════════════════════
#  v15.0 Phase C: Google Trends Related Queries
# ══════════════════════════════════════════════════════

async def _async_fetch_google_trends_related(
    session: httpx.AsyncClient,
    trends: list[RawTrend],
    country: str = "korea",
) -> dict[str, list[str]]:
    """
    Google Trends 소스의 news_headlines를 related queries로 변환.
    반환: {trend_name: [related_query_1, related_query_2, ...]}
    """
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
    """
    Google Suggest (자동완성) API로 연관 키워드 수집.
    반환: 추천 검색어 리스트
    """
    encoded = urllib.parse.quote(query)
    url = (
        f"https://suggestqueries.google.com/complete/search"
        f"?client=firefox&q={encoded}&hl={language}&gl={country}"
    )
    
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
            # Firefox 형식: [query, [suggestion1, suggestion2, ...]]
            if isinstance(data, list) and len(data) >= 2:
                return [s for s in data[1] if isinstance(s, str)]
            return []
    except Exception as e:
        log.debug(f"Google Suggest 수집 실패 ({query}): {e}")
        return []
