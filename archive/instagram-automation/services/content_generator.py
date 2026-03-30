"""LLM-based Instagram content generator.

Uses shared.llm to generate captions, hashtags, and content strategies
tailored to the account's niche and audience.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root for shared imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config import ContentConfig
from models import InstagramPost, PostType

from shared.llm import TaskTier, get_client

logger = logging.getLogger(__name__)


# ---- Prompt templates ----

CAPTION_PROMPT = """\
당신은 인스타그램 콘텐츠 전문가입니다.

## 주제
{topic}

## 스타일 가이드
- 스타일: {style}
- 타겟 오디언스: {audience}
- 톤: 자연스럽고 친근한 한국어 (AI 어투 금지)
- 현재 시각: {current_time}

## 작성 규칙
1. 첫 줄에 강력한 훅 (질문/반전/충격적 사실)
2. 본문은 가치 전달에 집중 (정보/인사이트/공감)
3. CTA(Call-to-Action)로 마무리 (댓글, 저장, 공유 유도)
4. 이모지 적절히 사용 (과다 사용 금지)
5. 최대 {max_length}자

## 금지 패턴
- "~인 것 같습니다", "주목받고 있다", "관심이 쏠리고 있다"
- 키워드를 첫 문장에서 그대로 반복
- 뻔한 명언이나 격언으로 시작

## 출력
캡션 텍스트만 출력하세요 (해시태그 제외)."""

HASHTAG_PROMPT = """\
다음 인스타그램 캡션에 최적화된 해시태그를 {count}개 생성하세요.

캡션: {caption}
주제: {topic}

규칙:
- 대형 태그(100만+) 3개, 중형(1만~100만) 7개, 소형(1만 미만) 5개 비율
- 한국어 + 영어 혼합
- 첫 번째는 가장 관련성 높은 태그

JSON 배열로만 출력: ["#태그1", "#태그2", ...]"""

ANGLE_PROMPT = """\
다음 주제에 대해 인스타그램 게시물의 앵글(관점)을 3개 제안하세요.

주제: {topic}
최근 트렌드: {trends}

각 앵글은 다음 중 하나:
A. 반전 - 통념을 뒤집는 시각
B. 데이터 펀치 - 놀라운 숫자/통계
C. 공감 자조 - 공감 유발 자기 이야기
D. 꿀팁 - 즉시 적용 가능한 실용 정보
E. 찬반 도발 - 논쟁 유발 의견

JSON으로 출력:
[{{"type": "A", "angle": "설명", "hook": "첫 줄 예시"}}, ...]"""


class ContentGenerator:
    """Generate Instagram posts using LLM."""

    def __init__(self, config: ContentConfig | None = None):
        self.config = config or ContentConfig()
        self._llm = get_client()

    async def research_topic(self, topic: str) -> str:
        """Research a topic using LLM for fact gathering.

        Returns a summary of relevant facts, stats, and recent info.
        """
        prompt = f"""\
다음 주제에 대해 인스타그램 포스트 작성에 도움이 될 정보를 조사하세요.

주제: {topic}

다음을 포함해서 간결하게 정리:
1. 핵심 팩트 2~3개 (숫자/통계 포함)
2. 최신 트렌드 또는 뉴스 1개
3. 타겟 오디언스가 관심 가질 인사이트 1개

5줄 이내로 요약하세요."""

        resp = await self._llm.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            messages=[{"role": "user", "content": prompt}],
            system="Research assistant. Be factual and concise.",
        )
        return resp.text.strip()

    async def generate_caption_with_research(
        self,
        topic: str,
        style: str = "informative",
        audience: str = "20-30대 한국인",
    ) -> str:
        """Generate a caption with research-backed facts."""
        research = await self.research_topic(topic)

        prompt = CAPTION_PROMPT.format(
            topic=f"{topic}\n\n## 리서치 결과\n{research}",
            style=style,
            audience=audience,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M KST"),
            max_length=self.config.max_caption_length,
        )
        resp = await self._llm.acreate(
            tier=TaskTier.STANDARD,
            messages=[{"role": "user", "content": prompt}],
            system="Instagram content expert. Use research facts. Output caption only.",
        )
        return resp.text.strip()

    async def generate_caption(
        self,
        topic: str,
        style: str = "informative",
        audience: str = "20-30대 한국인",
    ) -> str:
        """Generate a single caption for the given topic."""
        prompt = CAPTION_PROMPT.format(
            topic=topic,
            style=style,
            audience=audience,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M KST"),
            max_length=self.config.max_caption_length,
        )
        resp = await self._llm.acreate(
            tier=TaskTier.STANDARD,
            messages=[{"role": "user", "content": prompt}],
            system="Instagram content expert. Output caption only.",
        )
        return resp.text.strip()

    async def generate_hashtags(self, caption: str, topic: str) -> str:
        """Generate optimized hashtags for a caption."""
        prompt = HASHTAG_PROMPT.format(
            caption=caption[:500],
            topic=topic,
            count=self.config.default_hashtag_count,
        )
        resp = await self._llm.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            messages=[{"role": "user", "content": prompt}],
            system="Output JSON array of hashtags only.",
        )
        try:
            tags = json.loads(resp.text.strip())
            return " ".join(tags[: self.config.max_hashtags])
        except (json.JSONDecodeError, TypeError):
            # Fallback: extract hashtags from raw text
            raw = resp.text.strip()
            tags = [w for w in raw.split() if w.startswith("#")]
            return " ".join(tags[: self.config.max_hashtags])

    async def suggest_angles(self, topic: str, trends: str = "") -> list[dict]:
        """Suggest 3 content angles for a topic."""
        prompt = ANGLE_PROMPT.format(topic=topic, trends=trends or "N/A")
        resp = await self._llm.acreate(
            tier=TaskTier.STANDARD,
            messages=[{"role": "user", "content": prompt}],
            system="Output JSON array only.",
        )
        try:
            return json.loads(resp.text.strip())
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse angles, returning empty")
            return []

    async def generate_post(
        self,
        topic: str,
        post_type: PostType = PostType.IMAGE,
        style: str = "informative",
        audience: str = "20-30대 한국인",
        scheduled_at: datetime | None = None,
    ) -> InstagramPost:
        """Generate a complete Instagram post (caption + hashtags)."""
        caption = await self.generate_caption(topic, style, audience)
        hashtags = await self.generate_hashtags(caption, topic)

        return InstagramPost(
            caption=caption,
            hashtags=hashtags,
            post_type=post_type,
            scheduled_at=scheduled_at,
        )

    async def generate_post_with_critique(
        self,
        topic: str,
        post_type: PostType = PostType.IMAGE,
        style: str = "informative",
        audience: str = "20-30대 한국인",
        scheduled_at: datetime | None = None,
        *,
        max_revisions: int = 2,
        min_score: float = 7.0,
    ) -> InstagramPost:
        """Generate a post with AI self-critique quality loop.

        The caption goes through critique→revise cycles until it
        meets the quality threshold or max revisions are reached.
        """
        from services.content_critique import ContentCritique

        # Generate initial caption
        caption = await self.generate_caption(topic, style, audience)

        # Run critique loop
        critique = ContentCritique(threshold=min_score, max_revisions=max_revisions)
        result = await critique.run_critique_loop(caption, topic)

        # Use the refined caption
        final_caption = result.final_caption
        hashtags = await self.generate_hashtags(final_caption, topic)

        post = InstagramPost(
            caption=final_caption,
            hashtags=hashtags,
            post_type=post_type,
            scheduled_at=scheduled_at,
        )

        logger.info(
            "Post with critique: %d revision(s), avg=%.1f, passed=%s",
            result.revisions,
            result.critique_history[-1].average if result.critique_history else 0,
            result.passed,
        )
        return post

    async def generate_daily_batch(
        self,
        topics: list[str],
        posting_hours: list[int] | None = None,
    ) -> list[InstagramPost]:
        """Generate a batch of posts for the day."""
        posting_hours = posting_hours or [7, 12, 18, 21]
        posts = []
        styles = ["informative", "empathetic", "tips", "provocative"]

        for i, topic in enumerate(topics[: len(posting_hours)]):
            hour = posting_hours[i]
            now = datetime.now()
            scheduled = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if scheduled <= now:
                # If the hour already passed, skip
                continue

            style = styles[i % len(styles)]
            post = await self.generate_post(
                topic=topic,
                style=style,
                scheduled_at=scheduled,
            )
            posts.append(post)
            logger.info("Generated post for %02d:00 — %s", hour, topic[:30])

        return posts

    async def generate_dm_response(
        self,
        user_message: str,
        business_context: str = "",
    ) -> str:
        """Generate an LLM-based DM response."""
        prompt = f"""\
사용자 DM: {user_message}

비즈니스 정보: {business_context or '일반 문의'}

규칙:
- 친근하고 전문적인 톤
- 간결하게 답변 (3문장 이내)
- 필요시 추가 문의 유도
- 이모지 1-2개 적절히 사용"""

        resp = await self._llm.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            messages=[{"role": "user", "content": prompt}],
            system="Instagram business DM responder. Be concise and helpful.",
        )
        return resp.text.strip()
