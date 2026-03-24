"""collectors/ — Data Collection Package for getdaytrends.

멀티소스 트렌드 수집 패키지.
실제 소스 수집 구현은 collectors/sources.py에 위치.
컨텍스트 수집 구현은 context_collector.py에 위치.
뉴스 강화는 news_scraper.py에 위치.

공개 API (트렌드 수집):
    collect_trends(config, conn)        — 전체 파이프라인 (getdaytrends + Google Trends + YouTube → 병합)
    collect_contexts(raw_trends, config) — 심층 컨텍스트 수집 (Twitter, Reddit, News)
    fetch_getdaytrends(country, limit)  — getdaytrends.com 수집
    fetch_google_trends_rss(country, limit) — Google Trends RSS 수집
    fetch_youtube_trending(country, limit) — YouTube Trending RSS 수집

공개 API (소스별 컨텍스트):
    fetch_twitter_trends(keyword, bearer_token) — X/Twitter 최근 트윗 수집
    fetch_reddit_trends(keyword)                — Reddit 핫 포스트 수집
    fetch_google_news_trends(keyword)           — Google News RSS 수집
    post_to_x(content, access_token)            — X 트윗 게시 (동기)
    post_to_x_async(content, access_token)      — X 트윗 게시 (비동기)
"""

# ── Trend Collection (collectors/sources.py) ──
from collectors.sources import (  # noqa: F401
    _parse_rss_date,
    _format_news_age,
    _parse_volume_text,
    _FETCH_CACHE,
    _FETCH_CACHE_TTL,
    _COMMON_HEADERS,
    _DEFAULT_TIMEOUT,
    _SHORT_TIMEOUT,
    _async_fetch_getdaytrends,
    fetch_getdaytrends,
    _fallback_trends,
    _GEO_MAP,
    _is_korean_trend,
    _async_fetch_google_trends_rss,
    fetch_google_trends_rss,
    _is_similar_keyword,
    _YOUTUBE_GEO_MAP,
    _async_fetch_youtube_trending,
    fetch_youtube_trending,
    _merge_trends,
)

# ── Orchestrator (scraper.py) ──
# NOTE: lazy import to avoid circular dependency (scraper → collectors.sources → collectors/__init__ → scraper)
def __getattr__(name):
    if name in ("collect_trends", "collect_contexts"):
        import scraper as _scraper
        return getattr(_scraper, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# ── Context Collection (context_collector.py) ──
from context_collector import (  # noqa: F401
    _async_collect_contexts,
    _async_fetch_google_news_trends,
    _async_fetch_google_suggest,
    _async_fetch_google_trends_related,
    _async_fetch_reddit_trends,
    _async_fetch_twitter_trends,
    _calc_quality_score,
    fetch_google_news_trends,
    fetch_reddit_trends,
    fetch_twitter_trends,
    post_to_x,
    post_to_x_async,
)

# ── News Scraping (optional, requires Scrapling) ──
try:
    from news_scraper import enrich_news_context  # noqa: F401
except ImportError:
    pass  # Scrapling 미설치 시 사용 불가
