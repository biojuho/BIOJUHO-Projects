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

import asyncio
import logging
import os
from datetime import date
from typing import Any

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ContentReport
from antigravity_mcp.integrations.x_token_store import has_credentials, load_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Newsletter CTA injection for X ↔ Newsletter cross-pollination
# ---------------------------------------------------------------------------

NEWSLETTER_CTA = "\n\n\ud83d\udce7 \ub9e4\uc77c \uc544\uce68 \uacbd\uc81c \uc778\uc0ac\uc774\ud2b8 \u2192 {signup_url}"


def _inject_newsletter_cta(content: str, *, signup_url: str = "") -> str:
    """Append newsletter signup CTA to X posts if space allows.

    Only injects if:
    1. NEWSLETTER_CTA_ENABLED=1 is set (disabled by default)
    2. signup_url is configured
    3. Total length stays under 280 chars
    """
    if not os.getenv("NEWSLETTER_CTA_ENABLED", ""):
        return content
    if not signup_url:
        signup_url = os.getenv("NEWSLETTER_SIGNUP_URL", "")
    if not signup_url:
        return content
    cta = NEWSLETTER_CTA.format(signup_url=signup_url)
    if len(content) + len(cta) <= 280:
        return content + cta
    return content  # Don't sacrifice content for CTA

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


class XAdapter:
    """Publishes content to X (Twitter) or returns a draft dict."""

    def __init__(self, *, state_store: Any | None = None) -> None:
        self.settings = get_settings()
        self._state_store = state_store

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

        # Auto mode: check daily limit (persistent via SQLite)
        limit = self.settings.x_daily_post_limit
        today_str = date.today().isoformat()
        current_count = self._state_store.get_x_post_count(today_str) if self._state_store is not None else 0
        if current_count >= limit:
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

        tweet_text = _inject_newsletter_cta(content[:270])
        tweet_text = tweet_text[:280]  # Final safety trim
        try:
            response = await asyncio.to_thread(client.create_tweet, text=tweet_text)
            tweet_id = response.data["id"]
            tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"
            if self._state_store is not None:
                self._state_store.increment_x_post_count(today_str)
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

    async def post_thread(self, tweets: list[str]) -> list[dict[str, str]]:
        """Post a thread of tweets.

        Returns a list of result dicts per tweet.
        On mid-thread failure: logs partial thread state, marks remaining as skipped.
        """
        if not _TWEEPY_AVAILABLE or not has_credentials():
            return [{"status": "error", "message": "X not configured."}] * len(tweets)

        client = self._build_client()
        if client is None:
            return [{"status": "error", "message": "X client unavailable."}] * len(tweets)

        # 일일 제한 사전 체크 — 스레드 전체를 게시할 여유가 있는지 확인
        today_str = date.today().isoformat()
        limit = self.settings.x_daily_post_limit
        current_count = self._state_store.get_x_post_count(today_str) if self._state_store is not None else 0
        if current_count + len(tweets) > limit:
            logger.warning(
                "X daily limit would be exceeded by thread (%d + %d > %d); skipping.",
                current_count, len(tweets), limit,
            )
            return [{"status": "blocked", "message": f"Daily limit ({limit}) would be exceeded."}] * len(tweets)

        results: list[dict[str, str]] = []
        reply_to: str | None = None
        for i, tweet_text in enumerate(tweets):
            try:
                kwargs: dict[str, Any] = {"text": tweet_text[:280]}
                if reply_to:
                    kwargs["reply"] = {"in_reply_to_tweet_id": reply_to}
                response = await asyncio.to_thread(client.create_tweet, **kwargs)
                tweet_id = str(response.data["id"])
                reply_to = tweet_id
                if self._state_store is not None:
                    self._state_store.increment_x_post_count(today_str)
                results.append({"status": "published", "tweet_id": tweet_id, "tweet_index": str(i + 1)})
            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                logger.error(
                    "Thread tweet %d/%d failed: %s (published %d so far)",
                    i + 1, len(tweets), error_msg, len(results),
                )
                results.append({"status": "error", "message": error_msg, "tweet_index": str(i + 1)})
                # 나머지 트윗을 skipped로 표시 (silent 유실 방지)
                remaining = len(tweets) - len(results)
                results.extend(
                    {
                        "status": "skipped",
                        "message": f"Skipped: prior tweet {i + 1} failed",
                        "tweet_index": str(i + 2 + offset),
                    }
                    for offset in range(remaining)
                )
                break
        return results

    @staticmethod
    def split_to_thread(
        content: str,
        *,
        max_chars: int = 270,
        max_tweets: int = 5,
        cta: str = "",
    ) -> list[str]:
        """Split long-form content into a numbered thread of tweets.

        Each tweet is numbered (1/N format) and respects the character limit.
        An optional CTA is appended to the final tweet.

        Args:
            content: The full text to split.
            max_chars: Max characters per tweet (default 270, leaving room for numbering).
            max_tweets: Maximum number of tweets in the thread.
            cta: Optional call-to-action text for the last tweet.

        Returns:
            A list of tweet texts ready for ``post_thread()``.
        """
        if len(content) <= 280:
            return [content]

        # Split by paragraphs first, then sentences
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        chunks: list[str] = []
        current_chunk = ""

        for para in paragraphs:
            # If a single paragraph fits, try to add it to current chunk
            if len(current_chunk) + len(para) + 2 <= max_chars:
                current_chunk = f"{current_chunk}\n{para}".strip() if current_chunk else para
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # If paragraph itself is too long, split by sentences
                if len(para) > max_chars:
                    import re

                    sentences = re.split(r"(?<=[.!?])\s+", para)
                    sentence_chunk = ""
                    for sentence in sentences:
                        if len(sentence_chunk) + len(sentence) + 1 <= max_chars:
                            sentence_chunk = f"{sentence_chunk} {sentence}".strip() if sentence_chunk else sentence
                        else:
                            if sentence_chunk:
                                chunks.append(sentence_chunk)
                            sentence_chunk = sentence[:max_chars]
                    if sentence_chunk:
                        chunks.append(sentence_chunk)
                    current_chunk = ""
                else:
                    current_chunk = para

        if current_chunk:
            chunks.append(current_chunk)

        # Limit to max_tweets
        chunks = chunks[:max_tweets]
        total = len(chunks)

        # Number each tweet
        tweets: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            prefix = f"{i}/{total} "
            tweet = f"{prefix}{chunk}"
            if i == total and cta:
                tweet = f"{tweet}\n\n{cta}"
            tweets.append(tweet[:280])

        return tweets
