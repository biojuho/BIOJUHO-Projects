"""
context_collector — 후방 호환 shim.
실제 구현은 collectors/context.py로 이동.
"""

from collectors.context import *  # noqa: F401, F403
from collectors.context import (  # noqa: F811 — explicit re-exports for IDE
    _async_collect_contexts,
    _async_fetch_google_news_trends,
    _async_fetch_google_suggest,
    _async_fetch_google_trends_related,
    _async_fetch_reddit_trends,
    _async_fetch_reddit_trends_standalone,
    _async_fetch_single_source,
    _async_fetch_twitter_trends,
    _async_fetch_twitter_trends_standalone,
    _async_fetch_x_via_jina,
    _async_fetch_x_via_twikit_or_jina,
    _calc_quality_score,
    _check_rate_limit,
    _format_news_age,
    _is_similar_keyword,
    _parse_rss_date,
    fetch_google_news_trends,
    fetch_reddit_trends,
    fetch_twitter_trends,
    post_to_x,
    post_to_x_async,
)
