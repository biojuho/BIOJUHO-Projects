"""Self-critique for DailyNews briefings.

AI-powered 3-axis quality review for generated briefings:
- Accuracy: factual correctness and precision
- Balance: multi-perspective coverage
- Readability: clarity and flow

Ported from instagram-automation/content_critique.py (simplified).
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


CRITIQUE_PROMPT = """\
당신은 뉴스 브리핑 품질 검수 전문가입니다.
다음 브리핑을 3축으로 평가해주세요.

## 브리핑
{briefing}

## 평가 기준 (각 1~10)
1. **accuracy** — 사실적 정확성, 모호한 표현 없는지
2. **balance** — 다양한 관점 반영, 편향 없는지
3. **readability** — 구조 명확, 핵심 전달력, 가독성

## 출력 (JSON만)
{{
  "scores": {{"accuracy": N, "balance": N, "readability": N}},
  "average": N.N,
  "strengths": ["강점1"],
  "weaknesses": ["약점1"],
  "suggestions": ["개선안1"]
}}"""

REVISE_PROMPT = """\
다음 뉴스 브리핑을 검수 피드백에 따라 개선하세요.

## 원본 브리핑
{briefing}

## 검수 피드백
- 약점: {weaknesses}
- 개선안: {suggestions}

## 규칙
- 사실관계를 변경하지 마세요
- 기존 구조를 유지하면서 개선하세요
- 개선된 브리핑 텍스트만 출력하세요"""


SCORE_AXES = ("accuracy", "balance", "readability")


@dataclass
class BriefingCritiqueResult:
    """Result from a single critique pass."""

    scores: dict[str, float] = field(default_factory=dict)
    average: float = 0.0
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    passed: bool = False

    @classmethod
    def from_dict(cls, data: dict, threshold: float = 7.0) -> BriefingCritiqueResult:
        scores = data.get("scores", {})
        vals = [float(v) for v in scores.values()] if scores else []
        avg = sum(vals) / len(vals) if vals else 0.0

        return cls(
            scores=scores,
            average=round(avg, 1),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            suggestions=data.get("suggestions", []),
            passed=avg >= threshold,
        )


@dataclass
class BriefingCritiqueLoopResult:
    """Result from the full critique→revise loop."""

    final_briefing: str = ""
    revisions: int = 0
    passed: bool = False
    critique_history: list[BriefingCritiqueResult] = field(default_factory=list)


class BriefingCritique:
    """AI self-critique loop for news briefings."""

    def __init__(self, threshold: float = 7.0, max_revisions: int = 2):
        self.threshold = threshold
        self.max_revisions = max_revisions
        self._llm = get_client()

    async def critique(self, briefing: str) -> BriefingCritiqueResult:
        """Analyze briefing quality on 3 axes."""
        prompt = CRITIQUE_PROMPT.format(briefing=briefing[:3000])
        resp = await self._llm.acreate(
            tier=TaskTier.STANDARD,
            messages=[{"role": "user", "content": prompt}],
            system="News briefing quality reviewer. Output JSON only.",
        )
        try:
            text = resp.text.strip()
            # Extract JSON from possible markdown code block
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            data = json.loads(text)
            result = BriefingCritiqueResult.from_dict(data, self.threshold)
            logger.info(
                "Critique: avg=%.1f [%s] passed=%s",
                result.average,
                ", ".join(f"{k}={v}" for k, v in result.scores.items()),
                result.passed,
            )
            return result
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Critique JSON parse failed: %s", e)
            return BriefingCritiqueResult(passed=True)

    async def revise(
        self, briefing: str, critique: BriefingCritiqueResult
    ) -> str:
        """Revise briefing based on critique feedback."""
        prompt = REVISE_PROMPT.format(
            briefing=briefing[:3000],
            weaknesses=", ".join(critique.weaknesses),
            suggestions=", ".join(critique.suggestions),
        )
        resp = await self._llm.acreate(
            tier=TaskTier.STANDARD,
            messages=[{"role": "user", "content": prompt}],
            system="News briefing editor. Output improved briefing only.",
        )
        return resp.text.strip()

    async def run_critique_loop(
        self, briefing: str
    ) -> BriefingCritiqueLoopResult:
        """Run critique→revise loop until quality threshold met."""
        current = briefing
        history: list[BriefingCritiqueResult] = []

        for i in range(self.max_revisions + 1):
            result = await self.critique(current)
            history.append(result)

            if result.passed:
                logger.info("Critique passed at iteration %d", i)
                return BriefingCritiqueLoopResult(
                    final_briefing=current,
                    revisions=i,
                    passed=True,
                    critique_history=history,
                )

            if i < self.max_revisions:
                current = await self.revise(current, result)
                logger.info("Revision %d applied", i + 1)

        return BriefingCritiqueLoopResult(
            final_briefing=current,
            revisions=self.max_revisions,
            passed=False,
            critique_history=history,
        )
