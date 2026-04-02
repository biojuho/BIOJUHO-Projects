"""Async X publishing helpers for Content Intelligence Engine.

The publish flow requires an OAuth 2.0 user-context access token obtained
through Authorization Code with PKCE. We keep the boundary small here so
publishing does not depend on getdaytrends internals or blocking HTTP calls.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx
from loguru import logger as log

if TYPE_CHECKING:
    from config import CIEConfig
    from storage.models import ContentBatch, GeneratedContent, PublishResult


X_CREATE_TWEET_URL = "https://api.twitter.com/2/tweets"
X_PUBLISH_TIMEOUT_SEC = 30.0


def _get_x_access_token(config: "CIEConfig") -> str:
    return config.x_access_token.strip()


async def publish_to_x(
    content: "GeneratedContent",
    config: "CIEConfig",
) -> "PublishResult":
    """Publish a single approved content item to X."""
    from storage.models import PublishResult

    access_token = _get_x_access_token(config)
    if not config.enable_x_publish or not access_token:
        return PublishResult(
            platform="x",
            success=False,
            target="x",
            error=(
                "X publish is not configured. Set CIE_X_PUBLISH=true and provide "
                "X_ACCESS_TOKEN as an OAuth 2.0 user-context token."
            ),
        )

    if content.qa_report and content.qa_report.total_score < config.x_min_qa_score:
        return PublishResult(
            platform="x",
            success=False,
            target="x",
            error=f"QA score below threshold: {content.qa_report.total_score} < {config.x_min_qa_score}",
        )

    if not content.regulation_compliant:
        return PublishResult(
            platform="x",
            success=False,
            target="x",
            error="Regulation compliance check failed; publishing blocked.",
        )

    tweet_text = _compose_tweet(content)
    result = await _post_tweet(tweet_text, access_token=access_token)
    if result.get("ok"):
        tweet_id = str(result.get("tweet_id", "") or "")
        content.published_at = datetime.now()
        content.publish_target = "x"
        content.publish_error = ""
        log.info("X publish succeeded: {}", tweet_id)
        return PublishResult(
            platform="x",
            success=True,
            target="x",
            page_id=tweet_id,
        )

    error = str(result.get("error", "Unknown X publish error"))
    content.publish_error = error
    log.warning("X publish failed: {}", error)
    return PublishResult(
        platform="x",
        success=False,
        target="x",
        error=error,
    )


async def _post_tweet(
    tweet_text: str,
    *,
    access_token: str,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Post a single tweet through the X API with async I/O."""
    if not access_token:
        return {
            "ok": False,
            "error": (
                "Missing X user-context token. Set X_ACCESS_TOKEN with an "
                "Authorization Code with PKCE access token."
            ),
            "code": 0,
        }

    if len(tweet_text) > 280:
        return {"ok": False, "error": f"Tweet exceeds 280 characters ({len(tweet_text)})", "code": 0}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "ContentIntelligenceEngine/2.0",
    }
    payload = {"text": tweet_text}

    async def _send(client: httpx.AsyncClient) -> dict[str, Any]:
        try:
            response = await client.post(X_CREATE_TWEET_URL, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            return {"ok": False, "error": str(exc), "code": 0}
        return _parse_post_response(response)

    if session is not None:
        return await _send(session)

    async with httpx.AsyncClient(timeout=X_PUBLISH_TIMEOUT_SEC) as client:
        return await _send(client)


def _parse_post_response(response: httpx.Response) -> dict[str, Any]:
    body = _safe_json(response)
    if response.status_code in (200, 201):
        tweet_id = str(body.get("data", {}).get("id", "") or "")
        return {"ok": True, "tweet_id": tweet_id}

    error = _extract_x_error(body, response)
    return {"ok": False, "error": error, "code": response.status_code}


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_x_error(body: dict[str, Any], response: httpx.Response) -> str:
    errors = body.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            detail = first.get("detail") or first.get("message") or first.get("title")
            if detail:
                return str(detail)

    for key in ("detail", "title", "error"):
        value = body.get(key)
        if value:
            return str(value)

    text = response.text.strip()
    if text:
        return f"HTTP {response.status_code}: {text[:200]}"
    return f"HTTP {response.status_code}"


async def publish_batch_to_x(
    batch: "ContentBatch",
    config: "CIEConfig",
) -> list["PublishResult"]:
    """Publish all approved X content items from a batch."""
    results = []
    for content in batch.contents:
        if content.platform == "x" and content.qa_passed:
            result = await publish_to_x(content, config)
            results.append(result)
    return results


def _compose_tweet(content: "GeneratedContent") -> str:
    """Compose body plus hashtags within the X 280-char limit."""
    body = content.body or ""

    if content.hashtags:
        hashtag_str = " ".join(f"#{tag}" for tag in content.hashtags[:5])
        max_body = 280 - len(hashtag_str) - 2
        if len(body) > max_body:
            body = body[: max(0, max_body - 3)] + "..."
        return f"{body}\n\n{hashtag_str}"

    if len(body) > 280:
        body = body[:277] + "..."
    return body
