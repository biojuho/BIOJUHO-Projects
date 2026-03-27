"""
자동 소스 수집 모듈 — NotebookLM용
====================================
키워드를 입력하면 Google News RSS, DuckDuckGo, Wikipedia 등에서
관련 URL을 자동으로 수집하여 NotebookLM 소스로 제공.

무료 API만 사용하여 비용 없이 작동.
"""

import asyncio
import re
from urllib.parse import quote_plus, unquote

import httpx
from loguru import logger as log


# ──────────────────────────────────────────────────
#  Google News RSS
# ──────────────────────────────────────────────────

async def _google_news_search(
    keyword: str,
    lang: str = "ko",
    max_results: int = 5,
) -> list[dict]:
    """Google News RSS에서 뉴스 URL 수집."""
    encoded = quote_plus(keyword)
    rss_url = f"https://news.google.com/rss/search?q={encoded}&hl={lang}&gl=KR&ceid=KR:{lang}"

    results = []
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(rss_url, timeout=15, follow_redirects=True)
            resp.raise_for_status()
            xml = resp.text

        # 간단한 XML 파싱 (xml.etree 대신 regex — 경량)
        items = re.findall(
            r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?</item>",
            xml,
            re.DOTALL,
        )
        for title, link in items[:max_results]:
            # Google News 리다이렉트 URL에서 실제 URL 추출
            real_url = _extract_google_news_url(link.strip())
            results.append({
                "title": _clean_xml(title),
                "url": real_url,
                "source": "google_news",
            })
        log.info(f"[SourceFinder] Google News: {len(results)}개 발견")
    except Exception as e:
        log.warning(f"[SourceFinder] Google News 실패: {e}")

    return results


def _extract_google_news_url(url: str) -> str:
    """Google News 리다이렉트 URL 처리."""
    # 일부 Google News URL은 ./articles/... 형태
    if "news.google.com" in url:
        return url  # NotebookLM이 리다이렉트를 따라감
    return url


def _clean_xml(text: str) -> str:
    """XML CDATA 및 HTML 엔티티 제거."""
    text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'")
    return text.strip()


# ──────────────────────────────────────────────────
#  DuckDuckGo Instant Answer
# ──────────────────────────────────────────────────

async def _duckduckgo_search(
    keyword: str,
    max_results: int = 5,
) -> list[dict]:
    """DuckDuckGo HTML 검색에서 URL 수집."""
    encoded = quote_plus(keyword)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"

    results = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        async with httpx.AsyncClient() as http:
            resp = await http.get(url, headers=headers, timeout=15, follow_redirects=True)
            resp.raise_for_status()
            html = resp.text

        # 결과 URL 추출
        links = re.findall(
            r'class="result__a"[^>]*href="(.*?)"[^>]*>(.*?)</a>',
            html,
        )
        for link, title in links[:max_results]:
            # DuckDuckGo 리다이렉트 URL 디코딩
            real_url = _decode_ddg_url(link)
            if real_url and not any(x in real_url for x in ["duckduckgo.com", "ad_domain"]):
                results.append({
                    "title": re.sub(r"<.*?>", "", title).strip(),
                    "url": real_url,
                    "source": "duckduckgo",
                })
        log.info(f"[SourceFinder] DuckDuckGo: {len(results)}개 발견")
    except Exception as e:
        log.warning(f"[SourceFinder] DuckDuckGo 실패: {e}")

    return results


def _decode_ddg_url(url: str) -> str:
    """DuckDuckGo 리다이렉트 URL에서 실제 URL 추출."""
    if "uddg=" in url:
        match = re.search(r"uddg=([^&]+)", url)
        if match:
            return unquote(match.group(1))
    if url.startswith("//"):
        return "https:" + url
    return url


# ──────────────────────────────────────────────────
#  Wikipedia
# ──────────────────────────────────────────────────

async def _wikipedia_search(
    keyword: str,
    lang: str = "en",
    max_results: int = 2,
) -> list[dict]:
    """Wikipedia API에서 관련 문서 URL 수집."""
    encoded = quote_plus(keyword)
    api_url = (
        f"https://{lang}.wikipedia.org/w/api.php"
        f"?action=opensearch&search={encoded}&limit={max_results}&format=json"
    )

    results = []
    try:
        headers = {
            "User-Agent": "NotebookLM-SourceFinder/1.0 (contact@biojuho.dev)"
        }
        async with httpx.AsyncClient() as http:
            resp = await http.get(api_url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

        # opensearch: [query, [titles], [descriptions], [urls]]
        if len(data) >= 4:
            titles = data[1]
            urls = data[3]
            for title, url in zip(titles, urls):
                results.append({
                    "title": title,
                    "url": url,
                    "source": "wikipedia",
                })
        log.info(f"[SourceFinder] Wikipedia: {len(results)}개 발견")
    except Exception as e:
        log.warning(f"[SourceFinder] Wikipedia 실패: {e}")

    return results


# ──────────────────────────────────────────────────
#  Scholar / arXiv (학술 논문)
# ──────────────────────────────────────────────────

async def _arxiv_search(
    keyword: str,
    max_results: int = 3,
) -> list[dict]:
    """arXiv API에서 학술 논문 URL 수집."""
    encoded = quote_plus(keyword)
    api_url = (
        f"https://export.arxiv.org/api/query"
        f"?search_query=all:{encoded}&start=0&max_results={max_results}"
        f"&sortBy=relevance&sortOrder=descending"
    )

    results = []
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(api_url, timeout=15)
            resp.raise_for_status()
            xml = resp.text

        entries = re.findall(
            r"<entry>.*?<title>(.*?)</title>.*?<id>(.*?)</id>.*?</entry>",
            xml,
            re.DOTALL,
        )
        for title, arxiv_url in entries[:max_results]:
            results.append({
                "title": title.strip().replace("\n", " "),
                "url": arxiv_url.strip(),
                "source": "arxiv",
            })
        log.info(f"[SourceFinder] arXiv: {len(results)}개 발견")
    except Exception as e:
        log.warning(f"[SourceFinder] arXiv 실패: {e}")

    return results


# ──────────────────────────────────────────────────
#  Main: Auto Discover Sources
# ──────────────────────────────────────────────────

async def auto_discover_sources(
    keyword: str,
    source_types: list[str] | None = None,
    max_total: int = 10,
    include_academic: bool = False,
) -> list[dict]:
    """
    키워드로 관련 소스를 자동 수집.

    Args:
        keyword: 검색 키워드
        source_types: 수집 소스 유형 ["news", "web", "wiki", "arxiv"]
        max_total: 최대 URL 수
        include_academic: arXiv 논문 포함 여부

    Returns:
        [{"title": str, "url": str, "source": str}, ...]
    """
    default_types = ["news", "web", "wiki"]
    if include_academic:
        default_types.append("arxiv")
    types = source_types or default_types

    log.info(f"[SourceFinder] '{keyword}' → {types} 검색 시작")

    # 병렬 수집
    tasks = []
    if "news" in types:
        tasks.append(_google_news_search(keyword, max_results=5))
    if "web" in types:
        tasks.append(_duckduckgo_search(keyword, max_results=5))
    if "wiki" in types:
        tasks.append(_wikipedia_search(keyword, max_results=2))
        tasks.append(_wikipedia_search(keyword, lang="ko", max_results=1))
    if "arxiv" in types:
        tasks.append(_arxiv_search(keyword, max_results=3))

    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    # 결과 병합 + 중복 제거
    seen_urls = set()
    merged = []
    for batch in all_results:
        if isinstance(batch, Exception):
            continue
        for item in batch:
            url = item["url"]
            if url not in seen_urls:
                seen_urls.add(url)
                merged.append(item)

    final = merged[:max_total]
    log.info(f"[SourceFinder] 총 {len(final)}개 소스 수집 완료")
    return final


# ──────────────────────────────────────────────────
#  Standalone Test
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    async def _test():
        print("=== Source Finder Test ===")
        results = await auto_discover_sources(
            "CRISPR gene editing",
            include_academic=True,
        )
        for r in results:
            print(f"  [{r['source']:12}] {r['title'][:50]:50} → {r['url'][:80]}")

    asyncio.run(_test())
