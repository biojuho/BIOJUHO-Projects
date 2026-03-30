"""shared.llm.reasoning.sage - Self-Aware Guided Efficient Reasoning.

Implements SAGE: confidence-based reasoning efficiency:
- Estimates model confidence from the response itself
- High confidence → return immediately (save tokens)
- Low confidence → trigger additional reasoning stages (MARL integration)
- Prevents overthinking on easy tasks, ensures depth on hard ones

Usage:
    engine = SAGEEngine(client)
    result = engine.run(
        messages=[{"role": "user", "content": "간단한 질문"}],
        system="You are a helpful assistant.",
    )
    print(result.text)
    print(result.confidence)      # 0.0-1.0
    print(result.stages_applied)  # 1 if high-confidence, 3-5 if low
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..models import LLMPolicy, LLMResponse, TaskTier

if TYPE_CHECKING:
    from ..client import LLMClient

log = logging.getLogger("shared.llm.reasoning.sage")

# ---------------------------------------------------------------------------
# Confidence estimation prompt
# ---------------------------------------------------------------------------

_CONFIDENCE_PROMPT = """다음은 AI가 생성한 응답입니다. 이 응답의 품질과 정확도를 0~100 점수로 평가해주세요.

<response>
{response}
</response>

평가 기준:
1. 사실적 정확성 (30점)
2. 완전성 - 빠진 정보 없음 (25점)
3. 논리적 일관성 (25점)
4. 명확성과 구체성 (20점)

다음 형식으로만 응답하세요:
SCORE: [0-100]
REASON: [한 줄 요약]"""


@dataclass
class SAGEResult:
    """Result from SAGE adaptive reasoning."""

    text: str
    confidence: float = 0.0
    stages_applied: int = 1
    was_enhanced: bool = False
    original_text: str = ""
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0


def _parse_confidence_score(text: str) -> float:
    """Extract confidence score from SAGE evaluation response."""
    # Look for "SCORE: XX" pattern
    match = re.search(r"SCORE:\s*(\d+)", text, re.IGNORECASE)
    if match:
        score = int(match.group(1))
        return min(max(score / 100.0, 0.0), 1.0)

    # Fallback: look for any standalone number 0-100
    numbers = re.findall(r"\b(\d{1,3})\b", text)
    for n in numbers:
        val = int(n)
        if 0 <= val <= 100:
            return val / 100.0

    # Default: moderate confidence
    return 0.6


def _heuristic_confidence(text: str) -> float:
    """Quick heuristic confidence without LLM call.

    Checks structural markers that correlate with response quality.
    """
    score = 0.5  # baseline

    # Longer, more structured responses tend to be higher quality
    if len(text) > 500:
        score += 0.1
    if len(text) > 1500:
        score += 0.05

    # Code blocks indicate concrete implementation
    code_blocks = text.count("```")
    if code_blocks >= 2:
        score += 0.1

    # Numbered lists indicate structured thinking
    numbered = len(re.findall(r"^\d+[.)]", text, re.MULTILINE))
    if numbered >= 3:
        score += 0.1

    # Hedging language reduces confidence
    hedges = len(re.findall(
        r"(아마도|아닐 수|확실하지|잘 모르|maybe|perhaps|might|possibly|unclear)",
        text, re.IGNORECASE,
    ))
    score -= hedges * 0.05

    # Error/warning indicators reduce confidence
    if re.search(r"(주의|warning|caution|TODO|FIXME|HACK)", text, re.IGNORECASE):
        score -= 0.1

    return min(max(score, 0.0), 1.0)


class SAGEEngine:
    """Self-Aware Guided Efficient Reasoning.

    Dynamically adjusts reasoning depth based on confidence estimation:
    - High confidence (> threshold_high): return immediately
    - Medium: use MARL 3-stage critique-revision
    - Low confidence (< threshold_low): full 5-stage MARL
    """

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def run(
        self,
        *,
        messages: list[dict],
        system: str = "",
        policy: LLMPolicy | None = None,
        tier: TaskTier = TaskTier.MEDIUM,
        max_tokens: int = 2000,
        confidence_high: float = 0.85,
        confidence_low: float = 0.5,
        use_llm_confidence: bool = False,
    ) -> SAGEResult:
        """Run SAGE adaptive reasoning (synchronous).

        Args:
            use_llm_confidence: If True, use LLM-based confidence estimation
                (more accurate but costs extra tokens). Default False uses
                heuristic-only estimation.
        """
        t0 = time.perf_counter()

        # Step 1: Generate initial response
        initial_resp = self._client.create(
            tier=tier,
            messages=messages,
            max_tokens=max_tokens,
            system=system,
            policy=policy,
        )

        total_cost = initial_resp.cost_usd

        # Step 2: Estimate confidence
        if use_llm_confidence:
            conf_resp = self._client.create(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[{
                    "role": "user",
                    "content": _CONFIDENCE_PROMPT.format(response=initial_resp.text),
                }],
                max_tokens=200,
                system="You are a quality evaluator. Be strict and precise.",
                policy=policy,
            )
            confidence = _parse_confidence_score(conf_resp.text)
            total_cost += conf_resp.cost_usd
        else:
            confidence = _heuristic_confidence(initial_resp.text)

        log.info("SAGE confidence: %.2f (threshold high=%.2f, low=%.2f)",
                 confidence, confidence_high, confidence_low)

        # Step 3: Decide on enhancement
        if confidence >= confidence_high:
            # High confidence → return immediately
            log.info("SAGE: high confidence, returning directly (saved %d+ tokens)",
                     max_tokens * 2)
            return SAGEResult(
                text=initial_resp.text,
                confidence=confidence,
                stages_applied=1,
                was_enhanced=False,
                original_text=initial_resp.text,
                total_cost_usd=total_cost,
                total_latency_ms=(time.perf_counter() - t0) * 1000,
            )

        # Medium/Low confidence → apply MARL enhancement
        from ..marl import MARLConfig, MARLPipeline

        stages = 3 if confidence >= confidence_low else 5
        log.info("SAGE: confidence=%.2f, applying MARL %d-stage enhancement", confidence, stages)

        marl = MARLPipeline(self._client)
        marl_result = marl.run(
            messages=messages,
            system=system,
            policy=policy,
            config=MARLConfig(stages=stages),
        )

        total_cost += marl_result.total_cost_usd

        return SAGEResult(
            text=marl_result.final_text,
            confidence=confidence,
            stages_applied=marl_result.stages_completed + 1,  # +1 for initial
            was_enhanced=True,
            original_text=initial_resp.text,
            total_cost_usd=total_cost,
            total_latency_ms=(time.perf_counter() - t0) * 1000,
        )

    async def arun(
        self,
        *,
        messages: list[dict],
        system: str = "",
        policy: LLMPolicy | None = None,
        tier: TaskTier = TaskTier.MEDIUM,
        max_tokens: int = 2000,
        confidence_high: float = 0.85,
        confidence_low: float = 0.5,
        use_llm_confidence: bool = False,
    ) -> SAGEResult:
        """Run SAGE adaptive reasoning (asynchronous)."""
        t0 = time.perf_counter()

        initial_resp = await self._client.acreate(
            tier=tier, messages=messages, max_tokens=max_tokens,
            system=system, policy=policy,
        )
        total_cost = initial_resp.cost_usd

        if use_llm_confidence:
            conf_resp = await self._client.acreate(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[{"role": "user", "content": _CONFIDENCE_PROMPT.format(response=initial_resp.text)}],
                max_tokens=200,
                system="You are a quality evaluator. Be strict and precise.",
                policy=policy,
            )
            confidence = _parse_confidence_score(conf_resp.text)
            total_cost += conf_resp.cost_usd
        else:
            confidence = _heuristic_confidence(initial_resp.text)

        if confidence >= confidence_high:
            return SAGEResult(
                text=initial_resp.text, confidence=confidence,
                stages_applied=1, was_enhanced=False,
                original_text=initial_resp.text,
                total_cost_usd=total_cost,
                total_latency_ms=(time.perf_counter() - t0) * 1000,
            )

        from ..marl import MARLConfig, MARLPipeline

        stages = 3 if confidence >= confidence_low else 5
        marl = MARLPipeline(self._client)
        marl_result = await marl.arun(
            messages=messages, system=system, policy=policy,
            config=MARLConfig(stages=stages),
        )
        total_cost += marl_result.total_cost_usd

        return SAGEResult(
            text=marl_result.final_text, confidence=confidence,
            stages_applied=marl_result.stages_completed + 1,
            was_enhanced=True, original_text=initial_resp.text,
            total_cost_usd=total_cost,
            total_latency_ms=(time.perf_counter() - t0) * 1000,
        )
