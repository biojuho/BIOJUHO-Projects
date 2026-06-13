"""
getdaytrends — Context Collector (facade)
Twitter/Reddit/Google News/Google Suggest 컨텍스트 수집.
scraper.py에서 분리됨.

Implementation modules:
    twitter.py      — X API v2 / Twikit / Jina Reader + posting
    reddit.py       — Reddit Public JSON API
    google_news.py  — Google News RSS + Suggest + Related Queries
"""

import asyncio

import httpx
from loguru import logger as log

try:
    from ..config import AppConfig
    from ..models import MultiSourceContext, RawTrend
except ImportError:
    from config import AppConfig
    from models import MultiSourceContext, RawTrend

try:
    from . import twitter as _twitter
except ImportError:
    import collectors.twitter as _twitter

# ── Re-export all public APIs ──
from .google_news import (  # noqa: F401
    _async_fetch_google_news_trends,
    _async_fetch_google_suggest,
    _async_fetch_google_trends_related,
    _format_news_age,
    _parse_rss_date,
    fetch_google_news_trends,
)
from .reddit import (  # noqa: F401
    _async_fetch_reddit_trends,
    fetch_reddit_trends,
)
from .twitter import (  # noqa: F401
    _async_fetch_twitter_trends,
    _async_fetch_x_via_jina,
    _async_fetch_x_via_twikit_or_jina,
    _check_rate_limit,
    fetch_twitter_trends,
    post_to_x,
    post_to_x_async,
)

_async_fetch_x_via_twikit_or_jina_impl = _async_fetch_x_via_twikit_or_jina


async def _async_fetch_x_via_twikit_or_jina(
    session: httpx.AsyncClient,
    keyword: str,
    timeout: httpx.Timeout | float | None = None,
) -> str:
    _twitter._async_fetch_x_via_jina = _async_fetch_x_via_jina
    return await _async_fetch_x_via_twikit_or_jina_impl(session, keyword, timeout=timeout)


# Shared constants
_SHORT_TIMEOUT = httpx.Timeout(8.0, connect=4.0)

_COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
}


def _is_similar_keyword(new_keyword: str, existing: set[str]) -> bool:
    """키워드 유사도 비교: 부분 문자열 매칭으로 중복 판단."""
    new_lower = new_keyword.lower().strip()
    if new_lower in existing:
        return True
    for kw in existing:
        kw_lower = kw.lower().strip()
        if len(new_lower) >= 3 and len(kw_lower) >= 3:
            if new_lower in kw_lower or kw_lower in new_lower:
                log.debug(f"  유사 키워드 감지: '{new_keyword}' ≈ '{kw}'")
                return True
    return False


def _calc_quality_score(text: str) -> float:
    """컨텍스트 텍스트 기반 품질 점수 (0.0~1.0)."""
    if not text or len(text) < 20:
        return 0.0
    low = text.lower()
    if any(kw in low for kw in ["없음", "오류", "실패", "제한", "error", "none", "fail"]):
        return 0.0
    if len(text) >= 200:
        return 1.0
    return round(len(text) / 200, 2)


# ══════════════════════════════════════════════════════

def _context_effective_timeout(timeout_override: httpx.Timeout | float | None) -> httpx.Timeout | float:
    return _SHORT_TIMEOUT if timeout_override is None else timeout_override


def _merge_extra_news(result_text: str, extra_news: str) -> str:
    if not extra_news:
        return result_text
    return f"{extra_news} | {result_text}" if result_text != "관련 뉴스 없음" else extra_news


async def _fetch_context_source(
    session: httpx.AsyncClient,
    keyword: str,
    source_name: str,
    bearer_token: str,
    extra_news: str,
    timeout: httpx.Timeout | float,
) -> str:
    if source_name == "twitter":
        return await _async_fetch_twitter_trends(
            session,
            keyword,
            bearer_token,
            timeout=timeout,
        )
    if source_name == "reddit":
        return await _async_fetch_reddit_trends(session, keyword, timeout=timeout)

    result_text = await _async_fetch_google_news_trends(session, keyword, timeout=timeout)
    return _merge_extra_news(result_text, extra_news)


def _context_source_error_text(source_name: str, keyword: str) -> str:
    return f"[{source_name} 오류] {keyword}"


async def _record_direct_source_quality(
    conn,
    *,
    source_name: str,
    keyword: str,
    result_text: str,
    success: bool,
    latency_ms: float,
) -> None:
    if conn is None:
        return
    quality_score = _calc_quality_score(result_text) if success else 0.0
    try:
        from ..db import record_source_quality
    except ImportError:
        from db import record_source_quality

    try:
        await record_source_quality(conn, source_name, success, latency_ms, 1 if success else 0, quality_score)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.warning(f"Source quality record failed ({source_name}/{keyword}): {exc}")
#  Orchestrator: Multi-Source Context Collection
# ══════════════════════════════════════════════════════


async def _async_fetch_single_source(
    session: httpx.AsyncClient,
    keyword: str,
    source_name: str,
    bearer_token: str = "",
    extra_news: str = "",
    conn=None,
    metrics_recorder=None,
    timeout_override: httpx.Timeout | float | None = None,
) -> tuple[str, str, str]:
    """Fetch one context source and optionally record direct source-quality metrics."""
    import time

    t0 = time.perf_counter()
    success = True
    try:
        result_text = await _fetch_context_source(
            session,
            keyword,
            source_name,
            bearer_token,
            extra_news,
            _context_effective_timeout(timeout_override),
        )
    except Exception as e:
        log.warning(f"source collection failed ({source_name}/{keyword}): {e}")
        result_text = _context_source_error_text(source_name, keyword)
        success = False

    await _record_direct_source_quality(
        conn,
        source_name=source_name,
        keyword=keyword,
        result_text=result_text,
        success=success,
        latency_ms=(time.perf_counter() - t0) * 1000,
    )
    return keyword, source_name, result_text

async def _async_collect_contexts(
    raw_trends: list[RawTrend],
    config: AppConfig,
    session: httpx.AsyncClient | None = None,
    conn=None,
) -> dict[str, MultiSourceContext]:
    """Collect contexts using the runtime-safe implementation."""
    try:
        from .context_runtime import _async_collect_contexts as _runtime_collect_contexts
    except ImportError:
        from collectors.context_runtime import _async_collect_contexts as _runtime_collect_contexts

    return await _runtime_collect_contexts(raw_trends, config, session=session, conn=conn)
