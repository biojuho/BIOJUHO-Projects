"""
getdaytrends - Firecrawl Integration
뉴스 URL에서 기사 본문을 크롤링하여 TrendContext 심층 컨텍스트를 강화.
Firecrawl API (https://firecrawl.dev) 기반 비동기 스크래핑 + 요약.
"""

import asyncio
import os
import time
from dataclasses import dataclass

import httpx
from loguru import logger as log

# ══════════════════════════════════════════════════════
#  Rate Limiter (토큰 버킷, 10 req/min free tier)
# ══════════════════════════════════════════════════════

_FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v1"
_MAX_REQUESTS_PER_MIN = 10
_CONTENT_TRUNCATE_CHARS = 3000  # 기사 본문 최대 길이 (프롬프트 비용 제어)


class _RateLimiter:
    """간단한 슬라이딩 윈도우 레이트 리미터."""

    def __init__(self, max_requests: int = _MAX_REQUESTS_PER_MIN, window_seconds: float = 60.0):
        self._max = max_requests
        self._window = window_seconds
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """슬롯이 확보될 때까지 대기."""
        while True:
            async with self._lock:
                now = time.monotonic()
                self._timestamps = [t for t in self._timestamps if now - t < self._window]
                if len(self._timestamps) < self._max:
                    self._timestamps.append(now)
                    return
                wait = self._window - (now - self._timestamps[0])
            if wait > 0:
                log.debug(f"[Firecrawl] 레이트 리밋 대기: {wait:.1f}s")
                await asyncio.sleep(wait)


# 모듈 레벨 싱글턴
_rate_limiter = _RateLimiter()


# ══════════════════════════════════════════════════════
#  FirecrawlClient
# ══════════════════════════════════════════════════════


@dataclass
class ScrapedArticle:
    """크롤링된 기사 데이터."""

    url: str
    title: str = ""
    content: str = ""
    published_date: str = ""
    success: bool = False


class FirecrawlClient:
    """Firecrawl API 비동기 클라이언트.

    사용법:
        client = FirecrawlClient()
        if not client.available:
            log.warning("Firecrawl API 키 미설정")
            return

        article = await client.scrape_url("https://example.com/news/123")
        context_text = await client.enrich_trend_context("키워드", urls, max_articles=3)
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv("FIRECRAWL_API_KEY", "")
        self._client: httpx.AsyncClient | None = None

    @property
    def available(self) -> bool:
        """API 키가 설정되어 사용 가능한지 여부."""
        return bool(self._api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        """httpx.AsyncClient 싱글턴 (lazy init)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_FIRECRAWL_BASE_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def close(self) -> None:
        """클라이언트 리소스 정리."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # --------------------------------------------------
    #  Core: 단일 URL 스크래핑
    # --------------------------------------------------

    async def scrape_url(self, url: str) -> dict:
        """단일 URL을 스크래핑하여 기사 데이터 반환.

        Returns:
            {"title": str, "content": str, "published_date": str}
            실패 시 모든 값이 빈 문자열.
        """
        empty = {"title": "", "content": "", "published_date": ""}

        if not self.available:
            log.debug("[Firecrawl] API 키 미설정, 스킵")
            return empty

        try:
            await _rate_limiter.acquire()
            client = await self._get_client()

            resp = await client.post(
                "/scrape",
                json={
                    "url": url,
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                },
            )

            if resp.status_code == 402:
                log.warning("[Firecrawl] API 크레딧 소진 (402)")
                return empty
            if resp.status_code == 429:
                log.warning("[Firecrawl] 레이트 리밋 초과 (429)")
                return empty

            resp.raise_for_status()
            data = resp.json()

            # Firecrawl v1 응답 구조: {"success": bool, "data": {"markdown": ..., "metadata": {...}}}
            if not data.get("success"):
                log.warning(f"[Firecrawl] 스크래핑 실패: {url} - {data.get('error', 'unknown')}")
                return empty

            page_data = data.get("data", {})
            metadata = page_data.get("metadata", {})
            markdown = page_data.get("markdown", "")

            # 본문 길이 제한 (LLM 프롬프트 비용 절감)
            if len(markdown) > _CONTENT_TRUNCATE_CHARS:
                markdown = markdown[:_CONTENT_TRUNCATE_CHARS] + "\n...(truncated)"

            return {
                "title": metadata.get("title", "") or metadata.get("ogTitle", ""),
                "content": markdown,
                "published_date": (
                    metadata.get("publishedTime", "")
                    or metadata.get("articlePublishedTime", "")
                    or metadata.get("ogArticlePublishedTime", "")
                ),
            }

        except httpx.TimeoutException:
            log.warning(f"[Firecrawl] 타임아웃: {url}")
            return empty
        except httpx.HTTPStatusError as exc:
            log.warning(f"[Firecrawl] HTTP {exc.response.status_code}: {url}")
            return empty
        except Exception as exc:
            log.warning(f"[Firecrawl] 예외 발생: {url} - {exc}")
            return empty

    # --------------------------------------------------
    #  Batch: 여러 URL 크롤 + 컨텍스트 텍스트 생성
    # --------------------------------------------------

    async def enrich_trend_context(
        self,
        trend_keyword: str,
        news_urls: list[str],
        max_articles: int = 3,
    ) -> str:
        """뉴스 URL들을 크롤링하여 TrendContext 주입용 요약 텍스트 반환.

        Args:
            trend_keyword: 트렌드 키워드 (로그용).
            news_urls: 크롤링할 뉴스 URL 목록.
            max_articles: 최대 크롤링 기사 수.

        Returns:
            "[기사 본문 요약]" 형식의 텍스트. 크롤링 실패 시 빈 문자열.
        """
        if not self.available:
            return ""

        if not news_urls:
            return ""

        # 최대 기사 수 제한
        urls_to_crawl = news_urls[:max_articles]
        log.info(f"[Firecrawl] '{trend_keyword}' 기사 {len(urls_to_crawl)}건 크롤링 시작")

        # 병렬 크롤링 (레이트 리미터가 자동 제어)
        tasks = [self.scrape_url(url) for url in urls_to_crawl]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 성공한 기사만 수집
        articles: list[dict] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                log.warning(f"[Firecrawl] 크롤링 예외: {urls_to_crawl[i]} - {result}")
                continue
            if result and result.get("content"):
                articles.append(result)

        if not articles:
            log.info(f"[Firecrawl] '{trend_keyword}' 크롤링 성공 기사 없음")
            return ""

        log.info(f"[Firecrawl] '{trend_keyword}' {len(articles)}/{len(urls_to_crawl)}건 크롤링 성공")

        # 컨텍스트 텍스트 조립
        parts: list[str] = []
        for idx, article in enumerate(articles, 1):
            title = article["title"] or "(제목 없음)"
            content = article["content"].strip()
            date_info = f" ({article['published_date']})" if article["published_date"] else ""

            parts.append(f"--- 기사 {idx}{date_info} ---\n" f"제목: {title}\n" f"본문:\n{content}")

        return "[기사 본문 요약]\n" + "\n\n".join(parts)


# ══════════════════════════════════════════════════════
#  Module-level helpers (싱글턴 팩토리)
# ══════════════════════════════════════════════════════

_default_client: FirecrawlClient | None = None


def get_firecrawl_client() -> FirecrawlClient:
    """싱글턴 FirecrawlClient 인스턴스 반환."""
    global _default_client
    if _default_client is None:
        _default_client = FirecrawlClient()
    return _default_client
