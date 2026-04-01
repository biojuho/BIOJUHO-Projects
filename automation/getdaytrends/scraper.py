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
        fetch_youtube_trending,
    )
    from .config import AppConfig
    from .models import MultiSourceContext, RawTrend, TrendSource
    from .utils import run_async
except ImportError:
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
        fetch_youtube_trending,
    )
    from config import AppConfig
    from models import MultiSourceContext, RawTrend, TrendSource
    from utils import run_async

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
    try:
        from .db import get_recently_processed_keywords
    except ImportError:
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
            log.warning(
                f"[부분 성공] 데이터 소스 수집 성공률 50% 미만 ({success_sources}/{total_sources}). 파이프라인 강행."
            )
        else:
            log.info(f"[부분 성공] 수집 성공: {success_sources}/{total_sources} 개 소스 가동 중.")

        # 소스 품질 기록 (v5.0)
        if getattr(config, "enable_source_quality_tracking", True) and conn is not None:
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

        # 2단계: 병합 (getdaytrends → google_trends 순서 우선)
        all_trends = _merge_trends(gdt_trends, gtr_trends, limit=fetch_size)
        log.info(
            f"병합 완료: getdaytrends={len(gdt_trends)}, google_trends={len(gtr_trends)} " f"→ 총 {len(all_trends)}개"
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
        if len(all_trends) > 1 and getattr(config, "enable_embedding_clustering", True):
            try:
                from shared.embeddings import deduplicate_texts

                names = [t.name for t in all_trends]
                unique_indices = deduplicate_texts(
                    names,
                    threshold=getattr(config, "embedding_cluster_threshold", 0.75),
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
