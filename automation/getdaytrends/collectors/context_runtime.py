"""Runtime-safe overrides for context collection."""

from __future__ import annotations

import asyncio
import time

import httpx

try:
    from . import context as context_mod
    from ..config import AppConfig
    from ..models import MultiSourceContext, RawTrend, TrendSource
except ImportError:
    import collectors.context as context_mod
    from config import AppConfig
    from models import MultiSourceContext, RawTrend, TrendSource


async def _async_collect_contexts(
    raw_trends: list[RawTrend],
    config: AppConfig,
    session: httpx.AsyncClient | None = None,
    conn=None,
) -> dict[str, MultiSourceContext]:
    """Collect contexts while flushing source-quality metrics sequentially."""
    sources = ["twitter", "reddit", "news"]
    results: dict[str, dict[str, str]] = {trend.name: {} for trend in raw_trends}
    source_metric_events: list[tuple[str, bool, float, int, float]] = []
    tracking_enabled = conn is not None and getattr(config, "enable_source_quality_tracking", True)

    skip_sources: set[str] = set()
    source_timeouts: dict[str, float] = {}
    if tracking_enabled:
        try:
            try:
                from ..db import get_source_quality_summary
            except ImportError:
                from db import get_source_quality_summary

            quality_summary = await get_source_quality_summary(conn, days=7)
            for source_name, stats in quality_summary.items():
                avg_quality = stats.get("avg_quality_score", 0.5)
                success_rate = stats.get("success_rate", 100.0)
                if avg_quality < 0.3 and source_name in sources:
                    skip_sources.add(source_name)
                    context_mod.log.info(
                        f"  [B-3 quality filter] '{source_name}' skipped (avg={avg_quality:.2f} < 0.3)"
                    )
                elif source_name in sources:
                    if avg_quality >= 0.7 and success_rate >= 80:
                        source_timeouts[source_name] = 10.0
                    elif avg_quality < 0.5 or success_rate < 60:
                        source_timeouts[source_name] = 2.0
                    else:
                        source_timeouts[source_name] = 5.0
            if source_timeouts:
                context_mod.log.info(f"  [B-3 timeout tuning] {source_timeouts}")
        except Exception as exc:
            context_mod.log.debug(f"source quality summary lookup failed: {exc}")

    active_sources = [source for source in sources if source not in skip_sources]

    extra_news_map: dict[str, str] = {}
    for trend in raw_trends:
        if trend.source == TrendSource.GOOGLE_TRENDS:
            headlines = trend.extra.get("news_headlines", [])
            if headlines:
                extra_news_map[trend.name] = " | ".join(headlines)

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

    def _build_tasks(shared_session: httpx.AsyncClient) -> list[asyncio.Task[tuple[str, str, str]]]:
        tasks: list[asyncio.Task[tuple[str, str, str]]] = []
        for trend in raw_trends:
            extra_news = extra_news_map.get(trend.name, "")
            for source in active_sources:
                tasks.append(
                    asyncio.create_task(
                        _limited_fetch(
                            shared_session,
                            trend.name,
                            source,
                            config.twitter_bearer_token,
                            extra_news if source == "news" else "",
                        )
                    )
                )
        return tasks

    async def _collect_with_partial_timeout(
        shared_session: httpx.AsyncClient,
    ) -> list[tuple[str, str, str] | Exception]:
        tasks = _build_tasks(shared_session)
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

    global_timeout = getattr(config, "context_global_timeout", 120)
    if session is not None:
        gathered = await _collect_with_partial_timeout(session)
    else:
        async with httpx.AsyncClient() as shared_session:
            gathered = await _collect_with_partial_timeout(shared_session)

    if tracking_enabled and source_metric_events:
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

    for item in gathered:
        if isinstance(item, Exception):
            context_mod.log.warning(f"context collection exception: {type(item).__name__}: {item}")
            continue
        keyword, source, text = item
        if keyword in results:
            results[keyword][source] = text
            context_mod.log.debug(f"  async context collected: '{keyword}' [{source}]")

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
        except Exception as exc:
            context_mod.log.debug(f"[Scrapling] news enrichment failed '{keyword}': {exc}")

        contexts[keyword] = MultiSourceContext(
            twitter_insight=source_data.get("twitter", ""),
            reddit_insight=source_data.get("reddit", ""),
            news_insight=news_insight,
        )

    return contexts


context_mod._async_collect_contexts = _async_collect_contexts
