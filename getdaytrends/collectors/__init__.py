"""collectors/ — Data Collection Package for getdaytrends.

루트 디렉토리의 수집 관련 모듈을 패키지로 재노출.
실제 구현은 context_collector.py, news_scraper.py, scraper.py에 위치.

공개 API:
    collect_contexts(raw_trends, config, session, conn) — 멀티소스 병렬 컨텍스트 수집
    fetch_twitter_trends(keyword, bearer_token)         — X/Twitter 트렌드 수집
    fetch_reddit_trends(keyword)                        — Reddit 핫 포스트 수집
    fetch_google_news_trends(keyword)                   — Google News RSS 수집
    post_to_x(content, access_token)                    — X 트윗 게시
"""

from context_collector import (  # noqa: F401
    _async_collect_contexts,
    _async_fetch_google_news_trends,
    _async_fetch_google_suggest,
    _async_fetch_reddit_trends,
    _async_fetch_twitter_trends,
    fetch_google_news_trends,
    fetch_reddit_trends,
    fetch_twitter_trends,
    post_to_x,
    post_to_x_async,
)

try:
    from news_scraper import enrich_news_context  # noqa: F401
except ImportError:
    pass  # Scrapling 미설치 시 사용 불가

try:
    from scraper import (  # noqa: F401
        scrape_getdaytrends,
    )
except ImportError:
    pass  # 호환성 — scraper.py가 없을 수 있음
