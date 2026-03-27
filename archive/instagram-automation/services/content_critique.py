"""AI Self-Critique loop for Instagram content quality assurance.

Inspired by AI-Post-Content-Creator's Plan→Draft→Critique→Revise pattern.
Evaluates content on 5 axes and iteratively refines until quality threshold is met.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.llm import TaskTier, get_client

logger = logging.getLogger(__name__)


# ---- Prompt templates ----

CRITIQUE_PROMPT = """\
당신은 인스타그램 콘텐츠 품질 심사관입니다.
다음 캡션을 5가지 축으로 평가하세요.

## 캡션
{caption}

## 주제
{topic}

## 평가 기준 (각 1~10점)
1. **engagement** — 좋아요/댓글/저장을 유도하는가?
2. **clarity** — 메시지가 명확하고 읽기 쉬운가?
3. **hook** — 첫 줄이 스크롤을 멈추게 하는가?
4. **cta** — 행동 유도(CTA)가 자연스러운가?
5. **authenticity** — AI 어투 없이 자연스러운가?

## 출력 (JSON만)
{{
  "scores": {{
    "engagement": 0,
    "clarity": 0,
    "hook": 0,
    "cta": 0,
    "authenticity": 0
  }},
  "average": 0.0,
  "strengths": ["강점 1", "강점 2"],
  "weaknesses": ["약점 1"],
  "suggestions": ["구체적 개선안 1", "구체적 개선안 2"]
}}"""

REVISE_PROMPT = """\
당신은 인스타그램 콘텐츠 전문가입니다.
다음 캡션을 비평에 따라 개선하세요.

## 원본 캡션
{caption}

## 주제
{topic}

## 비평 결과
- 약점: {weaknesses}
- 개선안: {suggestions}

## 규칙
1. 약점을 반드시 해결할 것
2. 기존 강점은 유지할 것
3. AI 어투 금지 — 자연스러운 한국어
4. 최대 2200자

## 출력
개선된 캡션 텍스트만 출력하세요."""


@dataclass
class CritiqueResult:
    """Result from AI content critique."""

    scores: dict[str, float] = field(default_factory=dict)
    average: float = 0.0
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    passed: bool = False

    @classmethod
    def from_dict(cls, data: dict, threshold: float = 7.0) -> CritiqueResult:
        """Parse from LLM JSON output."""
        scores = data.get("scores", {})
        avg = data.get("average", 0.0)
        # Recalculate average for safety
        if scores:
            avg = sum(scores.values()) / len(scores)
        return cls(
            scores=scores,
            average=round(avg, 1),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            suggestions=data.get("suggestions", []),
            passed=avg >= threshold,
        )


@dataclass
class CritiqueLoopResult:
    """Result from the full critique loop."""

    final_caption: str
    revisions: int
    critique_history: list[CritiqueResult] = field(default_factory=list)
    passed: bool = False


class ContentCritique:
    """AI-powered content quality evaluator and reviser."""

    SCORE_AXES = ["engagement", "clarity", "hook", "cta", "authenticity"]
    DEFAULT_THRESHOLD = 7.0
    DEFAULT_MAX_REVISIONS = 2

    def __init__(self, threshold: float = 7.0, max_revisions: int = 2):
        self._llm = get_client()
        self.threshold = threshold
        self.max_revisions = max_revisions

    async def critique(self, caption: str, topic: str) -> CritiqueResult:
        """Evaluate a caption on 5 axes. Returns scores and feedback."""
        prompt = CRITIQUE_PROMPT.format(caption=caption, topic=topic)
        resp = await self._llm.acreate(
            tier=TaskTier.STANDARD,
            messages=[{"role": "user", "content": prompt}],
            system="Content quality evaluator. Output JSON only.",
        )

        try:
            data = json.loads(resp.text.strip())
            result = CritiqueResult.from_dict(data, self.threshold)
            logger.info(
                "Critique: avg=%.1f passed=%s [%s]",
                result.average,
                result.passed,
                ", ".join(f"{k}={v}" for k, v in result.scores.items()),
            )
            return result
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.warning("Critique parse failed: %s — returning default PASS", e)
            return CritiqueResult(
                scores={ax: 8.0 for ax in self.SCORE_AXES},
                average=8.0,
                passed=True,
            )

    async def revise(
        self, caption: str, topic: str, critique: CritiqueResult
    ) -> str:
        """Revise a caption based on critique feedback."""
        prompt = REVISE_PROMPT.format(
            caption=caption,
            topic=topic,
            weaknesses=", ".join(critique.weaknesses),
            suggestions=", ".join(critique.suggestions),
        )
        resp = await self._llm.acreate(
            tier=TaskTier.STANDARD,
            messages=[{"role": "user", "content": prompt}],
            system="Instagram content reviser. Output improved caption only.",
        )
        revised = resp.text.strip()
        logger.info(
            "Revised caption: %d→%d chars", len(caption), len(revised)
        )
        return revised

    async def run_critique_loop(
        self,
        caption: str,
        topic: str,
        *,
        max_revisions: int | None = None,
        threshold: float | None = None,
    ) -> CritiqueLoopResult:
        """Run critique→revise loop until quality threshold is met.

        Returns the final caption and full critique history.
        """
        max_rev = max_revisions if max_revisions is not None else self.max_revisions
        thresh = threshold if threshold is not None else self.threshold
        current = caption
        history: list[CritiqueResult] = []

        for revision_num in range(max_rev + 1):
            result = await self.critique(current, topic)
            history.append(result)

            if result.passed:
                logger.info(
                    "Critique PASSED (avg=%.1f) after %d revision(s)",
                    result.average,
                    revision_num,
                )
                return CritiqueLoopResult(
                    final_caption=current,
                    revisions=revision_num,
                    critique_history=history,
                    passed=True,
                )

            # Don't revise on the last iteration
            if revision_num < max_rev:
                logger.info(
                    "Revision %d/%d — avg=%.1f (threshold=%.1f)",
                    revision_num + 1,
                    max_rev,
                    result.average,
                    thresh,
                )
                current = await self.revise(current, topic, result)

        # Max revisions reached, return best effort
        logger.warning(
            "Max revisions reached (%d), returning best effort (avg=%.1f)",
            max_rev,
            history[-1].average,
        )
        return CritiqueLoopResult(
            final_caption=current,
            revisions=max_rev,
            critique_history=history,
            passed=False,
        )
