"""X (Twitter) publishing adapter using tweepy v4 (Twitter API v2).

Publishing modes:
  - ``manual``:  Returns a draft dict; no API call is made (default).
  - ``auto``:    Calls ``POST /2/tweets`` if ``AUTO_PUSH_ENABLED=true``
                 and all required credentials are present.

Required env vars for auto mode (OAuth 1.0a User Context):
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET

Optional:
  X_BEARER_TOKEN      — needed for read-only lookups (not for posting)
  X_DAILY_POST_LIMIT  — per-day cap (default 10); enforced by the adapter
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ContentReport
from antigravity_mcp.integrations.x_token_store import has_credentials, load_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional tweepy import
# ---------------------------------------------------------------------------

_tweepy: Any = None
_TWEEPY_AVAILABLE = False

try:
    import tweepy as _tweepy_module  # type: ignore

    _tweepy = _tweepy_module
    _TWEEPY_AVAILABLE = True
except ImportError:
    logger.debug("tweepy not installed; X posting disabled. Run: pip install tweepy")


# ---------------------------------------------------------------------------
# Simple in-memory daily post counter
# ---------------------------------------------------------------------------

_daily_posts: dict[date, int] = {}


def _today_post_count() -> int:
    return _daily_posts.get(date.today(), 0)


def _increment_post_count() -> None:
    today = date.today()
    _daily_posts[today] = _daily_posts.get(today, 0) + 1


class XAdapter:
    """Publishes content to X (Twitter) or returns a draft dict."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def _build_client(self) -> Any | None:
        """Build a tweepy.Client with OAuth 1.0a credentials. Returns None if unavailable."""
        if not _TWEEPY_AVAILABLE:
            return None
        api_key = load_token("X_API_KEY") or self.settings.x_api_key
        api_secret = load_token("X_API_SECRET") or self.settings.x_api_secret
        access_token = load_token("X_ACCESS_TOKEN") or self.settings.x_access_token
        access_token_secret = load_token("X_ACCESS_TOKEN_SECRET") or self.settings.x_access_token_secret
        if not all([api_key, api_secret, access_token, access_token_secret]):
            return None
        try:
            return _tweepy.Client(
                consumer_key=api_key,
                consumer_secret=api_secret,
                access_token=access_token,
                access_token_secret=access_token_secret,
                wait_on_rate_limit=False,
            )
        except Exception as exc:
            logger.error("Failed to build tweepy.Client: %s", exc)
            return None

    async def publish(
        self,
        report: ContentReport,
        content: str,
        *,
        approval_mode: str,
    ) -> dict[str, str]:
        """Publish content to X or return a draft dict.

        Returns a dict with keys: status, message (optional), tweet_url (if published).
        """
        if approval_mode == "manual" or not self.settings.auto_push_enabled:
            return {
                "status": "draft",
                "message": "Draft prepared. Manual approval required before publishing.",
            }

        # Auto mode: check daily limit
        limit = self.settings.x_daily_post_limit
        if _today_post_count() >= limit:
            logger.warning("X daily post limit (%d) reached; skipping auto-publish.", limit)
            return {
                "status": "blocked",
                "message": f"Daily post limit ({limit}) reached. Draft saved.",
            }

        # Check credentials
        if not _TWEEPY_AVAILABLE:
            return {
                "status": "error",
                "message": "tweepy not installed. Run: pip install 'antigravity-content-engine[social]'",
            }
        if not has_credentials():
            return {
                "status": "error",
                "message": "X API credentials not configured. Set X_API_KEY/SECRET/ACCESS_TOKEN/SECRET.",
            }

        client = self._build_client()
        if client is None:
            return {"status": "error", "message": "Failed to initialise X client."}

        tweet_text = content[:280]  # Twitter's character limit
        try:
            response = client.create_tweet(text=tweet_text)
            tweet_id = response.data["id"]
            tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"
            _increment_post_count()
            logger.info("Published tweet %s for report %s", tweet_id, report.report_id)
            return {
                "status": "published",
                "tweet_id": tweet_id,
                "tweet_url": tweet_url,
            }
        except Exception as exc:
            # Catch tweepy.TweepyException and any other errors
            error_name = type(exc).__name__
            logger.error("X publish failed (%s): %s", error_name, exc)
            if hasattr(exc, "response") and exc.response is not None:  # type: ignore[union-attr]
                status_code = exc.response.status_code  # type: ignore[union-attr]
                if status_code == 429:
                    return {"status": "rate_limited", "message": "X API rate limit hit; try again later."}
                if status_code in (401, 403):
                    return {"status": "auth_error", "message": f"X auth failed ({status_code}); check credentials."}
            return {"status": "error", "message": f"{error_name}: {exc}"}

    def post_thread(self, tweets: list[str]) -> list[dict[str, str]]:
        """Post a thread of tweets (synchronous helper for batch use).

        Returns a list of result dicts per tweet.
        """
        if not _TWEEPY_AVAILABLE or not has_credentials():
            return [{"status": "error", "message": "X not configured."}] * len(tweets)

        client = self._build_client()
        if client is None:
            return [{"status": "error", "message": "X client unavailable."}] * len(tweets)

        results: list[dict[str, str]] = []
        reply_to: str | None = None
        for tweet_text in tweets:
            try:
                kwargs: dict[str, Any] = {"text": tweet_text[:280]}
                if reply_to:
                    kwargs["reply"] = {"in_reply_to_tweet_id": reply_to}
                response = client.create_tweet(**kwargs)
                tweet_id = str(response.data["id"])
                reply_to = tweet_id
                _increment_post_count()
                results.append({"status": "published", "tweet_id": tweet_id})
            except Exception as exc:
                results.append({"status": "error", "message": str(exc)})
                break  # stop thread on first failure
        return results
