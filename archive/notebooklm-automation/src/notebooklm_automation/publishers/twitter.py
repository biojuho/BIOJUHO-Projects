"""X/Twitter auto-publisher — post tweets from content factory results.

Standalone implementation using httpx so this package has no dependency
on ``getdaytrends/scraper.py``.
"""

from __future__ import annotations

import httpx
from loguru import logger as log

from ..config import get_config


async def post_tweet(
    text: str,
    access_token: str | None = None,
) -> dict:
    """Post a tweet via the X API v2.

    Args:
        text: Tweet content (max 280 chars).
        access_token: OAuth 2.0 user token.  Falls back to ``X_ACCESS_TOKEN`` env.

    Returns:
        ``{"ok": bool, "tweet_id": str, "tweet_url": str, "error": str}``
    """
    cfg = get_config()
    token = access_token or cfg.x_access_token
    if not token:
        return {"ok": False, "tweet_id": "", "tweet_url": "", "error": "X_ACCESS_TOKEN 미설정"}

    if len(text) > 280:
        return {"ok": False, "tweet_id": "", "tweet_url": "", "error": f"트윗 280자 초과 ({len(text)}자)"}

    try:
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                "https://api.x.com/2/tweets",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"text": text},
                timeout=15,
            )

        if resp.status_code in (200, 201):
            data = resp.json().get("data", {})
            tid = data.get("id", "")
            return {
                "ok": True,
                "tweet_id": tid,
                "tweet_url": f"https://x.com/i/status/{tid}",
                "error": "",
            }

        return {"ok": False, "tweet_id": "", "tweet_url": "", "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    except Exception as e:
        log.error("[X] tweet post failed: %s", e)
        return {"ok": False, "tweet_id": "", "tweet_url": "", "error": str(e)}
