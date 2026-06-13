"""
getdaytrends — X (Twitter) Context Collector
Twikit/Jina Reader/API v2 기반 트윗 수집 + OAuth 2.0 게시.
collectors/context.py에서 분리됨.
"""

import time
import urllib.parse

import httpx
from loguru import logger as log

try:
    from ..utils import run_async
except ImportError:
    from utils import run_async

# Timeout settings
_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=6.0)
_SHORT_TIMEOUT = httpx.Timeout(8.0, connect=4.0)


def _resolve_timeout(timeout: httpx.Timeout | float | None) -> httpx.Timeout | float:
    return _SHORT_TIMEOUT if timeout is None else timeout


def _looks_like_login_shell(text: str) -> bool:
    lowered = (text or "").lower()
    return any(
        marker in lowered
        for marker in (
            "log in to x",
            "sign in to x",
            "login to x",
            "sign in",
            "log in",
            "<html",
            "<!doctype",
        )
    )


# ══════════════════════════════════════════════════════
#  Twikit / Jina Fallback
# ══════════════════════════════════════════════════════


async def _async_fetch_x_via_twikit_or_jina(
    session: httpx.AsyncClient,
    keyword: str,
    timeout: httpx.Timeout | float | None = None,
) -> str:
    """Twikit 우선 시도, 실패 시 Jina AI Reader 폴백."""
    try:
        try:
            from ..x_client import is_available, search_tweets_formatted
        except ImportError:
            from x_client import is_available, search_tweets_formatted

        if is_available():
            result = await search_tweets_formatted(keyword, count=10)
            if result and len(result) > 30:
                log.debug(f"[Twikit] '{keyword}' 트윗 수집 성공")
                return result
    except Exception as e:
        log.debug(f"[Twikit] '{keyword}' 수집 실패: {e}")

    return await _async_fetch_x_via_jina(session, keyword, timeout=timeout)


async def _async_fetch_x_via_jina(
    session: httpx.AsyncClient,
    keyword: str,
    timeout: httpx.Timeout | float | None = None,
) -> str:
    """Jina AI Reader로 X 검색 결과 무료 스크래핑."""
    encoded = urllib.parse.quote(f"{keyword} lang:ko")
    jina_url = f"https://r.jina.ai/https://x.com/search?q={encoded}&f=live"
    headers = {
        "User-Agent": "GetDayTrends/2.3",
        "Accept": "text/plain",
    }
    try:
        resp = await session.get(jina_url, headers=headers, timeout=_resolve_timeout(timeout))
        resp.raise_for_status()
        text = resp.text.strip()
        if _looks_like_login_shell(text):
            log.debug(f"Jina X shell/login page detected ({keyword})")
            return f"[X 데이터 없음] {keyword}"
        if len(text) > 50:
            return text[:500]
        return f"[X 검색] {keyword} 관련 실시간 데이터 부족"
    except Exception as e:
        log.debug(f"Jina X 스크래핑 실패 ({keyword}): {e}")
        return f"[X 데이터 없음] {keyword}"


# ══════════════════════════════════════════════════════
#  X API v2 Search
# ══════════════════════════════════════════════════════


def _check_rate_limit(headers: "httpx.Headers") -> None:
    remaining = headers.get("x-rate-limit-remaining")
    limit = headers.get("x-rate-limit-limit")
    reset = headers.get("x-rate-limit-reset")
    if remaining is not None and limit is not None:
        try:
            if int(remaining) <= 3:
                reset_in = int(reset) - int(time.time()) if reset else "?"
                log.warning(f"[X API] 레이트 리밋 임박: {remaining}/{limit} 남음, {reset_in}초 후 초기화")
        except (ValueError, TypeError):
            pass


def _twitter_recent_search_url(keyword: str) -> str:
    query_str = f"{keyword} -is:retweet -is:quote -is:nullcast lang:ko min_faves:3"
    encoded_query = urllib.parse.quote(query_str)
    return (
        "https://api.twitter.com/2/tweets/search/recent"
        f"?query={encoded_query}&max_results=25"
        "&tweet.fields=public_metrics,created_at,context_annotations"
        "&expansions=author_id"
    )


def _twitter_auth_headers(bearer_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {bearer_token}",
        "User-Agent": "GetDayTrends/2.4",
    }


async def _twitter_api_response(
    session: httpx.AsyncClient,
    keyword: str,
    bearer_token: str,
    timeout: httpx.Timeout | float | None,
) -> object:
    return await session.get(
        _twitter_recent_search_url(keyword),
        headers=_twitter_auth_headers(bearer_token),
        timeout=_resolve_timeout(timeout),
    )


async def _twitter_status_fallback(
    session: httpx.AsyncClient,
    keyword: str,
    resp,
    timeout: httpx.Timeout | float | None,
) -> str | None:
    if resp.status_code == 429:
        retry_after = resp.headers.get("retry-after", "60")
        log.warning(f"[X API] rate limit exceeded. Retry after {retry_after}s")
        return await _async_fetch_x_via_twikit_or_jina(session, keyword, timeout=timeout)
    if resp.status_code == 403:
        log.debug("[X API] search permission unavailable. Falling back to Jina.")
        return await _async_fetch_x_via_twikit_or_jina(session, keyword, timeout=timeout)
    return None


def _tweet_engagement(tweet: dict) -> int:
    metrics = tweet.get("public_metrics", {})
    return metrics.get("like_count", 0) + metrics.get("retweet_count", 0) * 2 + metrics.get("quote_count", 0)


def _tweet_time_label(tweet: dict) -> str:
    raw_ts = tweet.get("created_at", "")
    if not raw_ts:
        return ""
    try:
        from datetime import datetime, timedelta, timezone

        dt_utc = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone(timezone(timedelta(hours=9)))
        return dt_local.strftime("%m/%d %H:%M")
    except Exception:
        return ""


def _tweet_summary(tweet: dict) -> str:
    metrics = tweet.get("public_metrics", {})
    engagement = f"[{metrics.get('like_count', 0)}L/{metrics.get('retweet_count', 0)}RT]"
    text = tweet["text"].replace("\n", " ")[:200]
    time_label = _tweet_time_label(tweet)
    prefix = f"[{time_label}] " if time_label else ""
    return f"{prefix}{engagement} {text}"


def _twitter_summaries(data: dict, keyword: str) -> str:
    if "data" not in data:
        log.debug(f"[X API] '{keyword}' recent tweets unavailable")
        return "최근 관련 트윗 없음"

    tweets = data["data"]
    tweets.sort(key=_tweet_engagement, reverse=True)
    return "\n".join(_tweet_summary(tweet) for tweet in tweets[:7])


async def _async_fetch_twitter_trends(
    session: httpx.AsyncClient,
    keyword: str,
    bearer_token: str = "",
    timeout: httpx.Timeout | float | None = None,
) -> str:
    """X API v2 최신 트윗 검색."""
    if not bearer_token:
        return await _async_fetch_x_via_twikit_or_jina(session, keyword, timeout=timeout)

    try:
        resp = await _twitter_api_response(session, keyword, bearer_token, timeout)
        _check_rate_limit(resp.headers)

        fallback = await _twitter_status_fallback(session, keyword, resp, timeout)
        if fallback is not None:
            return fallback

        resp.raise_for_status()
        return _twitter_summaries(resp.json(), keyword)

    except httpx.HTTPStatusError as e:
        log.debug(f"Twitter API HTTP 오류 ({keyword}): {e.response.status_code} → Jina 폴백")
        return await _async_fetch_x_via_twikit_or_jina(session, keyword, timeout=timeout)
    except Exception as e:
        log.debug(f"Twitter API 오류 ({keyword}): {e}")
        return f"[X API 오류] {keyword} 트렌드 감지 실패"


def fetch_twitter_trends(keyword: str, bearer_token: str = "") -> str:
    """X API v2 최신 트윗 검색 (동기 호환 래퍼)."""
    return run_async(_async_fetch_twitter_trends_standalone(keyword, bearer_token))


async def _async_fetch_twitter_trends_standalone(keyword: str, bearer_token: str = "") -> str:
    async with httpx.AsyncClient() as session:
        return await _async_fetch_twitter_trends(session, keyword, bearer_token)


# ══════════════════════════════════════════════════════
#  X Posting (OAuth 2.0)
# ══════════════════════════════════════════════════════


async def post_to_x_async(
    content: str,
    access_token: str,
    session: httpx.AsyncClient | None = None,
) -> dict:
    """X API v2로 트윗 게시 (OAuth 2.0 유저 컨텍스트)."""
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
            resp = await sess.post(url, headers=headers, json=payload, timeout=_SHORT_TIMEOUT)
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
