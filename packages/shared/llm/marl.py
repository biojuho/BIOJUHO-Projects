"""shared.llm.marl - MARL (Metacognitive Amplification & Reasoning Layer).

Inspired by GiniGen SiteAgent's MARL engine.
A configurable multi-stage pipeline that enhances LLM output quality
by running self-critique and revision cycles.

Usage:
    from shared.llm import get_client
    from shared.llm.marl import MARLPipeline, MARLConfig

    client = get_client()
    marl = MARLPipeline(client)

    # Sync usage
    result = marl.run(
        messages=[{"role": "user", "content": "분석해줘"}],
        system="You are an expert analyst.",
        config=MARLConfig(stages=3),
    )
    print(result.final_text)
    print(result.total_cost_usd)

    # Async usage
    result = await marl.arun(messages=..., system=..., config=MARLConfig(stages=5))
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .models import LLMPolicy, LLMResponse, TaskTier

if TYPE_CHECKING:
    from .client import LLMClient

log = logging.getLogger("shared.llm.marl")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class MARLConfig:
    """Configuration for the MARL metacognitive pipeline.

    Attributes:
        stages: Number of pipeline stages (1-5). Default 3 for cost/quality balance.
            1: Generation only (same as regular call)
            2: Generation + Self-Critique
            3: Generation + Critique + Revision (recommended default)
            4: + Expert Deepening
            5: + Final Synthesis
        critique_tier: TaskTier for critique/revision (use cheap models).
        generation_tier: TaskTier for the initial generation.
        max_tokens_per_stage: Max tokens for each stage.
    """

    stages: int = 3
    critique_tier: TaskTier = TaskTier.LIGHTWEIGHT
    generation_tier: TaskTier = TaskTier.MEDIUM
    max_tokens_per_stage: int = 1500


@dataclass
class MARLStageLog:
    """Log entry for a single MARL stage."""

    stage: int
    name: str
    text: str
    tier: TaskTier
    backend: str = ""
    model: str = ""
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class MARLResult:
    """Result of a MARL pipeline run."""

    final_text: str
    stages_completed: int
    stage_logs: list[MARLStageLog] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    @property
    def initial_text(self) -> str:
        """The text from Stage 1 (before any critique/revision)."""
        if self.stage_logs:
            return self.stage_logs[0].text
        return self.final_text


# ---------------------------------------------------------------------------
# Stage prompt templates
# ---------------------------------------------------------------------------

_CRITIQUE_PROMPT = """다음은 AI가 생성한 응답입니다. 이 응답을 비판적으로 검토해주세요.

<generated_response>
{response}
</generated_response>

다음 관점에서 문제점을 지적해주세요:
1. 사실 정확성: 잘못된 정보나 근거 없는 주장이 있는가?
2. 논리적 일관성: 논리 비약이나 모순이 있는가?
3. 완전성: 빠진 중요한 관점이나 정보가 있는가?
4. 명확성: 모호하거나 이해하기 어려운 부분이 있는가?

비판을 구체적으로 작성하되, 개선 방향도 함께 제시해주세요."""

_REVISION_PROMPT = """다음은 원본 응답과 그에 대한 비판입니다. 비판을 반영하여 개선된 응답을 작성해주세요.

<original_response>
{original}
</original_response>

<critique>
{critique}
</critique>

비판에서 지적된 문제점을 모두 반영하여, 더 정확하고 완전한 응답을 작성해주세요.
원본의 좋은 부분은 유지하되, 문제가 있는 부분만 수정하세요."""

_DEEPENING_PROMPT = """다음 응답을 전문가 수준으로 심화해주세요.

<response>
{response}
</response>

다음을 보강해주세요:
1. 핵심 인사이트를 더 깊이 분석
2. 구체적 사례나 데이터 추가
3. 실용적 권고사항 강화
4. 전문 용어의 정확한 사용"""

_SYNTHESIS_PROMPT = """다음은 같은 주제에 대한 여러 단계의 분석 결과입니다.
모든 관점을 종합하여 최종 응답을 작성해주세요.

<initial_analysis>
{initial}
</initial_analysis>

<revised_analysis>
{revised}
</revised_analysis>

<deepened_analysis>
{deepened}
</deepened_analysis>

위 세 분석을 종합하여 가장 정확하고 완전하며 실용적인 최종 응답을 작성해주세요."""


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class MARLPipeline:
    """MARL 5-stage metacognitive pipeline.

    Enhances LLM output quality by running multiple stages:
    1. Initial Generation
    2. Self-Critique
    3. Revision
    4. Expert Deepening
    5. Final Synthesis
    """

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def run(
        self,
        *,
        messages: list[dict],
        system: str = "",
        policy: LLMPolicy | None = None,
        config: MARLConfig | None = None,
    ) -> MARLResult:
        """Run the MARL pipeline synchronously."""
        cfg = config or MARLConfig()
        t0 = time.perf_counter()
        stages: list[MARLStageLog] = []

        # Stage 1: Initial Generation
        gen_response = self._client.create(
            tier=cfg.generation_tier,
            messages=messages,
            max_tokens=cfg.max_tokens_per_stage,
            system=system,
            policy=policy,
        )
        stages.append(self._log_stage(1, "generation", gen_response))
        current_text = gen_response.text

        if cfg.stages < 2:
            return self._build_result(current_text, stages, t0)

        # Stage 2: Self-Critique
        critique_response = self._client.create(
            tier=cfg.critique_tier,
            messages=[{"role": "user", "content": _CRITIQUE_PROMPT.format(response=current_text)}],
            max_tokens=cfg.max_tokens_per_stage,
            system="You are a critical reviewer. Find flaws and suggest improvements.",
            policy=policy,
        )
        stages.append(self._log_stage(2, "critique", critique_response))

        if cfg.stages < 3:
            return self._build_result(current_text, stages, t0)

        # Stage 3: Revision
        revision_response = self._client.create(
            tier=cfg.generation_tier,
            messages=[
                {
                    "role": "user",
                    "content": _REVISION_PROMPT.format(
                        original=current_text,
                        critique=critique_response.text,
                    ),
                }
            ],
            max_tokens=cfg.max_tokens_per_stage,
            system=system,
            policy=policy,
        )
        stages.append(self._log_stage(3, "revision", revision_response))
        current_text = revision_response.text

        if cfg.stages < 4:
            return self._build_result(current_text, stages, t0)

        # Stage 4: Expert Deepening
        deepening_response = self._client.create(
            tier=cfg.generation_tier,
            messages=[
                {
                    "role": "user",
                    "content": _DEEPENING_PROMPT.format(response=current_text),
                }
            ],
            max_tokens=cfg.max_tokens_per_stage,
            system=system,
            policy=policy,
        )
        stages.append(self._log_stage(4, "deepening", deepening_response))
        current_text = deepening_response.text

        if cfg.stages < 5:
            return self._build_result(current_text, stages, t0)

        # Stage 5: Final Synthesis
        synthesis_response = self._client.create(
            tier=cfg.generation_tier,
            messages=[
                {
                    "role": "user",
                    "content": _SYNTHESIS_PROMPT.format(
                        initial=gen_response.text,
                        revised=revision_response.text,
                        deepened=deepening_response.text,
                    ),
                }
            ],
            max_tokens=cfg.max_tokens_per_stage * 2,  # extra room for synthesis
            system=system,
            policy=policy,
        )
        stages.append(self._log_stage(5, "synthesis", synthesis_response))
        current_text = synthesis_response.text

        return self._build_result(current_text, stages, t0)

    async def arun(
        self,
        *,
        messages: list[dict],
        system: str = "",
        policy: LLMPolicy | None = None,
        config: MARLConfig | None = None,
    ) -> MARLResult:
        """Run the MARL pipeline asynchronously."""
        cfg = config or MARLConfig()
        t0 = time.perf_counter()
        stages: list[MARLStageLog] = []

        # Stage 1: Initial Generation
        gen_response = await self._client.acreate(
            tier=cfg.generation_tier,
            messages=messages,
            max_tokens=cfg.max_tokens_per_stage,
            system=system,
            policy=policy,
        )
        stages.append(self._log_stage(1, "generation", gen_response))
        current_text = gen_response.text

        if cfg.stages < 2:
            return self._build_result(current_text, stages, t0)

        # Stage 2: Self-Critique
        critique_response = await self._client.acreate(
            tier=cfg.critique_tier,
            messages=[{"role": "user", "content": _CRITIQUE_PROMPT.format(response=current_text)}],
            max_tokens=cfg.max_tokens_per_stage,
            system="You are a critical reviewer. Find flaws and suggest improvements.",
            policy=policy,
        )
        stages.append(self._log_stage(2, "critique", critique_response))

        if cfg.stages < 3:
            return self._build_result(current_text, stages, t0)

        # Stage 3: Revision
        revision_response = await self._client.acreate(
            tier=cfg.generation_tier,
            messages=[
                {
                    "role": "user",
                    "content": _REVISION_PROMPT.format(
                        original=current_text,
                        critique=critique_response.text,
                    ),
                }
            ],
            max_tokens=cfg.max_tokens_per_stage,
            system=system,
            policy=policy,
        )
        stages.append(self._log_stage(3, "revision", revision_response))
        current_text = revision_response.text

        if cfg.stages < 4:
            return self._build_result(current_text, stages, t0)

        # Stage 4: Expert Deepening
        deepening_response = await self._client.acreate(
            tier=cfg.generation_tier,
            messages=[
                {
                    "role": "user",
                    "content": _DEEPENING_PROMPT.format(response=current_text),
                }
            ],
            max_tokens=cfg.max_tokens_per_stage,
            system=system,
            policy=policy,
        )
        stages.append(self._log_stage(4, "deepening", deepening_response))
        current_text = deepening_response.text

        if cfg.stages < 5:
            return self._build_result(current_text, stages, t0)

        # Stage 5: Final Synthesis
        synthesis_response = await self._client.acreate(
            tier=cfg.generation_tier,
            messages=[
                {
                    "role": "user",
                    "content": _SYNTHESIS_PROMPT.format(
                        initial=gen_response.text,
                        revised=revision_response.text,
                        deepened=deepening_response.text,
                    ),
                }
            ],
            max_tokens=cfg.max_tokens_per_stage * 2,
            system=system,
            policy=policy,
        )
        stages.append(self._log_stage(5, "synthesis", synthesis_response))
        current_text = synthesis_response.text

        return self._build_result(current_text, stages, t0)

    # -- Helpers --

    @staticmethod
    def _log_stage(stage: int, name: str, response: LLMResponse) -> MARLStageLog:
        return MARLStageLog(
            stage=stage,
            name=name,
            text=response.text,
            tier=response.tier,
            backend=response.backend,
            model=response.model,
            latency_ms=response.latency_ms,
            cost_usd=response.cost_usd,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

    @staticmethod
    def _build_result(
        final_text: str,
        stages: list[MARLStageLog],
        t0: float,
    ) -> MARLResult:
        total_latency = (time.perf_counter() - t0) * 1000
        return MARLResult(
            final_text=final_text,
            stages_completed=len(stages),
            stage_logs=stages,
            total_cost_usd=sum(s.cost_usd for s in stages),
            total_latency_ms=total_latency,
            total_input_tokens=sum(s.input_tokens for s in stages),
            total_output_tokens=sum(s.output_tokens for s in stages),
        )
