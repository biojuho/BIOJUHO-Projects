"""
Firecrawl integration bridge for GetDayTrends pipeline.

Provides a `enrich_contexts_with_firecrawl` function that can be called
after the standard context collection (Step 1) to enrich high-scoring trends
with full-text article content via Firecrawl.

Usage in main.py:
    from firecrawl_bridge import enrich_contexts_with_firecrawl
    contexts = await enrich_contexts_with_firecrawl(quality_trends, contexts, config)
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

try:
    from loguru import logger as log
except ImportError:
    import logging

    log = logging.getLogger(__name__)

from firecrawl_client import get_firecrawl_client

# Crawl4AI 자동 감지 (설치되어 있으면 Firecrawl 대신 우선 사용)
try:
    import crawl4ai_adapter

    _CRAWL4AI_AVAILABLE = crawl4ai_adapter.is_available()
except ImportError:
    _CRAWL4AI_AVAILABLE = False


def _get_backend() -> str:
    """사용할 크롤링 백엔드 결정.

    우선순위: Firecrawl (API 키 있으면) > Crawl4AI (설치되어 있으면) > None
    환경변수 CRAWL_BACKEND=crawl4ai 로 강제 지정 가능.
    """
    override = os.environ.get("CRAWL_BACKEND", "").lower()
    if override == "crawl4ai" and _CRAWL4AI_AVAILABLE:
        return "crawl4ai"
    if override == "firecrawl" and get_firecrawl_client().available:
        return "firecrawl"

    # 자동 감지
    firecrawl_client = get_firecrawl_client()
    if firecrawl_client.available:
        return "firecrawl"
    if _CRAWL4AI_AVAILABLE:
        return "crawl4ai"
    return "none"


async def enrich_contexts_with_firecrawl(
    quality_trends: list,
    contexts: dict[str, Any],
    config: Any = None,
    *,
    max_articles_per_trend: int = 3,
    min_score_for_enrichment: int = 60,
) -> dict[str, Any]:
    """Enrich trend contexts with full-text article content.

    자동으로 Firecrawl 또는 Crawl4AI 백엔드를 선택.
    Firecrawl API 키 설정 시 Firecrawl 우선, 아니면 Crawl4AI 폴백.

    Args:
        quality_trends: List of ScoredTrend objects.
        contexts: Existing contexts dict {keyword: TrendContext}.
        config: Pipeline configuration (optional).
        max_articles_per_trend: Max articles to crawl per trend.
        min_score_for_enrichment: Minimum viral_potential score.

    Returns:
        Updated contexts dict with enriched content.
    """
    backend = _get_backend()
    if backend == "none":
        log.info("[CrawlBridge] No crawl backend available, skipping enrichment")
        return contexts

    log.info(f"[CrawlBridge] Using backend: {backend}")
    client = get_firecrawl_client() if backend == "firecrawl" else None
    eligible = _eligible_trends_for_enrichment(quality_trends, min_score_for_enrichment)
    if not eligible:
        log.info("[CrawlBridge] No trends above enrichment threshold")
        return contexts

    log.info(
        f"[CrawlBridge] Enriching {len(eligible)} trends (min_score={min_score_for_enrichment}, backend={backend})"
    )

    try:
        for trend in eligible:
            await _enrich_single_context(
                trend,
                contexts,
                backend,
                client,
                max_articles_per_trend,
            )
    finally:
        await _close_backend(backend, client)

    return contexts


def _eligible_trends_for_enrichment(quality_trends: list, min_score_for_enrichment: int) -> list:
    return [trend for trend in quality_trends if getattr(trend, "viral_potential", 0) >= min_score_for_enrichment]


async def _crawl_enrichment_text(
    keyword: str,
    news_urls: list[str],
    backend: str,
    client,
    max_articles: int,
) -> str:
    if backend == "crawl4ai":
        return await crawl4ai_adapter.enrich_trend_context(keyword, news_urls, max_articles=max_articles)
    return await client.enrich_trend_context(keyword, news_urls, max_articles=max_articles)


def _attach_enriched_text(ctx: Any, enriched_text: str) -> None:
    if hasattr(ctx, "firecrawl_context"):
        ctx.firecrawl_context = enriched_text
    elif isinstance(ctx, dict):
        ctx["firecrawl_context"] = enriched_text
    else:
        combined = getattr(ctx, "combined_summary", "")
        if isinstance(combined, str):
            ctx.combined_summary = f"{combined}\n\n{enriched_text}"


async def _enrich_single_context(
    trend,
    contexts: dict[str, Any],
    backend: str,
    client,
    max_articles_per_trend: int,
) -> None:
    keyword = getattr(trend, "keyword", str(trend))
    ctx = contexts.get(keyword)
    if ctx is None:
        return

    news_urls = _extract_news_urls(ctx)
    if not news_urls:
        log.debug(f"[CrawlBridge] No news URLs for '{keyword}', skipping")
        return

    try:
        enriched_text = await _crawl_enrichment_text(keyword, news_urls, backend, client, max_articles_per_trend)
    except Exception as exc:
        log.warning(f"[CrawlBridge] Error enriching '{keyword}': {exc}")
        return

    if enriched_text:
        _attach_enriched_text(ctx, enriched_text)
        log.info(f"[CrawlBridge] Enriched '{keyword}' with {len(enriched_text)} chars")


async def _close_backend(backend: str, client) -> None:
    try:
        if backend == "crawl4ai":
            await crawl4ai_adapter.close()
        elif client is not None:
            await client.close()
    except Exception:
        pass


def _extract_news_urls(ctx: Any) -> list[str]:
    """Extract news article URLs from a TrendContext object."""
    urls = _urls_from_news_items(getattr(ctx, "news_items", None))
    if not urls and hasattr(ctx, "news") and isinstance(ctx.news, list):
        urls = _urls_from_news_items(ctx.news)
    if not urls and isinstance(ctx, dict):
        urls = _urls_from_news_items(ctx.get("news", []))
    return urls[:10]


def _urls_from_news_items(items: Any) -> list[str]:
    urls: list[str] = []
    for item in items or []:
        if hasattr(item, "url") and item.url:
            urls.append(item.url)
        elif isinstance(item, dict) and item.get("url"):
            urls.append(item["url"])
    return urls


if __name__ == "__main__":
    """Quick test: verify Firecrawl client is available."""
    client = get_firecrawl_client()
    print(f"Firecrawl available: {client.available}")
    if client.available:
        print("Ready for pipeline integration!")

        async def _test() -> None:
            result = await client.scrape_url("https://news.google.com")
            print(f"Test scrape result: title={result.get('title', 'N/A')[:50]}")
            await client.close()

        asyncio.run(_test())
    else:
        print("Set FIRECRAWL_API_KEY environment variable to enable Firecrawl.")
