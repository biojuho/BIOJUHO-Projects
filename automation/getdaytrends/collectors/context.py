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
    from ..models import MultiSourceContext, RawTrend, TrendSource
except ImportError:
    from config import AppConfig
    from models import MultiSourceContext, RawTrend, TrendSource

# ── Re-export all public APIs ──
from .twitter import (  # noqa: F401
    _async_fetch_twitter_trends,
    _async_fetch_x_via_jina,
    _async_fetch_x_via_twikit_or_jina,
    _check_rate_limit,
    fetch_twitter_trends,
    post_to_x,
    post_to_x_async,
)
from .reddit import (  # noqa: F401
    _async_fetch_reddit_trends,
    fetch_reddit_trends,
)
from .google_news import (  # noqa: F401
    _async_fetch_google_news_trends,
    _async_fetch_google_suggest,
    _async_fetch_google_trends_related,
    _format_news_age,
    _parse_rss_date,
    fetch_google_news_trends,
)

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
    """단일 소스 수집 (비동기). 소스 품질 메트릭 기록 포함."""
    import time

    t0 = time.perf_counter()
    effective_timeout = _SHORT_TIMEOUT if timeout_override is None else timeout_override
    result_text = ""
    success = True
    try:
        if source_name == "twitter":
            result_text = await _async_fetch_twitter_trends(
                session, keyword, bearer_token, timeout=effective_timeout,
            )
        elif source_name == "reddit":
            result_text = await _async_fetch_reddit_trends(session, keyword, timeout=effective_timeout)
        else:
            result_text = await _async_fetch_google_news_trends(session, keyword, timeout=effective_timeout)
            if extra_news:
                result_text = f"{extra_news} | {result_text}" if result_text != "관련 뉴스 없음" else extra_news
    except Exception as e:
        log.warning(f"소스 수집 실패 ({source_name}/{keyword}): {e}")
        result_text = f"[{source_name} 오류] {keyword}"
        success = False

    if conn is not None:
        latency_ms = (time.perf_counter() - t0) * 1000
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
            log.warning(f"소스 품질 기록 실패 ({source_name}/{keyword}): {exc}")

    return keyword, source_name, result_text


async def _async_collect_contexts(
    raw_trends: list[RawTrend],
    config: AppConfig,
    session: httpx.AsyncClient | None = None,
    conn=None,
) -> dict[str, MultiSourceContext]:
    """asyncio.gather로 전체 트렌드 x 3소스 병렬 수집."""
    sources = ["twitter", "reddit", "news"]
    results: dict[str, dict[str, str]] = {t.name: {} for t in raw_trends}

    # [v9.0 B-3] 소스 품질 기반 적응형 필터링 + 동적 타임아웃
    skip_sources: set[str] = set()
    source_timeouts: dict[str, float] = {}
    if conn is not None and getattr(config, "enable_source_quality_tracking", True):
        try:
            try:
                from ..db import get_source_quality_summary
            except ImportError:
                from db import get_source_quality_summary

            quality_summary = await get_source_quality_summary(conn, days=7)
            for src_name, stats in quality_summary.items():
                avg_quality = stats.get("avg_quality_score", 0.5)
                success_rate = stats.get("success_rate", 100.0)
                if avg_quality < 0.3 and src_name in sources:
                    skip_sources.add(src_name)
                    log.info(f"  [B-3 품질 필터] '{src_name}' 소스 스킵 (평균 품질={avg_quality:.2f} < 0.3)")
                elif src_name in sources:
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

    extra_news_map: dict[str, str] = {}
    for t in raw_trends:
        if t.source == TrendSource.GOOGLE_TRENDS:
            headlines = t.extra.get("news_headlines", [])
            if headlines:
                extra_news_map[t.name] = " | ".join(headlines)

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

    def _build_tasks(sess: httpx.AsyncClient):
        tasks = []
        for trend in raw_trends:
            extra_news = extra_news_map.get(trend.name, "")
            for source in active_sources:
                tasks.append(
                    asyncio.create_task(
                        _limited_fetch(
                            sess,
                            trend.name,
                            source,
                            config.twitter_bearer_token,
                            extra_news if source == "news" else "",
                        )
                    )
                )
        return tasks

    _GLOBAL_TIMEOUT = getattr(config, "context_global_timeout", 120)

    async def _collect_with_partial_timeout(sess: httpx.AsyncClient) -> list[tuple[str, str, str] | Exception]:
        tasks = _build_tasks(sess)
        if not tasks:
            return []

        done, pending = await asyncio.wait(tasks, timeout=_GLOBAL_TIMEOUT)
        if pending:
            log.error(
                f"[컨텍스트 수집] 글로벌 타임아웃({_GLOBAL_TIMEOUT}s) 초과 — {len(done)}개 결과 보존, {len(pending)}개 미완 task를 종료"
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

        gathered: list[tuple[str, str, str] | Exception] = []
        for task in done:
            try:
                gathered.append(task.result())
            except Exception as exc:
                gathered.append(exc)
        return gathered

    if session is not None:
        gathered = await _collect_with_partial_timeout(session)
    else:
        async with httpx.AsyncClient() as _session:
            gathered = await _collect_with_partial_timeout(_session)

    for item in gathered:
        if isinstance(item, Exception):
            log.warning(f"컨텍스트 수집 예외: {type(item).__name__}: {item}")
            continue
        keyword, source, text = item
        if keyword in results:
            results[keyword][source] = text
            log.debug(f"  비동기 수집 완료: '{keyword}' [{source}]")

    contexts: dict[str, MultiSourceContext] = {}
    for keyword, source_data in results.items():
        news_insight = source_data.get("news", "")

        try:
            try:
                from ..news_scraper import enrich_news_context
            except ImportError:
                from news_scraper import enrich_news_context

            news_insight = enrich_news_context(keyword, news_insight)
        except ImportError:
            pass
        except Exception as _e:
            log.debug(f"[Scrapling] 뉴스 보강 실패 '{keyword}': {_e}")

        contexts[keyword] = MultiSourceContext(
            twitter_insight=source_data.get("twitter", ""),
            reddit_insight=source_data.get("reddit", ""),
            news_insight=news_insight,
        )

    return contexts
