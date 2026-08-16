"""Detect L0/L1 candidates for shadow measurement and an additive product lane."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .collectors.breaking_news import (
        AdapterResult,
        KmaWeatherAdapter,
        fetch_google_news_breaking,
        fetch_yonhap_breaking,
    )
    from .content_filters import excluded_topic_reason
    from .filter_eval.source_time_shadow import (
        ensure_source_time_column_fail_open,
        record_filter_candidate_with_source_time_fail_open,
    )
else:
    try:
        from .collectors.breaking_news import (
            AdapterResult,
            KmaWeatherAdapter,
            fetch_google_news_breaking,
            fetch_yonhap_breaking,
        )
        from .content_filters import excluded_topic_reason
        from .filter_eval.source_time_shadow import (
            ensure_source_time_column_fail_open,
            record_filter_candidate_with_source_time_fail_open,
        )
    except ImportError:
        from collectors.breaking_news import (
            AdapterResult,
            KmaWeatherAdapter,
            fetch_google_news_breaking,
            fetch_yonhap_breaking,
        )
        from content_filters import excluded_topic_reason
        from filter_eval.source_time_shadow import (
            ensure_source_time_column_fail_open,
            record_filter_candidate_with_source_time_fail_open,
        )

GoogleFetcher = Callable[..., Awaitable[AdapterResult]]
YonhapFetcher = Callable[..., Awaitable[AdapterResult]]


def _utc(value: datetime) -> datetime:
    timestamp = value if value.tzinfo else value.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _product_source_label(source: str) -> str:
    if source == "yonhap-rss":
        return "연합뉴스"
    if source.startswith("kma:"):
        return "기상청"
    return ""


class BreakingNewsObserver:
    """Run approved adapters without merging their candidates into product ranking."""

    def __init__(
        self,
        shadow_store: object | None,
        *,
        google_fetcher: GoogleFetcher = fetch_google_news_breaking,
        yonhap_fetcher: YonhapFetcher = fetch_yonhap_breaking,
        kma_adapter: KmaWeatherAdapter | None = None,
    ) -> None:
        self.shadow_store = shadow_store
        self.google_fetcher = google_fetcher
        self.yonhap_fetcher = yonhap_fetcher
        self.kma_adapter = kma_adapter or KmaWeatherAdapter()

    async def observe(
        self,
        keywords: Iterable[str],
        *,
        observed_at: datetime | None = None,
    ) -> dict[str, object]:
        now = _utc(observed_at or datetime.now(UTC))
        keyword_list = list(keywords)
        ensure_source_time_column_fail_open(self.shadow_store)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            raw_results = await asyncio.gather(
                self.google_fetcher(client, keyword_list, observed_at=now),
                self.yonhap_fetcher(client, observed_at=now),
                self.kma_adapter.collect(observed_at=now),
                return_exceptions=True,
            )

        fallbacks = (
            AdapterResult(source="google-news-rss", available=False, error="observer_failed"),
            AdapterResult(source="yonhap-rss", available=False, error="observer_failed"),
            AdapterResult(source="kma-weather", available=False, error="observer_failed"),
        )
        results: list[AdapterResult] = []
        for result, fallback in zip(raw_results, fallbacks, strict=True):
            results.append(fallback if isinstance(result, BaseException) else result)

        verdicts: Counter[str] = Counter()
        inserted_count = 0
        product_candidates: list[dict[str, object]] = []
        for result in results:
            for item in result.results:
                filter_reason = excluded_topic_reason(item.title, item.extra_text) or ""
                verdict = "block" if filter_reason else "allow"
                verdicts[verdict] += 1
                inserted = record_filter_candidate_with_source_time_fail_open(
                    self.shadow_store,
                    source=item.source,
                    candidate_id=item.candidate_id,
                    title=item.title,
                    extra_text=item.extra_text,
                    filter_verdict=verdict,
                    filter_reason=filter_reason,
                    observed_at=now,
                    source_published_at=item.published_at,
                )
                inserted_count += int(inserted)
                source_label = _product_source_label(item.source)
                if verdict == "allow" and source_label:
                    product_candidates.append(
                        {
                            "id": item.candidate_id,
                            "keyword": item.title,
                            "source": item.source,
                            "source_label": source_label,
                            "source_url": item.source_url,
                            "source_published_at": (
                                _utc(item.published_at).isoformat() if item.published_at is not None else None
                            ),
                        }
                    )

        source_metrics: dict[str, dict[str, object]] = {}
        for result in results:
            metrics: dict[str, object] = dict(result.metrics())
            if result.source == "kma-weather":
                # Event-driven warning lists contain historical announcements;
                # their median age is not a valid source-quality measure.
                metrics.pop("median_minutes", None)
            if result.operation_status:
                metrics["operations"] = dict(result.operation_status)
            source_metrics[result.source] = metrics

        return {
            "enabled": True,
            "available": any(result.available for result in results),
            "observed_at": now.isoformat(),
            "detected_count": sum(len(result.results) for result in results),
            "recorded_count": inserted_count,
            "verdicts": dict(verdicts),
            "product_candidate_count": len(product_candidates),
            "product_candidates": product_candidates,
            "sources": source_metrics,
        }


__all__ = ["BreakingNewsObserver"]
