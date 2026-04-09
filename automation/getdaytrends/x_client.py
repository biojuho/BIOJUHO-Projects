"""
getdaytrends — Twikit 기반 X/Twitter 읽기 전용 클라이언트.

X API v2 Bearer Token이 없거나 레이트 리밋 초과 시,
Jina 스크래핑 대신 Twikit으로 트렌드/트윗을 직접 수집한다.

주의: Twikit은 비공식 API 사용. 전용 계정 권장, 게시 기능 사용 금지.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import random
import tempfile
from pathlib import Path
from typing import Any

from loguru import logger as log
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Twikit은 선택 의존성 (설치 안 되어 있으면 폴백 비활성화)
try:
    from twikit import Client as TwikitClient

    TWIKIT_AVAILABLE = True
except ImportError:
    TWIKIT_AVAILABLE = False

_COOKIES_PATH = Path(__file__).parent / "data" / "x_cookies.json"
_COOKIES_ENC_PATH = Path(__file__).parent / "data" / "x_cookies.enc"
_client: TwikitClient | None = None
# B-006 fix: 모듈 레벨 asyncio.Lock() 생성 금지 (이벤트 루프 없는 환경에서 크래시)
# 첫 사용 시 lazy 초기화
_client_lock: asyncio.Lock | None = None
_login_attempted = False

# ══════════════════════════════════════════════════════
#  쿠키 암호화 유틸리티
# ══════════════════════════════════════════════════════


def _derive_fernet_key() -> bytes | None:
    """TWIKIT_COOKIE_SECRET(우선) 또는 TWIKIT_PASSWORD에서 Fernet 키 도출.
    설정 없으면 None 반환 (암호화 비활성)."""
    secret = os.environ.get("TWIKIT_COOKIE_SECRET") or os.environ.get("TWIKIT_PASSWORD", "")
    if not secret:
        return None
    raw = hashlib.pbkdf2_hmac("sha256", secret.encode(), b"gdt-twikit-cookie-v1", 200_000)
    return base64.urlsafe_b64encode(raw)


def _load_encrypted_cookies(client: "TwikitClient") -> bool:
    """암호화된 쿠키(.enc)를 복호화해 클라이언트에 로드. 성공하면 True."""
    if not _COOKIES_ENC_PATH.exists():
        return False
    key = _derive_fernet_key()
    if not key:
        return False
    try:
        from cryptography.fernet import Fernet, InvalidToken

        f = Fernet(key)
        decrypted = f.decrypt(_COOKIES_ENC_PATH.read_bytes())
        cookies = json.loads(decrypted)
        # Twikit은 파일 경로를 요구하므로 임시 파일 경유
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            json.dump(cookies, tmp)
            tmp_path = tmp.name
        try:
            client.load_cookies(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        return True
    except ImportError:
        log.debug("[Twikit] cryptography 미설치 — 암호화 쿠키 로드 불가")
        return False
    except Exception as e:
        log.warning(f"[Twikit] 암호화 쿠키 로드 실패: {e}")
        return False


def _save_encrypted_cookies(plain_path: Path) -> None:
    """로그인 후 생성된 평문 쿠키를 암호화 저장하고 원본 삭제.
    cryptography 미설치 또는 시크릿 미설정 시 평문 유지 + 경고."""
    key = _derive_fernet_key()
    if not key:
        log.warning(
            "[Twikit] TWIKIT_COOKIE_SECRET 미설정 — 쿠키가 평문으로 저장됩니다. "
            "보안 강화를 위해 .env에 TWIKIT_COOKIE_SECRET=<무작위 긴 문자열> 을 추가하세요."
        )
        return
    try:
        from cryptography.fernet import Fernet

        f = Fernet(key)
        encrypted = f.encrypt(plain_path.read_bytes())
        _COOKIES_ENC_PATH.parent.mkdir(parents=True, exist_ok=True)
        _COOKIES_ENC_PATH.write_bytes(encrypted)
        plain_path.unlink(missing_ok=True)
        log.info("[Twikit] 쿠키 암호화 저장 완료 (원본 삭제)")
    except ImportError:
        log.warning("[Twikit] cryptography 미설치 — 쿠키 암호화 건너뜀. pip install cryptography")
    except OSError as e:
        log.warning(f"[Twikit] 쿠키 암호화 저장 실패: {e}")


async def _get_client() -> TwikitClient | None:
    """Twikit 싱글톤 클라이언트. 쿠키 기반 세션 재사용."""
    global _client, _login_attempted, _client_lock

    if not TWIKIT_AVAILABLE:
        return None

    # B-006 fix: 이벤트 루프 내에서 첫 사용 시 Lock 생성
    if _client_lock is None:
        _client_lock = asyncio.Lock()

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

        # 1순위: 암호화 쿠키 (.enc)
        if _load_encrypted_cookies(_client):
            log.info("[Twikit] 암호화 쿠키로 세션 복원")
            return _client

        # 2순위: 평문 쿠키 잔존 시 로드 후 즉시 암호화 전환
        if _COOKIES_PATH.exists():
            try:
                _client.load_cookies(str(_COOKIES_PATH))
                log.info("[Twikit] 평문 쿠키 로드 → 암호화 전환 중")
                _save_encrypted_cookies(_COOKIES_PATH)
                return _client
            except (OSError, ValueError, RuntimeError) as e:
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
            log.info("[Twikit] 로그인 성공, 쿠키 암호화 저장 중")
            _save_encrypted_cookies(_COOKIES_PATH)
            return _client
        except (ValueError, RuntimeError, ConnectionError, TimeoutError) as e:
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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((RuntimeError, ConnectionError, TimeoutError, asyncio.TimeoutError, ValueError)),  # B-017
    retry_error_callback=lambda rs: []
)
async def search_tweets(keyword: str, count: int = 10) -> list[dict[str, Any]]:
    """키워드로 최신 트윗 검색. 실패 시 3회 재시도 후 빈 리스트 반환."""
    client = await _get_client()
    if client is None:
        return []

    await asyncio.sleep(random.uniform(1.5, 4.0))  # 봇 감지 회피
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
            except ValueError:
                pass

        prefix = f"[{time_label}] " if time_label else ""
        summaries.append(f"{prefix}{eng} {text}")

    return "\n".join(summaries)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((RuntimeError, ConnectionError, TimeoutError, ValueError)),
    retry_error_callback=lambda rs: []
)
async def fetch_trends(category: str = "trending") -> list[dict[str, Any]]:
    """X 트렌딩 토픽 직접 수집. 실패 시 3회 재시도 후 빈 리스트."""
    client = await _get_client()
    if client is None:
        return []

    await asyncio.sleep(random.uniform(1.0, 3.0))
    trends = await client.get_trends(category)
    return [{"name": getattr(t, "name", str(t)), "tweet_count": getattr(t, "tweet_count", 0) or 0} for t in trends]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    # B-017 fix: asyncio.TimeoutError 명시 적용
    retry=retry_if_exception_type((RuntimeError, ConnectionError, TimeoutError, asyncio.TimeoutError, ValueError)),
    retry_error_callback=lambda rs: None
)
async def get_tweet_metrics(tweet_id: str) -> dict[str, Any] | None:
    """트윗 ID로 참여도 메트릭 조회. 3회 재시도 수행."""
    client = await _get_client()
    if client is None:
        return None

    await asyncio.sleep(random.uniform(1.0, 3.0))
    tweet = await client.get_tweet_by_id(tweet_id)
    return {
        "tweet_id": tweet_id,
        "likes": getattr(tweet, "favorite_count", 0) or 0,
        "retweets": getattr(tweet, "retweet_count", 0) or 0,
        "quotes": getattr(tweet, "quote_count", 0) or 0,
        "replies": getattr(tweet, "reply_count", 0) or 0,
        "views": getattr(tweet, "view_count", 0) or 0,
    }
