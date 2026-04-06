"""Notion Content Hub 자동 발행 모듈.

CIE에서 생성 + QA 통과한 콘텐츠를 Notion 데이터베이스에 페이지로 발행한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from loguru import logger as log

if TYPE_CHECKING:
    from config import CIEConfig
    from storage.models import ContentBatch, GeneratedContent, PublishResult


async def publish_to_notion(
    content: GeneratedContent,
    config: CIEConfig,
) -> PublishResult:
    """단일 콘텐츠를 Notion Content Hub에 발행한다."""
    from storage.models import PublishResult

    if not config.can_publish_notion:
        return PublishResult(
            platform=content.platform,
            success=False,
            target="notion",
            error="Notion 발행 미설정 (CIE_NOTION_PUBLISH=true 필요)",
        )

    try:
        import httpx

        # Notion API 페이지 생성
        headers = {
            "Authorization": f"Bearer {config.notion_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        # 본문을 Notion 블록으로 변환 (최대 2000자)
        body_text = content.body[:2000] if content.body else "(본문 없음)"
        body_blocks = _split_to_blocks(body_text)

        # v13 표준 스키마 — 8개 속성
        # Tags = keywords + hashtags 통합
        tag_items = [{"name": kw[:100]} for kw in content.trend_keywords_used[:5]]
        if content.hashtags:
            tag_items.extend([{"name": h[:100]} for h in content.hashtags[:5]])

        payload = {
            "parent": {"database_id": config.notion_database_id},
            "properties": {
                "Name": {
                    "title": [
                        {
                            "text": {
                                "content": content.title
                                or f"[{content.platform.upper()}] {content.trend_keywords_used[0] if content.trend_keywords_used else 'CIE 콘텐츠'}"
                            }
                        }
                    ]
                },
                "Status": {"select": {"name": "Draft"}},
                "Platform": {"select": {"name": content.platform.upper()}},
                "Score": {"number": content.qa_report.total_score if content.qa_report else 0},
                "Tags": {"multi_select": tag_items},
            },
            "children": body_blocks,
        }

        # C-06 fix: async httpx로 교체 — 이벤트루프 블로킹 방지
        # M-08 fix: 429 Rate Limit 재시도 (최대 2회)
        import asyncio as _asyncio

        resp = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            for _attempt in range(3):
                resp = await client.post(
                    "https://api.notion.com/v1/pages",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code != 429:
                    break
                retry_after = min(int(resp.headers.get("retry-after", "2")), 30)
                log.warning(f"  ⏳ Notion 429 Rate Limit — {retry_after}s 대기 후 재시도")
                await _asyncio.sleep(retry_after)

        if resp is not None and resp.status_code == 200:
            page_id = resp.json().get("id", "")
            content.notion_page_id = page_id
            content.published_at = datetime.now()
            content.publish_target = "notion"

            log.info(f"  ✅ Notion 발행 성공: {content.platform}/{content.content_type} → {page_id}")
            return PublishResult(
                platform=content.platform,
                success=True,
                target="notion",
                page_id=page_id,
            )
        else:
            error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            log.warning(f"  ❌ Notion 발행 실패: {error}")
            content.publish_error = error
            return PublishResult(
                platform=content.platform,
                success=False,
                target="notion",
                error=error,
            )

    except Exception as e:
        error = str(e)
        log.error(f"  ❌ Notion 발행 에러: {error}")
        content.publish_error = error
        return PublishResult(
            platform=content.platform,
            success=False,
            target="notion",
            error=error,
        )


async def publish_batch_to_notion(
    batch: ContentBatch,
    config: CIEConfig,
) -> list[PublishResult]:
    """배치 내 모든 QA 통과 콘텐츠를 Notion에 발행한다."""
    results = []
    for content in batch.contents:
        if content.qa_passed:
            result = await publish_to_notion(content, config)
            results.append(result)
    return results


def _split_to_blocks(text: str, max_len: int = 2000) -> list[dict]:
    """텍스트를 Notion 블록 리스트로 변환한다."""
    blocks = []
    paragraphs = text.split("\n\n")

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 2000자 제한 처리
        while len(para) > max_len:
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": para[:max_len]}}]},
                }
            )
            para = para[max_len:]

        if para:
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": para}}]},
                }
            )

    return blocks or [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": "(빈 본문)"}}]},
        }
    ]
