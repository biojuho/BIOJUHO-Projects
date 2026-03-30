"""
getdaytrends — Scrapling 기반 뉴스 스크래핑 모듈.

기존 Google News RSS + BeautifulSoup 기반 수집을 보완하여:
1. 안티봇 우회 (TLS 핑거프린트 위장)
2. 적응형 파싱 (사이트 레이아웃 변경에 자동 대응)
3. 한국 뉴스 사이트 직접 수집 (네이버 뉴스, 다음 뉴스)

Usage:
    from news_scraper import fetch_news_enhanced
    articles = await fetch_news_enhanced("삼성전자", max_results=5)
"""

from __future__ import annotations

import urllib.parse

from loguru import logger as log

# Scrapling 선택 의존성
try:
    from scrapling import Fetcher, StealthyFetcher

    SCRAPLING_AVAILABLE = True
except ImportError:
    SCRAPLING_AVAILABLE = False


# ══════════════════════════════════════════════════════
#  Scrapling 기반 뉴스 수집
# ══════════════════════════════════════════════════════


def fetch_news_enhanced(
    keyword: str,
    *,
    max_results: int = 5,
    sources: list[str] | None = None,
) -> list[dict]:
    """
    키워드에 대한 뉴스 기사를 Scrapling으로 수집.

    Returns:
        [{"title": str, "source": str, "url": str, "snippet": str}, ...]
    """
    if not SCRAPLING_AVAILABLE:
        return _fetch_news_fallback(keyword, max_results=max_results)

    results: list[dict] = []
    _sources = sources or ["naver", "daum"]

    for source in _sources:
        try:
            if source == "naver":
                results.extend(_fetch_naver_news(keyword, max_results))
            elif source == "daum":
                results.extend(_fetch_daum_news(keyword, max_results))
        except Exception as e:
            log.debug(f"[Scrapling] {source} 수집 실패: {e}")

    # 중복 제거 (제목 기준)
    seen_titles = set()
    unique = []
    for article in results:
        title_key = article["title"][:30].lower()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique.append(article)

    return unique[:max_results]


def _fetch_naver_news(keyword: str, max_results: int = 5) -> list[dict]:
    """네이버 뉴스 검색 결과 스크래핑."""
    encoded = urllib.parse.quote(keyword)
    url = f"https://search.naver.com/search.naver?where=news&query={encoded}&sort=1"

    try:
        fetcher = Fetcher(auto_match=True)
        page = fetcher.get(url, stealthy_headers=True)

        articles = []
        # 네이버 뉴스 검색 결과 파싱
        news_items = page.css(".news_area") or page.css(".list_news > li")
        for item in news_items[:max_results]:
            title_el = item.css_first(".news_tit") or item.css_first("a.news_tit")
            source_el = item.css_first(".info.press") or item.css_first(".info_group .press")
            snippet_el = item.css_first(".news_dsc") or item.css_first(".dsc_wrap")

            title = title_el.text.strip() if title_el else ""
            source_name = source_el.text.strip() if source_el else "네이버 뉴스"
            snippet = snippet_el.text.strip()[:200] if snippet_el else ""
            link = title_el.attrib.get("href", "") if title_el else ""

            if title:
                articles.append(
                    {
                        "title": title,
                        "source": source_name,
                        "url": link,
                        "snippet": snippet,
                    }
                )

        log.info(f"[Scrapling] 네이버 뉴스 '{keyword}': {len(articles)}건")
        return articles

    except Exception as e:
        log.debug(f"[Scrapling] 네이버 뉴스 수집 실패: {e}")
        return []


def _fetch_daum_news(keyword: str, max_results: int = 5) -> list[dict]:
    """다음 뉴스 검색 결과 스크래핑."""
    encoded = urllib.parse.quote(keyword)
    url = f"https://search.daum.net/search?w=news&q={encoded}&sort=recency"

    try:
        fetcher = Fetcher(auto_match=True)
        page = fetcher.get(url, stealthy_headers=True)

        articles = []
        news_items = page.css(".c-list-basic > li") or page.css("#newsColl .cont_thumb")
        for item in news_items[:max_results]:
            title_el = item.css_first("a.tit_main") or item.css_first(".wrap_tit a")
            source_el = item.css_first(".info_cp") or item.css_first(".cont_info .txt_info")
            snippet_el = item.css_first(".desc") or item.css_first(".f_eb")

            title = title_el.text.strip() if title_el else ""
            source_name = source_el.text.strip() if source_el else "다음 뉴스"
            snippet = snippet_el.text.strip()[:200] if snippet_el else ""
            link = title_el.attrib.get("href", "") if title_el else ""

            if title:
                articles.append(
                    {
                        "title": title,
                        "source": source_name,
                        "url": link,
                        "snippet": snippet,
                    }
                )

        log.info(f"[Scrapling] 다음 뉴스 '{keyword}': {len(articles)}건")
        return articles

    except Exception as e:
        log.debug(f"[Scrapling] 다음 뉴스 수집 실패: {e}")
        return []


def _fetch_news_fallback(keyword: str, max_results: int = 5) -> list[dict]:
    """Scrapling 미설치 시 기존 방식으로 폴백 (빈 리스트 반환)."""
    log.debug("[Scrapling] 미설치 → 뉴스 직접 수집 비활성")
    return []


# ══════════════════════════════════════════════════════
#  scraper.py 통합 헬퍼
# ══════════════════════════════════════════════════════


def enrich_news_context(keyword: str, existing_insight: str) -> str:
    """
    기존 Google News RSS 인사이트를 Scrapling 직접 수집으로 보강.
    기존 인사이트가 충분하면(5건 이상) 추가 수집하지 않음.
    """
    # 기존 인사이트가 이미 충분하면 스킵
    if existing_insight and existing_insight.count("|") >= 4:
        return existing_insight

    articles = fetch_news_enhanced(keyword, max_results=3)
    if not articles:
        return existing_insight

    # 새 기사를 기존 인사이트에 병합
    new_headlines = [f"[{a['source']}] {a['title']}" for a in articles if a["title"] not in existing_insight]

    if not new_headlines:
        return existing_insight

    combined = existing_insight
    if combined and not combined.endswith(" | "):
        combined += " | "
    combined += " | ".join(new_headlines[:3])

    log.info(f"[Scrapling] '{keyword}' 뉴스 보강: +{len(new_headlines)}건")
    return combined
