"""
getdaytrends — Twikit 기반 X/Twitter 읽기 전용 클라이언트.

X API v2 Bearer Token이 없거나 레이트 리밋 초과 시,
Jina 스크래핑 대신 Twikit으로 트렌드/트윗을 직접 수집한다.

주의: Twikit은 비공식 API 사용. 전용 계정 권장, 게시 기능 사용 금지.
"""

from __future__ import annotations

import asyncio
import os
import random
from pathlib import Path
from typing import Any

from loguru import logger as log

# Twikit은 선택 의존성 (설치 안 되어 있으면 폴백 비활성화)
try:
    from twikit import Client as TwikitClient

    TWIKIT_AVAILABLE = True
except ImportError:
    TWIKIT_AVAILABLE = False

_COOKIES_PATH = Path(__file__).parent / "data" / "x_cookies.json"
_client: TwikitClient | None = None
_client_lock = asyncio.Lock()
_login_attempted = False


async def _get_client() -> TwikitClient | None:
    """Twikit 싱글톤 클라이언트. 쿠키 기반 세션 재사용."""
    global _client, _login_attempted

    if not TWIKIT_AVAILABLE:
        return None

    async with _client_lock:
        if _client is not None:
            return _client

        if _login_attempted:
            # 이전 로그인 시도 실패 — 재시도하지 않음
            return None

        username = os.environ.get("TWIKIT_USERNAME", "")
        email = os.environ.get("TWIKIT_EMAIL", "")
        password = os.environ.get("TWIKIT_PASSWORD", "")

        if not (username and password):
            log.debug("[Twikit] TWIKIT_USERNAME/TWIKIT_PASSWORD 미설정 -- 비활성화")
            _login_attempted = True
            return None

        _client = TwikitClient("ko")

        # 쿠키 파일이 있으면 재사용 (로그인 API 호출 회피)
        if _COOKIES_PATH.exists():
            try:
                _client.load_cookies(str(_COOKIES_PATH))
                log.info("[Twikit] 저장된 쿠키로 세션 복원")
                return _client
            except Exception as e:
                log.warning(f"[Twikit] 쿠키 로드 실패: {e} -- 재로그인 시도")

        # 첫 로그인
        _login_attempted = True
        try:
            _COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
            await _client.login(
                auth_info_1=username,
                auth_info_2=email or username,
                password=password,
                cookies_file=str(_COOKIES_PATH),
            )
            log.info("[Twikit] 로그인 성공, 쿠키 저장됨")
            return _client
        except Exception as e:
            log.warning(f"[Twikit] 로그인 실패: {e}")
            _client = None
            return None


def is_available() -> bool:
    """Twikit 사용 가능 여부 (패키지 설치 + 자격증명 설정)."""
    if not TWIKIT_AVAILABLE:
        return False
    username = os.environ.get("TWIKIT_USERNAME", "")
    password = os.environ.get("TWIKIT_PASSWORD", "")
    return bool(username and password)


async def search_tweets(keyword: str, count: int = 10) -> list[dict[str, Any]]:
    """키워드로 최신 트윗 검색. 실패 시 빈 리스트 반환."""
    client = await _get_client()
    if client is None:
        return []

    await asyncio.sleep(random.uniform(1.5, 4.0))  # 봇 감지 회피

    try:
        tweets = await client.search_tweet(keyword, "Latest", count=count)
        results = []
        for tweet in tweets:
            metrics = {
                "likes": getattr(tweet, "favorite_count", 0) or 0,
                "retweets": getattr(tweet, "retweet_count", 0) or 0,
                "views": getattr(tweet, "view_count", 0) or 0,
                "replies": getattr(tweet, "reply_count", 0) or 0,
                "quotes": getattr(tweet, "quote_count", 0) or 0,
            }
            results.append(
                {
                    "id": getattr(tweet, "id", ""),
                    "text": getattr(tweet, "text", ""),
                    "user": getattr(tweet.user, "screen_name", "") if tweet.user else "",
                    "created_at": getattr(tweet, "created_at", ""),
                    **metrics,
                }
            )
        return results
    except Exception as e:
        log.debug(f"[Twikit] 트윗 검색 실패 ({keyword}): {e}")
        return []


async def search_tweets_formatted(keyword: str, count: int = 10) -> str:
    """키워드로 트윗 검색 후 scraper.py 호환 텍스트 반환.

    _async_fetch_twitter_trends()의 반환 포맷과 동일:
    "[MM/DD HH:MM] [좋아요L/RTRT] 트윗 본문" 줄바꿈 구분
    """
    tweets = await search_tweets(keyword, count)
    if not tweets:
        return ""

    # 참여도 기반 정렬 (좋아요 + RT*2 + 인용*1.5)
    for t in tweets:
        t["_eng"] = t["likes"] + t["retweets"] * 2 + t["quotes"] * 1.5
    tweets.sort(key=lambda t: t["_eng"], reverse=True)

    summaries = []
    for t in tweets[:7]:
        eng = f"[{t['likes']}L/{t['retweets']}RT]"
        text = t["text"].replace("\n", " ")[:200]

        time_label = ""
        raw_ts = t.get("created_at", "")
        if raw_ts:
            try:
                from datetime import datetime, timedelta, timezone

                # Twikit은 "Thu Mar 19 12:30:00 +0000 2026" 형식
                dt_utc = datetime.strptime(raw_ts, "%a %b %d %H:%M:%S %z %Y")
                dt_local = dt_utc.astimezone(timezone(timedelta(hours=9)))  # KST
                time_label = dt_local.strftime("%m/%d %H:%M")
            except Exception:
                pass

        prefix = f"[{time_label}] " if time_label else ""
        summaries.append(f"{prefix}{eng} {text}")

    return "\n".join(summaries)


async def fetch_trends(category: str = "trending") -> list[dict[str, Any]]:
    """X 트렌딩 토픽 직접 수집. 실패 시 빈 리스트."""
    client = await _get_client()
    if client is None:
        return []

    await asyncio.sleep(random.uniform(1.0, 3.0))

    try:
        trends = await client.get_trends(category)
        return [{"name": getattr(t, "name", str(t)), "tweet_count": getattr(t, "tweet_count", 0) or 0} for t in trends]
    except Exception as e:
        log.debug(f"[Twikit] 트렌드 수집 실패: {e}")
        return []


async def get_tweet_metrics(tweet_id: str) -> dict[str, Any] | None:
    """트윗 ID로 참여도 메트릭 조회."""
    client = await _get_client()
    if client is None:
        return None

    await asyncio.sleep(random.uniform(1.0, 3.0))

    try:
        tweet = await client.get_tweet_by_id(tweet_id)
        return {
            "tweet_id": tweet_id,
            "likes": getattr(tweet, "favorite_count", 0) or 0,
            "retweets": getattr(tweet, "retweet_count", 0) or 0,
            "quotes": getattr(tweet, "quote_count", 0) or 0,
            "replies": getattr(tweet, "reply_count", 0) or 0,
            "views": getattr(tweet, "view_count", 0) or 0,
        }
    except Exception as e:
        log.debug(f"[Twikit] 메트릭 조회 실패 ({tweet_id}): {e}")
        return None
