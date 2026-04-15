"""
getdaytrends — Reddit Context Collector
Reddit Public JSON API 기반 핫 포스트 수집.
collectors/context.py에서 분리됨.
"""

import urllib.parse

import httpx
from loguru import logger as log

try:
    from ..utils import run_async
except ImportError:
    from utils import run_async

_SHORT_TIMEOUT = httpx.Timeout(8.0, connect=4.0)


def _resolve_timeout(timeout: httpx.Timeout | float | None) -> httpx.Timeout | float:
    return _SHORT_TIMEOUT if timeout is None else timeout


async def _async_fetch_reddit_trends(
    session: httpx.AsyncClient,
    keyword: str,
    timeout: httpx.Timeout | float | None = None,
) -> str:
    """Reddit 핫 포스트 수집 (비동기)."""
    encoded_query = urllib.parse.quote(keyword)
    url = f"https://www.reddit.com/search.json?q={encoded_query}&sort=hot&limit=5&t=day"
    headers = {"User-Agent": "GetDayTrends/2.3"}

    try:
        resp = await session.get(url, headers=headers, timeout=_resolve_timeout(timeout))
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
    async with httpx.AsyncClient() as session:
        return await _async_fetch_reddit_trends(session, keyword)
