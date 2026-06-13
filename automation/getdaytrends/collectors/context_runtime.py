"""Runtime-safe overrides for context collection."""

from __future__ import annotations

import asyncio
import time

import httpx

try:
    from ..config import AppConfig
    from ..models import MultiSourceContext, RawTrend, TrendSource
    from . import context as context_mod
except ImportError:
    import collectors.context as context_mod
    from config import AppConfig
    from models import MultiSourceContext, RawTrend, TrendSource


_CONTEXT_SOURCES = ["twitter", "reddit", "news"]


def _should_skip_context_source(stats: dict, min_calls_to_skip: int) -> bool:
    avg_quality = stats.get("avg_quality_score", 0.5)
    success_rate = stats.get("success_rate", 100.0)
    total_calls = stats.get("total_calls", 0)
    return total_calls >= min_calls_to_skip and avg_quality < 0.3 and success_rate < 40


def _context_source_timeout(stats: dict) -> float:
    avg_quality = stats.get("avg_quality_score", 0.5)
    success_rate = stats.get("success_rate", 100.0)
    if avg_quality >= 0.7 and success_rate >= 80:
        return 10.0
    if avg_quality < 0.5 or success_rate < 60:
        return 2.0
    return 5.0


def _apply_context_source_quality_policy(
    quality_summary: dict,
    *,
    min_calls_to_skip: int,
) -> tuple[set[str], dict[str, float]]:
    skip_sources: set[str] = set()
    source_timeouts: dict[str, float] = {}
    for source_name, stats in quality_summary.items():
        if source_name not in _CONTEXT_SOURCES:
            continue
        if _should_skip_context_source(stats, min_calls_to_skip):
            skip_sources.add(source_name)
            continue
        source_timeouts[source_name] = _context_source_timeout(stats)
    return skip_sources, source_timeouts


def _log_context_source_skips(quality_summary: dict, skip_sources: set[str]) -> None:
    for source_name in skip_sources:
        stats = quality_summary.get(source_name, {})
        context_mod.log.info(
            "  [B-3 quality filter] "
            f"'{source_name}' skipped "
            f"(calls={stats.get('total_calls', 0)}, "
            f"success={stats.get('success_rate', 100.0):.1f}%, "
            f"avg={stats.get('avg_quality_score', 0.5):.2f})"
        )


async def _context_source_quality_settings(conn, config) -> tuple[set[str], dict[str, float]]:
    try:
        try:
            from ..db import get_source_quality_summary
        except ImportError:
            from db import get_source_quality_summary

        quality_summary = await get_source_quality_summary(conn, days=7)
        skip_sources, source_timeouts = _apply_context_source_quality_policy(
            quality_summary,
            min_calls_to_skip=getattr(config, "min_source_quality_calls", 5),
        )
        _log_context_source_skips(quality_summary, skip_sources)
        if source_timeouts:
            context_mod.log.info(f"  [B-3 timeout tuning] {source_timeouts}")
        return skip_sources, source_timeouts
    except Exception as exc:
        context_mod.log.debug(f"source quality summary lookup failed: {exc}")
        return set(), {}


def _context_extra_news_map(raw_trends: list[RawTrend]) -> dict[str, str]:
    extra_news_map: dict[str, str] = {}
    for trend in raw_trends:
        if trend.source == TrendSource.GOOGLE_TRENDS:
            headlines = trend.extra.get("news_headlines", [])
            if headlines:
                extra_news_map[trend.name] = " | ".join(headlines)
    return extra_news_map


def _context_fetch_tasks(
    raw_trends: list[RawTrend],
    active_sources: list[str],
    extra_news_map: dict[str, str],
    shared_session: httpx.AsyncClient,
    config,
    fetch_one,
) -> list[asyncio.Task[tuple[str, str, str]]]:
    tasks: list[asyncio.Task[tuple[str, str, str]]] = []
    for trend in raw_trends:
        extra_news = extra_news_map.get(trend.name, "")
        for source in active_sources:
            tasks.append(
                asyncio.create_task(
                    fetch_one(
                        shared_session,
                        trend.name,
                        source,
                        config.twitter_bearer_token,
                        extra_news if source == "news" else "",
                    )
                )
            )
    return tasks


async def _gather_context_tasks_with_timeout(
    tasks: list[asyncio.Task[tuple[str, str, str]]],
    global_timeout: float,
) -> list[tuple[str, str, str] | Exception]:
    if not tasks:
        return []

    done, pending = await asyncio.wait(tasks, timeout=global_timeout)
    if pending:
        context_mod.log.error(
            "[context collection] global timeout exceeded (%ss); preserving %d completed result(s), cancelling %d pending task(s)",
            global_timeout,
            len(done),
            len(pending),
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


async def _flush_source_metric_events(conn, source_metric_events: list[tuple[str, bool, float, int, float]]) -> None:
    if not source_metric_events:
        return
    try:
        try:
            from ..db import record_source_quality
        except ImportError:
            from db import record_source_quality

        for source_name, success, latency_ms, item_count, quality_score in source_metric_events:
            try:
                await record_source_quality(conn, source_name, success, latency_ms, item_count, quality_score)
            except Exception as exc:
                context_mod.log.warning(f"source quality flush failed ({source_name}): {exc}")
    except Exception as exc:
        context_mod.log.warning(f"source quality flush setup failed: {exc}")


def _apply_context_gathered_results(
    results: dict[str, dict[str, str]],
    gathered: list[tuple[str, str, str] | Exception],
) -> None:
    for item in gathered:
        if isinstance(item, Exception):
            context_mod.log.warning(f"context collection exception: {type(item).__name__}: {item}")
            continue
        keyword, source, text = item
        if keyword in results:
            results[keyword][source] = text
            context_mod.log.debug(f"  async context collected: '{keyword}' [{source}]")


def _enrich_news_insight(keyword: str, news_insight: str) -> str:
    try:
        try:
            from ..news_scraper import enrich_news_context
        except ImportError:
            from news_scraper import enrich_news_context

        return enrich_news_context(keyword, news_insight)
    except ImportError:
        return news_insight
    except Exception as exc:
        context_mod.log.debug(f"[Scrapling] news enrichment failed '{keyword}': {exc}")
        return news_insight


def _context_results_to_models(results: dict[str, dict[str, str]]) -> dict[str, MultiSourceContext]:
    contexts: dict[str, MultiSourceContext] = {}
    for keyword, source_data in results.items():
        contexts[keyword] = MultiSourceContext(
            twitter_insight=source_data.get("twitter", ""),
            reddit_insight=source_data.get("reddit", ""),
            news_insight=_enrich_news_insight(keyword, source_data.get("news", "")),
        )
    return contexts


async def _async_collect_contexts(
    raw_trends: list[RawTrend],
    config: AppConfig,
    session: httpx.AsyncClient | None = None,
    conn=None,
) -> dict[str, MultiSourceContext]:
    """Collect contexts while flushing source-quality metrics sequentially."""
    results: dict[str, dict[str, str]] = {trend.name: {} for trend in raw_trends}
    source_metric_events: list[tuple[str, bool, float, int, float]] = []
    tracking_enabled = conn is not None and getattr(config, "enable_source_quality_tracking", True)

    skip_sources: set[str] = set()
    source_timeouts: dict[str, float] = {}
    if tracking_enabled:
        skip_sources, source_timeouts = await _context_source_quality_settings(conn, config)

    active_sources = [source for source in _CONTEXT_SOURCES if source not in skip_sources]
    extra_news_map = _context_extra_news_map(raw_trends)
    semaphore = asyncio.Semaphore(config.max_workers)

    async def _limited_fetch(
        shared_session: httpx.AsyncClient,
        keyword: str,
        source: str,
        bearer_token: str,
        extra_news: str,
    ) -> tuple[str, str, str]:
        async with semaphore:
            started_at = time.perf_counter()
            success = True
            result: tuple[str, str, str] | None = None
            try:
                result = await context_mod._async_fetch_single_source(
                    shared_session,
                    keyword,
                    source,
                    bearer_token,
                    extra_news,
                    conn=None,
                    timeout_override=source_timeouts.get(source),
                )
                return result
            except asyncio.CancelledError:
                success = False
                raise
            except Exception:
                success = False
                raise
            finally:
                if tracking_enabled:
                    text = result[2] if result is not None else f"[{source} error] {keyword}"
                    latency_ms = (time.perf_counter() - started_at) * 1000
                    quality_score = context_mod._calc_quality_score(text) if success else 0.0
                    source_metric_events.append((source, success, latency_ms, 1 if success else 0, quality_score))

    async def _collect(shared_session: httpx.AsyncClient) -> list[tuple[str, str, str] | Exception]:
        tasks = _context_fetch_tasks(raw_trends, active_sources, extra_news_map, shared_session, config, _limited_fetch)
        return await _gather_context_tasks_with_timeout(tasks, getattr(config, "context_global_timeout", 120))

    if session is not None:
        gathered = await _collect(session)
    else:
        async with httpx.AsyncClient() as shared_session:
            gathered = await _collect(shared_session)

    if tracking_enabled:
        await _flush_source_metric_events(conn, source_metric_events)

    _apply_context_gathered_results(results, gathered)
    return _context_results_to_models(results)

context_mod._async_collect_contexts = _async_collect_contexts
