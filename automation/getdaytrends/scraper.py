"""
getdaytrends v2.4 - Multi-Source Trend Collection (asyncio)
getdaytrends.com + Google Trends RSS + Twitter API + Reddit + Google News RSS.
비동기 병렬 수집 지원 (aiohttp + asyncio.gather).

NOTE: 소스별 수집 함수는 collectors/sources.py로 이동됨.
이 파일은 오케스트레이터(_async_collect_trends)와 공개 API만 유지.
기존 ``from scraper import ...`` 호환성을 위해 re-export 포함.
"""

import asyncio

import httpx
from loguru import logger as log

# ══════════════════════════════════════════════════════
#  Backward-compat re-exports from collectors.sources
# ══════════════════════════════════════════════════════
try:
    from .collectors.modoo import fetch_modoo_ideas
    from .collectors.sources import (  # noqa: F401
        _COMMON_HEADERS,
        _DEFAULT_TIMEOUT,
        _FETCH_CACHE,
        _FETCH_CACHE_TTL,
        _GEO_MAP,
        _SHORT_TIMEOUT,
        _YOUTUBE_GEO_MAP,
        _async_fetch_getdaytrends,
        _async_fetch_getdaytrends_standalone,
        _async_fetch_google_trends_rss,
        _async_fetch_google_trends_rss_standalone,
        _async_fetch_hacker_news,
        _async_fetch_hacker_news_standalone,
        _async_fetch_reddit_popular,
        _async_fetch_reddit_popular_standalone,
        _async_fetch_youtube_trending,
        _async_fetch_youtube_trending_standalone,
        _fallback_trends,
        _format_news_age,
        _is_korean_trend,
        _is_similar_keyword,
        _merge_trends,
        _parse_rss_date,
        _parse_volume_text,
        fetch_getdaytrends,
        fetch_google_trends_rss,
        fetch_hacker_news,
        fetch_reddit_popular,
        fetch_youtube_trending,
    )
    from .config import AppConfig
    from .models import MultiSourceContext, RawTrend, TrendSource
    from .utils import run_async
except ImportError:
    from collectors.modoo import fetch_modoo_ideas
    from collectors.sources import (  # noqa: F401
        _COMMON_HEADERS,
        _DEFAULT_TIMEOUT,
        _FETCH_CACHE,
        _FETCH_CACHE_TTL,
        _GEO_MAP,
        _SHORT_TIMEOUT,
        _YOUTUBE_GEO_MAP,
        _async_fetch_getdaytrends,
        _async_fetch_getdaytrends_standalone,
        _async_fetch_google_trends_rss,
        _async_fetch_google_trends_rss_standalone,
        _async_fetch_hacker_news,
        _async_fetch_hacker_news_standalone,
        _async_fetch_reddit_popular,
        _async_fetch_reddit_popular_standalone,
        _async_fetch_youtube_trending,
        _async_fetch_youtube_trending_standalone,
        _fallback_trends,
        _format_news_age,
        _is_korean_trend,
        _is_similar_keyword,
        _merge_trends,
        _parse_rss_date,
        _parse_volume_text,
        fetch_getdaytrends,
        fetch_google_trends_rss,
        fetch_hacker_news,
        fetch_reddit_popular,
        fetch_youtube_trending,
    )
    from config import AppConfig
    from models import MultiSourceContext, RawTrend, TrendSource
    from utils import run_async

# ══════════════════════════════════════════════════════
#  Async Orchestrator
# ══════════════════════════════════════════════════════


def _source_fetch_options(config: AppConfig) -> dict[str, int | bool]:
    return {
        "hn_enabled": bool(getattr(config, "enable_hacker_news", False)),
        "hn_limit": int(getattr(config, "hacker_news_limit", 15)),
        "rd_enabled": bool(getattr(config, "enable_reddit_primary", False)),
        "rd_limit": int(getattr(config, "reddit_primary_limit", 20)),
        "modoo_enabled": bool(getattr(config, "enable_modoo", False)),
        "modoo_pages": int(getattr(config, "modoo_pages", 3)),
    }


def _build_fetch_tasks(
    session: httpx.AsyncClient,
    country_slug: str,
    fetch_size: int,
    options: dict[str, int | bool],
) -> tuple[list, dict[str, int]]:
    fetch_tasks = [
        _async_fetch_getdaytrends(session, country_slug, fetch_size),
        _async_fetch_google_trends_rss(session, country_slug, fetch_size),
    ]
    indices = {"getdaytrends": 0, "google_trends": 1, "hacker_news": -1, "reddit": -1, "modoo": -1}
    if options["hn_enabled"]:
        indices["hacker_news"] = len(fetch_tasks)
        fetch_tasks.append(_async_fetch_hacker_news(session, int(options["hn_limit"])))
    if options["rd_enabled"]:
        indices["reddit"] = len(fetch_tasks)
        fetch_tasks.append(_async_fetch_reddit_popular(session, int(options["rd_limit"])))
    if options["modoo_enabled"]:
        indices["modoo"] = len(fetch_tasks)
        fetch_tasks.append(asyncio.to_thread(fetch_modoo_ideas, int(options["modoo_pages"])))
    return fetch_tasks, indices


def _fetch_result_list(fetch_results: list, idx: int) -> list[RawTrend]:
    if idx < 0 or idx >= len(fetch_results):
        return []
    value = fetch_results[idx]
    if isinstance(value, BaseException):
        return []
    return list(value)


def _fetch_result_lists(fetch_results: list, indices: dict[str, int]) -> dict[str, list[RawTrend]]:
    return {name: _fetch_result_list(fetch_results, idx) for name, idx in indices.items()}


def _log_fetch_failures(fetch_results: list, indices: dict[str, int]) -> None:
    warning_sources = {
        "hacker_news": "Hacker News",
        "reddit": "Reddit /r/popular",
        "modoo": "modoo.or.kr",
        "google_trends": "Google Trends",
    }
    for source, label in warning_sources.items():
        idx = indices[source]
        if idx >= 0 and isinstance(fetch_results[idx], BaseException):
            log.warning(f"{label} collection failed: {fetch_results[idx]}")
    gdt_idx = indices["getdaytrends"]
    if isinstance(fetch_results[gdt_idx], Exception):
        log.error(f"getdaytrends collection failed: {fetch_results[gdt_idx]}")


def _active_source_count(options: dict[str, int | bool]) -> int:
    return 2 + sum(1 for flag in ("hn_enabled", "rd_enabled", "modoo_enabled") if bool(options[flag]))


def _ensure_source_success(
    trends_by_source: dict[str, list[RawTrend]],
    total_sources: int,
) -> None:
    success_sources = sum(1 for trends in trends_by_source.values() if trends)
    if success_sources == 0:
        log.error("[source-check] all active sources failed; using fallback trends")
        trends_by_source["getdaytrends"] = _fallback_trends()
    elif success_sources / total_sources < 0.5:
        log.warning(
            f"[source-check] collection success below 50% ({success_sources}/{total_sources}); "
            "continuing with available sources"
        )
    else:
        log.info(f"[source-check] collection success: {success_sources}/{total_sources} active sources")


async def _record_primary_source_quality(
    config: AppConfig,
    conn,
    gdt_trends: list[RawTrend],
    gtr_trends: list[RawTrend],
    fetch_size: int,
) -> None:
    if not getattr(config, "enable_source_quality_tracking", True) or conn is None:
        return
    try:
        from .db import record_source_quality
    except ImportError:
        from db import record_source_quality

    await record_source_quality(
        conn,
        "getdaytrends",
        bool(gdt_trends),
        0,
        len(gdt_trends),
        min(len(gdt_trends) / max(fetch_size, 1), 1.0),
    )
    await record_source_quality(
        conn, "google_trends", bool(gtr_trends), 0, len(gtr_trends), min(len(gtr_trends) / 20, 1.0)
    )


def _merge_primary_trends(
    gdt_trends: list[RawTrend],
    gtr_trends: list[RawTrend],
    modoo_trends: list[RawTrend],
    fetch_size: int,
) -> list[RawTrend]:
    all_trends = _merge_trends(gdt_trends, gtr_trends, limit=fetch_size)
    if modoo_trends:
        all_trends = _merge_trends(all_trends, modoo_trends, limit=fetch_size)
    log.info(
        f"Merge complete: getdaytrends={len(gdt_trends)}, google_trends={len(gtr_trends)}"
        f"{f', modoo={len(modoo_trends)}' if modoo_trends else ''}"
        f", total={len(all_trends)}"
    )
    return all_trends


async def _filter_recently_seen_trends(
    all_trends: list[RawTrend],
    config: AppConfig,
    conn,
) -> list[RawTrend]:
    if conn is None:
        return all_trends
    try:
        from .db import get_recently_processed_keywords
    except ImportError:
        from db import get_recently_processed_keywords

    try:
        seen = await get_recently_processed_keywords(conn, hours=config.dedupe_window_hours)
    except Exception as _e:
        log.warning(f"Recently-seen keyword lookup failed: {_e}")
        seen = set()
    fresh = [t for t in all_trends if not _is_similar_keyword(t.name, seen)]
    if fresh:
        log.info(
            f"Recently-seen dedupe: {len(all_trends)} -> {len(fresh)} "
            f"(excluded {len(all_trends) - len(fresh)})"
        )
        return fresh
    log.warning(
        f"All trends were seen within {config.dedupe_window_hours}h; keeping original trend list"
    )
    return all_trends


def _dedupe_embedding_trends(all_trends: list[RawTrend], config: AppConfig) -> list[RawTrend]:
    if len(all_trends) <= 1 or not getattr(config, "enable_embedding_clustering", True):
        return all_trends
    try:
        from shared.embeddings import deduplicate_texts

        names = [t.name for t in all_trends]
        unique_indices = deduplicate_texts(
            names,
            threshold=getattr(config, "embedding_cluster_threshold", 0.75),
        )
        removed = len(all_trends) - len(unique_indices)
        if removed:
            log.info(f"[embedding-dedupe] removed {removed} duplicate trends; kept {len(unique_indices)}")
            return [all_trends[i] for i in unique_indices]
    except Exception as _e:
        log.debug(f"[embedding-dedupe] skipped: {_e}")
    return all_trends


def _build_seed_contexts(raw_trends: list[RawTrend]) -> dict[str, MultiSourceContext]:
    contexts: dict[str, MultiSourceContext] = {}
    for trend in raw_trends:
        extra_news = ""
        if trend.source == TrendSource.GOOGLE_TRENDS:
            extra_news = " | ".join(trend.extra.get("news_headlines", []))
        elif trend.source == TrendSource.YOUTUBE:
            extra_news = f"[YouTube trend] {trend.name}"
        contexts[trend.name] = MultiSourceContext(news_insight=extra_news)
    return contexts


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
    country_slug = config.resolve_country_slug()
    fetch_size = config.limit + 10  # 여유 있게 수집

    # ── O1-1: 단일 httpx 세션 + 연결 풀 최적화 (aiohttp 잔재 제거) ──
    limits = httpx.Limits(
        max_connections=config.max_workers * 2,
        max_keepalive_connections=config.max_workers,
        keepalive_expiry=30,
    )
    async with httpx.AsyncClient(limits=limits) as session:
        # 1단계: 소스 병렬 수집 (HN + Reddit /r/popular 보조 — 모두 X 비의존 신호)
        options = _source_fetch_options(config)
        fetch_tasks, indices = _build_fetch_tasks(session, country_slug, fetch_size, options)

        fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        _log_fetch_failures(fetch_results, indices)
        trends_by_source = _fetch_result_lists(fetch_results, indices)

        # Allow partial source success and fall back only when every source failed.
        _ensure_source_success(trends_by_source, _active_source_count(options))
        gdt_trends = trends_by_source["getdaytrends"]
        gtr_trends = trends_by_source["google_trends"]
        modoo_trends = trends_by_source["modoo"]

        await _record_primary_source_quality(config, conn, gdt_trends, gtr_trends, fetch_size)

        all_trends = _merge_primary_trends(gdt_trends, gtr_trends, modoo_trends, fetch_size)
        all_trends = await _filter_recently_seen_trends(all_trends, config, conn)
        all_trends = _dedupe_embedding_trends(all_trends, config)

        raw_trends = all_trends[: config.limit]
        contexts = _build_seed_contexts(raw_trends)

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
try:
    from .context_collector import (  # noqa: F401
        _async_collect_contexts,
        _async_fetch_google_news_trends,
        _async_fetch_google_suggest,
        _async_fetch_google_trends_related,
        _async_fetch_reddit_trends,
        _async_fetch_twitter_trends,
        _calc_quality_score,
        fetch_google_news_trends,
        fetch_reddit_trends,
        fetch_twitter_trends,
        post_to_x,
        post_to_x_async,
    )
except ImportError:
    from context_collector import (  # noqa: F401
        _async_collect_contexts,
        _async_fetch_google_news_trends,
        _async_fetch_google_suggest,
        _async_fetch_google_trends_related,
        _async_fetch_reddit_trends,
        _async_fetch_twitter_trends,
        _calc_quality_score,
        fetch_google_news_trends,
        fetch_reddit_trends,
        fetch_twitter_trends,
        post_to_x,
        post_to_x_async,
    )
