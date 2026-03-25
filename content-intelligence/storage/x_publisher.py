"""X(Twitter) 자동 발행 모듈.

QA 통과한 X 콘텐츠를 getdaytrends의 x_client.py를 활용하여 자동 발행한다.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger as log

if TYPE_CHECKING:
    from config import CIEConfig
    from storage.models import ContentBatch, GeneratedContent, PublishResult


def _ensure_gdt_path() -> None:
    """getdaytrends를 임포트 가능하도록 경로 추가."""
    gdt_dir = Path(__file__).resolve().parents[2] / "getdaytrends"
    if str(gdt_dir) not in sys.path:
        sys.path.insert(0, str(gdt_dir))


async def publish_to_x(
    content: GeneratedContent,
    config: CIEConfig,
) -> PublishResult:
    """단일 콘텐츠를 X(Twitter)에 발행한다."""
    from storage.models import PublishResult

    if not config.can_publish_x:
        return PublishResult(
            platform="x",
            success=False,
            target="x",
            error="X 발행 미설정 (CIE_X_PUBLISH=true + X_ACCESS_TOKEN 필요)",
        )

    # QA 점수 확인 (X는 더 높은 기준)
    if content.qa_report and content.qa_report.total_score < config.x_min_qa_score:
        return PublishResult(
            platform="x",
            success=False,
            target="x",
            error=f"QA 점수 미달: {content.qa_report.total_score} < {config.x_min_qa_score}",
        )

    # 규제 준수 확인
    if not content.regulation_compliant:
        return PublishResult(
            platform="x",
            success=False,
            target="x",
            error="규제 미준수 콘텐츠 — 발행 차단",
        )

    try:
        _ensure_gdt_path()

        # getdaytrends의 x_client 활용 시도
        try:
            from x_client import XClient

            client = XClient(
                access_token=config.x_access_token,
                client_id=config.x_client_id,
                client_secret=config.x_client_secret,
            )

            # 본문 + 해시태그 조합
            tweet_text = _compose_tweet(content)
            result = await client.post_tweet(tweet_text)

            if result.get("success"):
                content.published_at = datetime.now()
                content.publish_target = "x"
                tweet_id = result.get("tweet_id", "")
                log.info(f"  ✅ X 발행 성공: {tweet_id}")
                return PublishResult(
                    platform="x",
                    success=True,
                    target="x",
                    page_id=tweet_id,
                )
            else:
                error = result.get("error", "알 수 없는 오류")
                content.publish_error = error
                return PublishResult(
                    platform="x",
                    success=False,
                    target="x",
                    error=error,
                )

        except ImportError:
            # x_client 없을 경우 직접 X API v2 호출
            return await _direct_x_post(content, config)

    except Exception as e:
        error = str(e)
        log.error(f"  ❌ X 발행 에러: {error}")
        content.publish_error = error
        return PublishResult(
            platform="x",
            success=False,
            target="x",
            error=error,
        )


async def _direct_x_post(
    content: GeneratedContent,
    config: CIEConfig,
) -> PublishResult:
    """x_client 없을 경우 직접 X API v2 호출."""
    from storage.models import PublishResult
    import requests

    tweet_text = _compose_tweet(content)

    headers = {
        "Authorization": f"Bearer {config.x_access_token}",
        "Content-Type": "application/json",
    }
    payload = {"text": tweet_text}

    try:
        resp = requests.post(
            "https://api.twitter.com/2/tweets",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if resp.status_code in (200, 201):
            data = resp.json().get("data", {})
            tweet_id = data.get("id", "")
            content.published_at = datetime.now()
            content.publish_target = "x"
            log.info(f"  ✅ X 직접 발행 성공: {tweet_id}")
            return PublishResult(
                platform="x",
                success=True,
                target="x",
                page_id=tweet_id,
            )
        else:
            error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            content.publish_error = error
            return PublishResult(
                platform="x",
                success=False,
                target="x",
                error=error,
            )
    except Exception as e:
        return PublishResult(
            platform="x",
            success=False,
            target="x",
            error=str(e),
        )


async def publish_batch_to_x(
    batch: ContentBatch,
    config: CIEConfig,
) -> list[PublishResult]:
    """배치 내 X 플랫폼 콘텐츠 중 QA 통과한 것만 발행한다."""
    results = []
    for content in batch.contents:
        if content.platform == "x" and content.qa_passed:
            result = await publish_to_x(content, config)
            results.append(result)
    return results


def _compose_tweet(content: GeneratedContent) -> str:
    """콘텐츠 본문 + 해시태그를 트윗 형식으로 조합한다."""
    body = content.body or ""

    # 해시태그 추가
    if content.hashtags:
        hashtag_str = " ".join(f"#{h}" for h in content.hashtags[:5])
        # 280자 제한 고려
        max_body = 280 - len(hashtag_str) - 2
        if len(body) > max_body:
            body = body[:max_body - 1] + "…"
        return f"{body}\n\n{hashtag_str}"

    # 해시태그 없는 경우
    if len(body) > 280:
        body = body[:279] + "…"
    return body
