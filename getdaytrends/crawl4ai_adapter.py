"""
getdaytrends — Crawl4AI 어댑터.

Firecrawl API 대안으로 로컬 Crawl4AI 크롤러를 사용.
Crawl4AI 미설치 시 자동으로 기존 Firecrawl 클라이언트로 폴백.

설치:
    pip install crawl4ai
    crawl4ai-setup          # Chromium 다운로드

사용법 (firecrawl_bridge.py에서 자동 감지):
    CRAWL4AI가 설치되어 있으면 자동으로 사용됨.
    FIRECRAWL_API_KEY가 설정되어 있으면 Firecrawl 우선.
    둘 다 없으면 크롤링 비활성화.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

from loguru import logger as log

# Crawl4AI는 선택 의존성
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False

_CONTENT_TRUNCATE_CHARS = 3000  # Firecrawl 클라이언트와 동일한 제한

# 싱글톤 크롤러 인스턴스
_crawler: "AsyncWebCrawler | None" = None
_crawler_lock = asyncio.Lock()


async def _get_crawler() -> "AsyncWebCrawler | None":
    """Crawl4AI 싱글톤 크롤러."""
    global _crawler
    if not CRAWL4AI_AVAILABLE:
        return None

    async with _crawler_lock:
        if _crawler is None:
            _crawler = AsyncWebCrawler(
                config=BrowserConfig(
                    headless=True,
                    java_script_enabled=False,  # 뉴스 사이트는 JS 불필요
                )
            )
            await _crawler.__aenter__()
            log.info("[Crawl4AI] 브라우저 인스턴스 초기화 완료")
        return _crawler


def is_available() -> bool:
    """Crawl4AI 사용 가능 여부."""
    return CRAWL4AI_AVAILABLE


async def scrape_url(url: str) -> dict[str, str]:
    """단일 URL을 크롤링하여 마크다운 반환.

    Firecrawl 클라이언트의 scrape_url()과 동일한 반환 형식:
        {"title": str, "content": str, "published_date": str}
    """
    empty = {"title": "", "content": "", "published_date": ""}

    crawler = await _get_crawler()
    if crawler is None:
        return empty

    try:
        md_gen = DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.4, threshold_type="fixed"
            )
        )
        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            markdown_generator=md_gen,
        )

        result = await crawler.arun(url=url, config=config)

        if not result.success:
            log.debug(f"[Crawl4AI] 크롤링 실패: {url} - {result.error_message}")
            return empty

        content = result.markdown.fit_markdown or result.markdown.raw_markdown or ""

        # 본문 길이 제한
        if len(content) > _CONTENT_TRUNCATE_CHARS:
            content = content[:_CONTENT_TRUNCATE_CHARS] + "\n...(truncated)"

        # 메타데이터 추출 (Crawl4AI는 metadata를 별도로 제공하지 않으므로
        # 마크다운 첫 줄을 제목으로 사용)
        title = ""
        lines = content.split("\n", 3)
        for line in lines:
            stripped = line.strip().lstrip("#").strip()
            if stripped and len(stripped) > 5:
                title = stripped[:200]
                break

        return {
            "title": title,
            "content": content,
            "published_date": "",  # Crawl4AI는 발행일 메타 미제공
        }

    except Exception as exc:
        log.debug(f"[Crawl4AI] 예외: {url} - {exc}")
        return empty


async def enrich_trend_context(
    trend_keyword: str,
    news_urls: list[str],
    max_articles: int = 3,
) -> str:
    """뉴스 URL들을 크롤링하여 TrendContext 주입용 텍스트 반환.

    FirecrawlClient.enrich_trend_context()과 동일한 인터페이스.
    """
    if not is_available():
        return ""
    if not news_urls:
        return ""

    urls_to_crawl = news_urls[:max_articles]
    log.info(f"[Crawl4AI] '{trend_keyword}' 기사 {len(urls_to_crawl)}건 크롤링 시작")

    tasks = [scrape_url(url) for url in urls_to_crawl]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    articles = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            log.debug(f"[Crawl4AI] 크롤링 예외: {urls_to_crawl[i]} - {result}")
            continue
        if result and result.get("content"):
            articles.append(result)

    if not articles:
        log.info(f"[Crawl4AI] '{trend_keyword}' 성공 기사 없음")
        return ""

    log.info(f"[Crawl4AI] '{trend_keyword}' {len(articles)}/{len(urls_to_crawl)}건 성공")

    parts = []
    for idx, article in enumerate(articles, 1):
        title = article["title"] or "(제목 없음)"
        content = article["content"].strip()
        date_info = f" ({article['published_date']})" if article["published_date"] else ""
        parts.append(
            f"--- 기사 {idx}{date_info} ---\n"
            f"제목: {title}\n"
            f"본문:\n{content}"
        )

    return "[기사 본문 요약]\n" + "\n\n".join(parts)


async def close() -> None:
    """크롤러 리소스 정리."""
    global _crawler
    if _crawler is not None:
        try:
            await _crawler.__aexit__(None, None, None)
        except Exception:
            pass
        _crawler = None
