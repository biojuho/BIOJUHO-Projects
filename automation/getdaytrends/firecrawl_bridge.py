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

    # Filter trends worth enriching
    eligible = [t for t in quality_trends if getattr(t, "viral_potential", 0) >= min_score_for_enrichment]

    if not eligible:
        log.info("[CrawlBridge] No trends above enrichment threshold")
        return contexts

    log.info(
        f"[CrawlBridge] Enriching {len(eligible)} trends " f"(min_score={min_score_for_enrichment}, backend={backend})"
    )

    for trend in eligible:
        keyword = getattr(trend, "keyword", str(trend))
        ctx = contexts.get(keyword)

        if ctx is None:
            continue

        # Extract news URLs from existing context
        news_urls = _extract_news_urls(ctx)
        if not news_urls:
            log.debug(f"[CrawlBridge] No news URLs for '{keyword}', skipping")
            continue

        # Enrich with full-text articles (backend-aware)
        try:
            if backend == "crawl4ai":
                enriched_text = await crawl4ai_adapter.enrich_trend_context(
                    keyword, news_urls, max_articles=max_articles_per_trend
                )
            else:
                enriched_text = await client.enrich_trend_context(
                    keyword, news_urls, max_articles=max_articles_per_trend
                )

            if enriched_text:
                # Append enriched context to existing context
                if hasattr(ctx, "firecrawl_context"):
                    ctx.firecrawl_context = enriched_text
                elif isinstance(ctx, dict):
                    ctx["firecrawl_context"] = enriched_text
                else:
                    # Fallback: inject into combined_summary
                    combined = getattr(ctx, "combined_summary", "")
                    if isinstance(combined, str):
                        ctx.combined_summary = f"{combined}\n\n{enriched_text}"

                log.info(f"[CrawlBridge] Enriched '{keyword}' with {len(enriched_text)} chars")

        except Exception as exc:
            log.warning(f"[CrawlBridge] Error enriching '{keyword}': {exc}")
            continue

    # Cleanup
    try:
        if backend == "crawl4ai":
            await crawl4ai_adapter.close()
        elif client is not None:
            await client.close()
    except Exception:
        pass

    return contexts


def _extract_news_urls(ctx: Any) -> list[str]:
    """Extract news article URLs from a TrendContext object."""
    urls: list[str] = []

    # Try different context structures
    if hasattr(ctx, "news_items"):
        for item in ctx.news_items or []:
            if hasattr(item, "url") and item.url:
                urls.append(item.url)
            elif isinstance(item, dict) and item.get("url"):
                urls.append(item["url"])

    elif hasattr(ctx, "news") and isinstance(ctx.news, list):
        for item in ctx.news:
            if isinstance(item, dict) and item.get("url"):
                urls.append(item["url"])

    elif isinstance(ctx, dict):
        for item in ctx.get("news", []):
            if isinstance(item, dict) and item.get("url"):
                urls.append(item["url"])

    return urls[:10]  # Cap at 10 URLs


if __name__ == "__main__":
    """Quick test: verify Firecrawl client is available."""
    client = get_firecrawl_client()
    print(f"Firecrawl available: {client.available}")
    if client.available:
        print("Ready for pipeline integration!")

        async def _test():
            result = await client.scrape_url("https://news.google.com")
            print(f"Test scrape result: title={result.get('title', 'N/A')[:50]}")
            await client.close()

        asyncio.run(_test())
    else:
        print("Set FIRECRAWL_API_KEY environment variable to enable Firecrawl.")
