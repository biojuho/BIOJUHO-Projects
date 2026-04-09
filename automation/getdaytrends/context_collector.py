"""Compatibility shim for the legacy ``context_collector`` module path."""

try:
    from .collectors.context import (
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
    from .collectors.context_runtime import _async_collect_contexts
except ImportError:
    from collectors.context import (
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
    from collectors.context_runtime import _async_collect_contexts

__all__ = [
    "_async_collect_contexts",
    "_async_fetch_google_news_trends",
    "_async_fetch_google_suggest",
    "_async_fetch_google_trends_related",
    "_async_fetch_reddit_trends",
    "_async_fetch_twitter_trends",
    "_calc_quality_score",
    "fetch_google_news_trends",
    "fetch_reddit_trends",
    "fetch_twitter_trends",
    "post_to_x",
    "post_to_x_async",
]
