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
from typing import Any

try:
    from loguru import logger as log
except ImportError:
    import logging
    log = logging.getLogger(__name__)

from firecrawl_client import FirecrawlClient, get_firecrawl_client


async def enrich_contexts_with_firecrawl(
    quality_trends: list,
    contexts: dict[str, Any],
    config: Any = None,
    *,
    max_articles_per_trend: int = 3,
    min_score_for_enrichment: int = 60,
) -> dict[str, Any]:
    """Enrich trend contexts with Firecrawl full-text article content.

    Only enriches trends above `min_score_for_enrichment` to conserve
    Firecrawl free tier credits (500 crawls/month).

    Args:
        quality_trends: List of ScoredTrend objects.
        contexts: Existing contexts dict {keyword: TrendContext}.
        config: Pipeline configuration (optional).
        max_articles_per_trend: Max articles to crawl per trend.
        min_score_for_enrichment: Minimum viral_potential score.

    Returns:
        Updated contexts dict with Firecrawl-enriched content.
    """
    client = get_firecrawl_client()

    if not client.available:
        log.info("[FirecrawlBridge] API key not configured, skipping enrichment")
        return contexts

    # Filter trends worth enriching
    eligible = [
        t for t in quality_trends
        if getattr(t, "viral_potential", 0) >= min_score_for_enrichment
    ]

    if not eligible:
        log.info("[FirecrawlBridge] No trends above enrichment threshold")
        return contexts

    log.info(
        f"[FirecrawlBridge] Enriching {len(eligible)} trends "
        f"(min_score={min_score_for_enrichment})"
    )

    for trend in eligible:
        keyword = getattr(trend, "keyword", str(trend))
        ctx = contexts.get(keyword)

        if ctx is None:
            continue

        # Extract news URLs from existing context
        news_urls = _extract_news_urls(ctx)
        if not news_urls:
            log.debug(f"[FirecrawlBridge] No news URLs for '{keyword}', skipping")
            continue

        # Enrich with full-text articles
        try:
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

                log.info(f"[FirecrawlBridge] Enriched '{keyword}' with {len(enriched_text)} chars")

        except Exception as exc:
            log.warning(f"[FirecrawlBridge] Error enriching '{keyword}': {exc}")
            continue

    try:
        await client.close()
    except Exception:
        pass

    return contexts


def _extract_news_urls(ctx: Any) -> list[str]:
    """Extract news article URLs from a TrendContext object."""
    urls: list[str] = []

    # Try different context structures
    if hasattr(ctx, "news_items"):
        for item in (ctx.news_items or []):
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
